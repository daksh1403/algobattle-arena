/**
 * runTests.ts — execute the active editor's code against visible samples.
 */

import * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { NotificationService } from '../services/NotificationService';
import type { OutputChannelService } from '../services/OutputChannelService';
import type { SubmissionAPI } from '../api/submissions';
import type { ProblemAPI } from '../api/problems';
import { findAlgobattleRoot, slugFromAlgobattlePath } from '../util/problem-storage';
import { detectFromFilename, fromVscodeId, displayToApi } from '../util/languages';
import type { SupportedLanguage, Problem, ProblemDetail, TestCaseResult } from '../api/types';

export interface RunTestsResult {
  verdict: string;
  total: number;
  passed: number;
}

export async function runTestsCommand(
  auth: AuthService,
  problems: ProblemAPI,
  submissions: SubmissionAPI,
  notifications: NotificationService,
  output: OutputChannelService,
): Promise<RunTestsResult | undefined> {
  await auth.load();
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    notifications.error('Open a problem file first.');
    return undefined;
  }

  const slug = slugFromAlgobattlePath(editor.document.uri);
  if (!slug) {
    notifications.error('Run tests only works inside a .algobattle/<slug>/ file.');
    return undefined;
  }

  const lang = resolveLanguage(editor.document);
  if (!lang) {
    notifications.error(`Unsupported language: ${editor.document.languageId}`);
    return undefined;
  }

  let detail: ProblemDetail;
  try {
    detail = await notifications.withProgress(`Loading ${slug}`, async () => problems.get(slug));
  } catch (err) {
    notifications.error(err instanceof Error ? err.message : String(err));
    return undefined;
  }

  const code = editor.document.getText();
  if (!code.trim()) {
    notifications.error('Nothing to run — the editor is empty.');
    return undefined;
  }

  let result;
  try {
    result = await notifications.withProgress(
      'Running tests',
      async (report) => {
        report('Submitting to judge…');
        const res = await submissions.run({ problem_id: detail.id, language: lang.apiId, code });
        return res;
      },
    );
  } catch (err) {
    notifications.error(err instanceof Error ? err.message : String(err));
    return undefined;
  }

  const passed = result.results.filter((r) => r.verdict === 'accepted').length;
  const total = result.results.length;
  renderOutput(output, detail, result.results, result.compile_error);

  const summary = `${passed}/${total} sample${total === 1 ? '' : 's'} passed — ${result.verdict}`;
  if (result.verdict === 'accepted') {
    notifications.info(summary);
  } else {
    notifications.warn(summary);
  }

  return { verdict: result.verdict, total, passed };
}

function resolveLanguage(doc: vscode.TextDocument): ReturnType<typeof fromVscodeId> {
  const id = doc.languageId;
  if (id) {
    const lang = fromVscodeId(id);
    if (lang) return lang;
  }
  return detectFromFilename(doc.fileName);
}

function renderOutput(
  output: OutputChannelService,
  detail: ProblemDetail,
  results: TestCaseResult[],
  compileError: string | undefined,
): void {
  output.reveal(false);
  output.info(`Run results for ${detail.title}`);
  if (compileError) {
    output.warn(`Compile error: ${compileError}`);
  }
  results.forEach((r, idx) => {
    const head = `[#${idx + 1}] ${r.verdict}`;
    if (typeof r.runtime_ms === 'number') {
      output.appendLine(`${head} (${r.runtime_ms}ms)`);
    } else {
      output.appendLine(head);
    }
    if (r.input !== undefined) {
      output.appendLine('  input:');
      appendIndented(output, r.input);
    }
    if (r.expected_output !== undefined) {
      output.appendLine('  expected:');
      appendIndented(output, r.expected_output);
    }
    if (r.actual_output !== undefined) {
      output.appendLine('  actual:');
      appendIndented(output, r.actual_output);
    }
    if (r.message) {
      output.appendLine('  message:');
      appendIndented(output, r.message);
    }
  });
}

function appendIndented(output: OutputChannelService, text: string): void {
  for (const line of text.split(/\r?\n/)) {
    output.appendLine(`    ${line}`);
  }
}

export { findAlgobattleRoot };

// Re-export type used in callers
export type { SupportedLanguage, Problem };
