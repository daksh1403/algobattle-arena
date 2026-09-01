/**
 * panel.ts — leaderboard WebView panel.
 *
 * Subscribes to the contest's live leaderboard via WebSocket. Initial snapshot
 * is fetched synchronously via REST, then updates stream in.
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import * as vscode from 'vscode';
import type { AuthService } from '../../services/AuthService';
import type { ContestCache } from '../../services/ContestCache';
import type { NotificationService } from '../../services/NotificationService';
import type { LeaderboardAPI } from '../../api/leaderboard';
import type { Contest, LeaderboardEntry } from '../../api/types';
import { renderWebviewHtml, escapeHtml } from '../shared';

interface RevealOptions {
  context: vscode.ExtensionContext;
  auth: AuthService;
  cache: ContestCache;
  leaderboards: LeaderboardAPI;
  notifications: NotificationService;
  contest: Contest;
}

let activePanel: LeaderboardPanel | undefined;

export class LeaderboardPanel {
  static revealOrCreate(opts: RevealOptions): LeaderboardPanel {
    if (activePanel) {
      activePanel.switchTo(opts.contest);
      activePanel.reveal();
      return activePanel;
    }
    const panel = new LeaderboardPanel(opts);
    activePanel = panel;
    return panel;
  }

  private readonly panel: vscode.WebviewPanel;
  private readonly disposables: vscode.Disposable[] = [];
  private current: Contest;
  private unsubscribe?: () => void;

  private constructor(private readonly opts: RevealOptions) {
    this.current = opts.contest;
    this.panel = vscode.window.createWebviewPanel(
      'algobattle.leaderboard',
      `Leaderboard · ${opts.contest.title}`,
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

    void this.bootstrap();
  }

  reveal(): void {
    this.panel.reveal(vscode.ViewColumn.Beside);
  }

  switchTo(contest: Contest): void {
    if (contest.id === this.current.id) return;
    this.current = contest;
    this.panel.title = `Leaderboard · ${contest.title}`;
    this.disposeSubscription();
    void this.bootstrap();
  }

  private async bootstrap(): Promise<void> {
    let entries: LeaderboardEntry[] = [];
    try {
      entries = await this.opts.leaderboards.get(String(this.current.id));
    } catch (err) {
      this.opts.notifications.warn(
        `Failed to load initial leaderboard: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
    this.panel.webview.html = await renderWebviewHtml({
      title: `Leaderboard · ${this.current.title}`,
      body: await readAsset('main.html'),
      styles: await readAsset('styles.css'),
      script: await readAsset('leaderboard-main.js'),
      initialState: { contest: { id: this.current.id, title: this.current.title }, entries },
    });
    this.panel.webview.postMessage({ type: 'status', status: 'reconnecting' });
    this.startStream();
  }

  private startStream(): void {
    this.disposeSubscription();
    const token = this.opts.auth.currentTokenSync();
    this.unsubscribe = this.opts.leaderboards.subscribe(String(this.current.id), (entries) => {
      this.panel.webview.postMessage({ type: 'update', entries });
      this.panel.webview.postMessage({ type: 'status', status: 'connected' });
    }, { token });
    // After 1s, if no update, mark as still connecting.
    setTimeout(() => {
      this.panel.webview.postMessage({ type: 'status', status: 'reconnecting' });
    }, 1000).unref?.();
  }

  private disposeSubscription(): void {
    if (this.unsubscribe) {
      try { this.unsubscribe(); } catch { /* ignore */ }
      this.unsubscribe = undefined;
    }
  }

  private onMessage(_msg: unknown): void {
    // Currently no host→extension messages from the leaderboard WebView.
  }

  private dispose(): void {
    this.disposeSubscription();
    while (this.disposables.length) {
      const d = this.disposables.pop();
      try { d?.dispose(); } catch { /* ignore */ }
    }
    activePanel = undefined;
  }
}

async function readAsset(name: string): Promise<string> {
  const candidates = [
    path.join(__dirname, '..', '..', '..', 'src', 'webviews', 'leaderboard', name),
    path.join(__dirname, '..', '..', 'webviews', 'leaderboard', name),
  ];
  for (const p of candidates) {
    try {
      return await fs.readFile(p, 'utf8');
    } catch {
      /* try next */
    }
  }
  throw new Error(`Missing leaderboard asset: ${escapeHtml(name)}`);
}
