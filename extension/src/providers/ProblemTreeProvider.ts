/**
 * ProblemTreeProvider — TreeView with root nodes "Easy", "Medium", "Hard"
 * each containing problems fetched from the API (cached).
 *
 * Click → opens the problem in the editor via the `algobattle.openProblem` command.
 */

import * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { ContestCache } from '../services/ContestCache';
import type { NotificationService } from '../services/NotificationService';
import type { OutputChannelService } from '../services/OutputChannelService';
import type { ProblemAPI } from '../api/problems';
import type { Difficulty, Problem } from '../api/types';

type Node = DifficultyNode | ProblemNode;

interface DifficultyNode {
  readonly kind: 'difficulty';
  readonly difficulty: Difficulty;
}

interface ProblemNode {
  readonly kind: 'problem';
  readonly problem: Problem;
}

export class ProblemTreeProvider implements vscode.TreeDataProvider<Node> {
  private readonly emitter = new vscode.EventEmitter<Node | undefined>();
  readonly onDidChangeTreeData = this.emitter.event;
  private problems: readonly Problem[] = [];
  private loading = false;
  private unsubscribeAuth?: vscode.Disposable;

  constructor(
    private readonly auth: AuthService,
    private readonly cache: ContestCache,
    private readonly problemsApi: ProblemAPI,
    private readonly notifications: NotificationService,
    private readonly output: OutputChannelService,
  ) {
    // Listen for cache mutations; refresh on `problems` key.
    cache.onDidChange((key) => {
      if (key === 'problems') {
        this.problems = cache.getProblems() ?? this.problems;
        this.emitter.fire(undefined);
      }
    });
  }

  /** Wire up auth-aware behaviour; call once from `activate`. */
  bind(): void {
    if (this.unsubscribeAuth) return;
    this.unsubscribeAuth = this.auth.onAuthChanged(() => {
      // Whenever auth flips we clear the cache & refresh.
      this.cache.invalidateProblems();
      this.refresh();
    });
  }

  dispose(): void {
    this.unsubscribeAuth?.dispose();
    this.emitter.dispose();
  }

  refresh(): void {
    this.problems = this.cache.getProblems() ?? [];
    this.emitter.fire(undefined);
    void this.loadInBackground();
  }

  getTreeItem(element: Node): vscode.TreeItem {
    if (element.kind === 'difficulty') {
      const item = new vscode.TreeItem(
        labelForDifficulty(element.difficulty),
        vscode.TreeItemCollapsibleState.Collapsed,
      );
      item.contextValue = `difficulty.${element.difficulty}`;
      item.iconPath = new vscode.ThemeIcon(iconForDifficulty(element.difficulty));
      return item;
    }
    const p = element.problem;
    const item = new vscode.TreeItem(p.title, vscode.TreeItemCollapsibleState.None);
    item.description = p.slug;
    item.tooltip = `${p.title}\n${p.solved_count} solved · ${(p.acceptance * 100).toFixed(0)}% AC`;
    item.contextValue = 'problem';
    item.command = {
      command: 'algobattle.openProblem',
      title: 'Open problem',
      arguments: [p],
    };
    item.iconPath = new vscode.ThemeIcon(iconForDifficulty(p.difficulty));
    return item;
  }

  async getChildren(element?: Node): Promise<Node[]> {
    if (!element) {
      if (this.loading && this.problems.length === 0) return [loadingNode()];
      const sorted = [...this.problems];
      sorted.sort((a, b) => a.title.localeCompare(b.title));
      const hasEasy = sorted.some((p) => p.difficulty === 'easy');
      const hasMed = sorted.some((p) => p.difficulty === 'medium');
      const hasHard = sorted.some((p) => p.difficulty === 'hard');
      if (!hasEasy && !hasMed && !hasHard) return [emptyNode()];
      const out: Node[] = [];
      if (hasEasy) out.push({ kind: 'difficulty', difficulty: 'easy' });
      if (hasMed) out.push({ kind: 'difficulty', difficulty: 'medium' });
      if (hasHard) out.push({ kind: 'difficulty', difficulty: 'hard' });
      return out;
    }
    if (element.kind === 'difficulty') {
      return this.problems
        .filter((p) => p.difficulty === element.difficulty)
        .sort((a, b) => a.title.localeCompare(b.title))
        .map<Node>((p) => ({ kind: 'problem', problem: p }));
    }
    return [];
  }

  private async loadInBackground(): Promise<void> {
    if (this.loading) return;
    this.loading = true;
    try {
      const list = await this.cache.getOrLoad<readonly Problem[]>('problems', () =>
        this.problemsApi.listAll(),
      );
      this.problems = list;
      this.emitter.fire(undefined);
    } catch (err) {
      this.output.warn('Failed to load problems', { error: String(err) });
      if (this.problems.length === 0) this.emitter.fire(undefined);
    } finally {
      this.loading = false;
    }
  }
}

function labelForDifficulty(d: Difficulty): string {
  switch (d) {
    case 'easy':
      return 'Easy';
    case 'medium':
      return 'Medium';
    case 'hard':
      return 'Hard';
  }
}

function iconForDifficulty(d: Difficulty): string {
  switch (d) {
    case 'easy':
      return 'circle-filled';
    case 'medium':
      return 'circle-medium';
    case 'hard':
      return 'circle-large';
  }
}

function loadingNode(): Node {
  return { kind: 'problem', problem: makeFakeLoading() };
}

function emptyNode(): Node {
  return { kind: 'problem', problem: makeFakeEmpty() };
}

function makeFakeLoading(): Problem {
  return {
    id: '__loading__',
    slug: '__loading__',
    title: 'Loading problems…',
    difficulty: 'easy',
    tags: [],
    acceptance: 0,
    solved_count: 0,
    attempts: 0,
    created_at: '',
  };
}

function makeFakeEmpty(): Problem {
  return {
    id: '__empty__',
    slug: '__empty__',
    title: 'No problems yet',
    difficulty: 'easy',
    tags: [],
    acceptance: 0,
    solved_count: 0,
    attempts: 0,
    created_at: '',
  };
}
