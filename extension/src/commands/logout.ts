/**
 * logout.ts — clears JWT from SecretStorage and refreshes dependent views.
 */

import * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { ContestCache } from '../services/ContestCache';
import type { NotificationService } from '../services/NotificationService';
import type { ProblemTreeProvider } from '../providers/ProblemTreeProvider';
import type { ContestTreeProvider } from '../providers/ContestTreeProvider';

export async function logoutCommand(
  auth: AuthService,
  cache: ContestCache,
  notifications: NotificationService,
  problemTree: ProblemTreeProvider,
  contestTree: ContestTreeProvider,
): Promise<void> {
  await auth.load();
  if (!auth.snapshot().authenticated) {
    notifications.info('Already signed out');
    await vscode.commands.executeCommand('setContext', 'algobattle.authed', false);
    return;
  }
  await auth.logout();
  cache.invalidateAll();
  problemTree.refresh();
  contestTree.refresh();
  await vscode.commands.executeCommand('setContext', 'algobattle.authed', false);
  notifications.info('Signed out');
}
