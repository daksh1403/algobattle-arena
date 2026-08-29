/**
 * openProblem.ts — quickpick → fetch detail → scaffold into .algobattle/.
 */

import * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { ContestCache } from '../services/ContestCache';
import type { NotificationService } from '../services/NotificationService';
import type { ProblemAPI } from '../api/problems';
import type { Problem } from '../api/types';
import { pickProblem } from './pickProblem';
import {
  pathsFor,
  readSolution,
  scaffoldProblem,
} from '../util/problem-storage';
import { displayToApi } from '../util/languages';

export interface OpenProblemOptions {
  /** When provided, skip the QuickPick and use this problem directly. */
  problem?: Problem;
  /** Preferred language display id ('python3' | 'javascript' | 'cpp'). */
  language?: string;
}

export async function openProblemCommand(
  auth: AuthService,
  cache: ContestCache,
  problems: ProblemAPI,
  notifications: NotificationService,
  opts: OpenProblemOptions = {},
): Promise<vscode.Uri | undefined> {
  await auth.load();

  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    notifications.error('Open a folder in VS Code before opening a problem.');
    return undefined;
  }
  const folder = folders[0]!;

  // Resolve the problem (either directly or via QuickPick).
  let chosen: Problem | undefined = opts.problem;
  if (!chosen) {
    const all = await notifications.withProgress('Loading problems', async () => {
      return cache.getOrLoad<readonly Problem[]>('problems', () => problems.listAll());
    });
    chosen = await pickProblem(all, { title: 'Algobattle: Open Problem' });
  }
  if (!chosen) return undefined;

  // Make sure the cache has the latest detail.
  let detail;
  try {
    detail = await notifications.withProgress(`Loading ${chosen.title}`, async () =>
      problems.get(chosen!.slug),
    );
  } catch (err) {
    notifications.error(err instanceof Error ? err.message : String(err));
    return undefined;
  }

  // Scaffold (or reuse) the .algobattle/<slug>/starter.* file.
  let starter: vscode.Uri;
  try {
    const result = await scaffoldProblem(detail, folder, {
      preferred: opts.language ? displayToApi(opts.language) : undefined,
    });
    starter = result.starter;
    if (result.created) {
      notifications.info(`Created ${result.paths.dir.fsPath}`);
    }
  } catch (err) {
    notifications.error(err instanceof Error ? err.message : String(err));
    return undefined;
  }

  // Open the starter file in the editor and ensure it's not empty.
  const doc = await vscode.workspace.openTextDocument(starter);
  await vscode.window.showTextDocument(doc, { preview: false });
  if ((await readSolution(starter)).length === 0) {
    notifications.warn('The starter file is empty — paste your solution here.');
  }
  return starter;
}
