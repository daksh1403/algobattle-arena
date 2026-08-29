/**
 * panel.ts — manages the problem-detail WebView panel.
 *
 * - `revealOrCreate` reuses the existing panel if one is open
 * - State (problems list, currently selected slug, code buffer) lives in
 *   the WebView; the host only reacts to `select` / `run` / `submit` messages
 * - All cross-origin resources are disabled by a strict CSP
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import * as vscode from 'vscode';
import type { AuthService } from '../../services/AuthService';
import type { ContestCache } from '../../services/ContestCache';
import type { NotificationService } from '../../services/NotificationService';
import type { OutputChannelService } from '../../services/OutputChannelService';
import type { ProblemAPI } from '../../api/problems';
import type { SubmissionAPI } from '../../api/submissions';
import { renderWebviewHtml, renderMarkdown, escapeHtml } from '../shared';
import { slugFromAlgobattlePath, readSolution, pathsFor } from '../../util/problem-storage';
import { fromApiId } from '../../util/languages';
import type { Problem, ProblemDetail } from '../../api/types';

interface RevealOptions {
  context: vscode.ExtensionContext;
  auth: AuthService;
  cache: ContestCache;
  problems: ProblemAPI;
  notifications: NotificationService;
  submissions?: SubmissionAPI;
  output?: OutputChannelService;
}

let activePanel: ProblemDetailPanel | undefined;

export class ProblemDetailPanel {
  static revealOrCreate(opts: RevealOptions): ProblemDetailPanel {
    if (activePanel) {
      activePanel.reveal();
      return activePanel;
    }
    const panel = new ProblemDetailPanel(opts);
    activePanel = panel;
    return panel;
  }

  private readonly panel: vscode.WebviewPanel;
  private readonly disposables: vscode.Disposable[] = [];
  private detailCache = new Map<string, ProblemDetail>();
  private htmlCache: string | undefined;

  private constructor(private readonly opts: RevealOptions) {
    this.panel = vscode.window.createWebviewPanel(
      'algobattle.problemDetail',
      'Algobattle Problems',
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [vscode.Uri.file(opts.context.extensionPath)],
      },
    );

    this.panel.iconPath = vscode.Uri.joinPath(
      vscode.Uri.file(opts.context.extensionPath),
      'resources',
      'icon.png',
    );

    this.panel.webview.onDidReceiveMessage((msg) => this.onMessage(msg), undefined, this.disposables);
    this.panel.onDidDispose(() => this.dispose(), undefined, this.disposables);

    void this.refresh();
  }

  reveal(): void {
    this.panel.reveal(vscode.ViewColumn.Beside);
  }

  private async refresh(): Promise<void> {
    try {
      const problems = await this.opts.problems.listAll();
      this.opts.cache.setProblems(problems);

      const initialState = {
        problems: problems.map((p) => ({
          id: p.id,
          slug: p.slug,
          title: p.title,
          difficulty: p.difficulty,
        })),
        selectedSlug: null,
      };

      this.panel.webview.html = await this.buildHtml(initialState);
    } catch (err) {
      this.opts.notifications.error(err instanceof Error ? err.message : String(err));
    }
  }

  private async buildHtml(initialState: {
    problems: Array<Pick<Problem, 'id' | 'slug' | 'title' | 'difficulty'>>;
    selectedSlug: string | null;
  }): Promise<string> {
    if (this.htmlCache) {
      return renderWebviewHtml({
        title: 'Algobattle · Problem Browser',
        body: await readAsset('main.html'),
        styles: await readAsset('styles.css'),
        script: await readAsset('main.js'),
        initialState,
      });
    }
    return renderWebviewHtml({
      title: 'Algobattle · Problem Browser',
      body: await readAsset('main.html'),
      styles: await readAsset('styles.css'),
      script: await readAsset('main.js'),
      initialState,
    });
  }

  private async onMessage(msg: unknown): Promise<void> {
    if (!msg || typeof msg !== 'object') return;
    const m = msg as { type?: unknown; slug?: unknown; code?: unknown };
    switch (m.type) {
      case 'select': {
        const slug = typeof m.slug === 'string' ? m.slug : '';
        if (slug) await this.loadDetail(slug);
        break;
      }
      case 'run': {
        const slug = typeof m.slug === 'string' ? m.slug : '';
        const code = typeof m.code === 'string' ? m.code : '';
        await this.runSample(slug, code);
        break;
      }
      case 'submit': {
        const slug = typeof m.slug === 'string' ? m.slug : '';
        const code = typeof m.code === 'string' ? m.code : '';
        await this.submit(slug, code);
        break;
      }
      default:
        // ignore unknown
        break;
    }
  }

  private async loadDetail(slug: string): Promise<void> {
    try {
      let detail = this.detailCache.get(slug);
      if (!detail) {
        detail = await this.opts.problems.get(slug);
        this.detailCache.set(slug, detail);
      }
      // Pre-fill the editor with code on disk if available.
      const workspace = vscode.workspace.workspaceFolders?.[0];
      let code = detail.starter_code?.python || '';
      if (workspace) {
        const paths = pathsFor(slug, workspace);
        // Probe common starter extensions.
        for (const ext of ['.py', '.js', '.cpp']) {
          const uri = vscode.Uri.file(paths.starter.fsPath + ext);
          const onDisk = await readSolution(uri);
          if (onDisk) {
            code = onDisk;
            break;
          }
        }
      }

      const stmtHtml = await renderMarkdown(detail.statement_md ?? '');
      this.panel.webview.postMessage({
        type: 'detail',
        detail: {
          ...detail,
          statement_html: stmtHtml,
          code,
        },
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.panel.webview.postMessage({ type: 'error', message });
      this.opts.notifications.error(`Failed to load ${slug}: ${message}`);
    }
  }

  private async runSample(slug: string, code: string): Promise<void> {
    if (!this.opts.submissions) {
      this.panel.webview.postMessage({
        type: 'error',
        message: 'Submission API is not wired up.',
      });
      return;
    }
    try {
      const detail = this.detailCache.get(slug) ?? (await this.opts.problems.get(slug));
      this.detailCache.set(slug, detail);
      const lang = pickLang(detail, code);
      const res = await this.opts.submissions.run({
        problem_id: detail.id,
        language: lang,
        code,
      });
      this.panel.webview.postMessage({
        type: 'run-result',
        verdict: res.verdict,
        results: res.results,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.panel.webview.postMessage({ type: 'error', message });
    }
  }

  private async submit(slug: string, code: string): Promise<void> {
    if (!this.opts.submissions) {
      this.panel.webview.postMessage({ type: 'error', message: 'Submission API is not wired up.' });
      return;
    }
    try {
      await this.opts.auth.load();
      if (!this.opts.auth.snapshot().authenticated) {
        this.panel.webview.postMessage({
          type: 'error',
          message: 'Sign in before submitting.',
        });
        return;
      }
      const detail = this.detailCache.get(slug) ?? (await this.opts.problems.get(slug));
      this.detailCache.set(slug, detail);
      const lang = pickLang(detail, code);
      const sub = await this.opts.submissions.submit({
        problem_id: detail.id,
        language: lang,
        code,
      });
      const final = await this.opts.submissions.pollUntilDone(sub.id, {
        intervalMs: 1500,
        timeoutMs: 5 * 60_000,
      });
      this.panel.webview.postMessage({
        type: 'submit-result',
        verdict: final.verdict,
        results: final.results,
      });
      this.opts.notifications.info(`Submission ${final.verdict.toUpperCase()}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this.panel.webview.postMessage({ type: 'error', message });
    }
  }

  private dispose(): void {
    while (this.disposables.length) {
      const d = this.disposables.pop();
      try { d?.dispose(); } catch { /* ignore */ }
    }
    activePanel = undefined;
  }
}

function pickLang(detail: ProblemDetail, code: string): 'python' | 'javascript' | 'cpp' {
  // Try to detect from a `class Solution:` pattern (Python/CPP) or `function solve(` (JS).
  if (/^\s*def\s+\w+\(/m.test(code) || /^\s*class\s+Solution\s*:/m.test(code)) return 'python';
  if (/^\s*function\s+solve\s*\(/m.test(code) || /module\.exports/.test(code)) return 'javascript';
  if (/^\s*#include\s+/m.test(code)) return 'cpp';
  // Fallback: use the first starter language.
  for (const lang of ['python', 'javascript', 'cpp'] as const) {
    if (detail.starter_code?.[lang]) return lang;
  }
  return 'python';
}

async function readAsset(name: string): Promise<string> {
  const candidates = [
    path.join(__dirname, '..', '..', '..', 'src', 'webviews', 'problem-detail', name),
    path.join(__dirname, '..', '..', 'webviews', 'problem-detail', name),
  ];
  for (const p of candidates) {
    try {
      return await fs.readFile(p, 'utf8');
    } catch {
      /* try next */
    }
  }
  // Surface failure to the caller; we re-throw a clean Error.
  throw new Error(`Missing webview asset: ${escapeHtml(name)}`);
}

// Silence "unused" warning for imports used implicitly by tests.
export type { ProblemDetail, Problem };
