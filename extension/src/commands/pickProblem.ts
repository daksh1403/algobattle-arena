/**
 * pickProblem.ts — quickpick a problem (from cache) and return it.
 */

import * as vscode from 'vscode';
import type { Problem } from '../api/types';

interface ProblemQuickPickItem extends vscode.QuickPickItem {
  problem: Problem;
}

const DIFFICULTY_ICONS: Record<Problem['difficulty'], string> = {
  easy: '$(circle-filled)',
  medium: '$(circle-medium)',
  hard: '$(circle-large)',
};

export async function pickProblem(
  problems: readonly Problem[],
  options: { placeholder?: string; title?: string } = {},
): Promise<Problem | undefined> {
  if (problems.length === 0) {
    void vscode.window.showInformationMessage('No problems available yet.');
    return undefined;
  }

  const items: ProblemQuickPickItem[] = problems.map((p) => ({
    problem: p,
    label: `${DIFFICULTY_ICONS[p.difficulty]} ${p.title}`,
    description: p.slug,
    detail: `${p.solved_count}/${p.attempts} solved · ${(p.acceptance * 100).toFixed(0)}% acceptance`,
  }));

  const selection = await vscode.window.showQuickPick<ProblemQuickPickItem>(items, {
    title: options.title ?? 'Algobattle: Pick a Problem',
    placeHolder: options.placeholder ?? 'Search for a problem…',
    matchOnDescription: true,
    matchOnDetail: true,
    ignoreFocusOut: true,
  });

  return selection?.problem;
}
