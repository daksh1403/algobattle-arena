/**
 * browseProblems.ts — opens the problem-browser WebView panel.
 */

import type * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { ContestCache } from '../services/ContestCache';
import type { NotificationService } from '../services/NotificationService';
import type { ProblemAPI } from '../api/problems';
import { ProblemDetailPanel } from '../webviews/problem-detail/panel';

export async function browseProblemsCommand(
  context: vscode.ExtensionContext,
  auth: AuthService,
  cache: ContestCache,
  problems: ProblemAPI,
  notifications: NotificationService,
): Promise<void> {
  await auth.load();
  ProblemDetailPanel.revealOrCreate({
    context,
    auth,
    cache,
    problems,
    notifications,
  });
}
