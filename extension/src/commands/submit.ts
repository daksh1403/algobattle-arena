/**
 * submit.ts — submit the active editor's solution for full judging.
 */

import * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { NotificationService } from '../services/NotificationService';
import type { OutputChannelService } from '../services/OutputChannelService';
import type { SubmissionAPI } from '../api/submissions';
import type { ProblemAPI } from '../api/problems';
import { slugFromAlgobattlePath } from '../util/problem-storage';
import { fromVscodeId, detectFromFilename } from '../util/languages';
import type { Submission } from '../api/types';

export interface SubmitOptions {
  /** Optional contest id — when provided, the submission counts for that contest. */
  contestId?: string;
}

export async function submitCommand(
  auth: AuthService,
  problems: ProblemAPI,
  submissions: SubmissionAPI,
  notifications: NotificationService,
  output: OutputChannelService,
  context: vscode.ExtensionContext,
  opts: SubmitOptions = {},
): Promise<Submission | undefined> {
  await auth.load();
  if (!auth.snapshot().authenticated) {
    notifications.error('Sign in before submitting a solution.');
    return;
  }

  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    notifications.error('Open a problem file first.');
    return undefined;
  }

  const slug = slugFromAlgobattlePath(editor.document.uri);
  if (!slug) {
    notifications.error('Submit only works inside a .algobattle/<slug>/ file.');
    return undefined;
  }

  const langId = editor.document.languageId;
  const lang = (langId && fromVscodeId(langId)) || detectFromFilename(editor.document.fileName);
  if (!lang) {
    notifications.error(`Unsupported language: ${editor.document.languageId}`);
    return undefined;
  }

  const code = editor.document.getText();
  if (!code.trim()) {
    notifications.error('Cannot submit an empty file.');
    return undefined;
  }

  let detail;
  try {
    detail = await notifications.withProgress(`Loading ${slug}`, async () => problems.get(slug));
  } catch (err) {
    notifications.error(err instanceof Error ? err.message : String(err));
    return undefined;
  }

  let submission: Submission;
  try {
    submission = await notifications.withProgress('Submitting to judge', async (report) => {
      report('Sending submission…');
      const sub = await submissions.submit({
        problem_id: detail.id,
        language: lang.apiId,
        code,
        contest_id: opts.contestId ?? null,
      });
      report('Waiting for verdict…');
      return submissions.pollUntilDone(sub.id, {
        intervalMs: 1500,
        timeoutMs: 5 * 60_000,
      });
    });
  } catch (err) {
    notifications.error(err instanceof Error ? err.message : String(err));
    return undefined;
  }

  // Persist last submission for re-query.
  await context.workspaceState.update(`algobattle.lastSubmission.${slug}`, submission.id);

  renderSubmissionOutput(output, detail.title, submission);

  const summary = `Submission ${submission.verdict.toUpperCase()}`;
  if (submission.verdict === 'accepted') {
    notifications.info(summary, {
      fields: { id: submission.id, problem: detail.slug, runtime_ms: submission.runtime_ms },
    });
  } else if (submission.verdict === 'pending' || submission.verdict === 'running') {
    notifications.warn(`${summary} — judging still in progress`);
  } else {
    notifications.error(summary, {
      fields: { id: submission.id, problem: detail.slug },
    });
  }
  return submission;
}

function renderSubmissionOutput(output: OutputChannelService, title: string, sub: Submission): void {
  output.reveal(false);
  output.info(`Submission ${sub.id} for ${title}: ${sub.verdict.toUpperCase()}`);
  if (typeof sub.runtime_ms === 'number') {
    output.appendLine(`  runtime: ${sub.runtime_ms}ms`);
  }
  if (typeof sub.memory_kb === 'number') {
    output.appendLine(`  memory: ${sub.memory_kb}KB`);
  }
  output.appendLine('  results:');
  for (const r of sub.results) {
    output.appendLine(
      `    [${r.index + 1}] ${r.verdict}` +
        (typeof r.runtime_ms === 'number' ? ` (${r.runtime_ms}ms)` : '') +
        (r.hidden ? ' [hidden]' : ''),
    );
    if (r.message) {
      for (const line of r.message.split(/\r?\n/)) output.appendLine(`      ${line}`);
    }
  }
}
