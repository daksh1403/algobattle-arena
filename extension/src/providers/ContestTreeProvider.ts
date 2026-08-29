/**
 * ContestTreeProvider — TreeView grouped by status (Active / Upcoming / Past).
 */

import * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { ContestCache } from '../services/ContestCache';
import type { NotificationService } from '../services/NotificationService';
import type { OutputChannelService } from '../services/OutputChannelService';
import type { ContestAPI } from '../api/contests';
import type { Contest } from '../api/types';

type Status = Contest['status'];
type Node = StatusNode | ContestNode;

interface StatusNode {
  readonly kind: 'status';
  readonly status: Status;
}

interface ContestNode {
  readonly kind: 'contest';
  readonly contest: Contest;
}

export class ContestTreeProvider implements vscode.TreeDataProvider<Node> {
  private readonly emitter = new vscode.EventEmitter<Node | undefined>();
  readonly onDidChangeTreeData = this.emitter.event;
  private contests: readonly Contest[] = [];
  private loading = false;

  constructor(
    private readonly auth: AuthService,
    private readonly cache: ContestCache,
    private readonly contestsApi: ContestAPI,
    private readonly notifications: NotificationService,
    private readonly output: OutputChannelService,
  ) {
    cache.onDidChange((key) => {
      if (key === 'contests') {
        this.contests = this.cache.getContests() ?? this.contests;
        this.emitter.fire(undefined);
      }
    });
  }

  refresh(): void {
    this.contests = this.cache.getContests() ?? [];
    this.emitter.fire(undefined);
    void this.loadInBackground();
  }

  getTreeItem(element: Node): vscode.TreeItem {
    if (element.kind === 'status') {
      const item = new vscode.TreeItem(
        labelForStatus(element.status),
        vscode.TreeItemCollapsibleState.Collapsed,
      );
      item.contextValue = `status.${element.status}`;
      item.iconPath = new vscode.ThemeIcon(iconForStatus(element.status));
      return item;
    }
    const c = element.contest;
    const item = new vscode.TreeItem(c.title, vscode.TreeItemCollapsibleState.None);
    item.description = c.slug;
    item.tooltip = `${c.title}\n${c.problem_count} problems · ${c.participant_count} participants`;
    item.contextValue = 'contest';
    item.iconPath = new vscode.ThemeIcon(iconForStatus(c.status));
    item.command = {
      command: 'algobattle.showLeaderboard',
      title: 'Open leaderboard',
      arguments: [c.id],
    };
    return item;
  }

  async getChildren(element?: Node): Promise<Node[]> {
    if (!element) {
      if (this.loading && this.contests.length === 0) return [loadingNode()];
      const active = this.contests.some((c) => c.status === 'active');
      const upcoming = this.contests.some((c) => c.status === 'upcoming');
      const past = this.contests.some((c) => c.status === 'past');
      const out: Node[] = [];
      if (active) out.push({ kind: 'status', status: 'active' });
      if (upcoming) out.push({ kind: 'status', status: 'upcoming' });
      if (past) out.push({ kind: 'status', status: 'past' });
      return out.length > 0 ? out : [emptyNode()];
    }
    if (element.kind === 'status') {
      return this.contests
        .filter((c) => c.status === element.status)
        .sort((a, b) => a.title.localeCompare(b.title))
        .map<Node>((c) => ({ kind: 'contest', contest: c }));
    }
    return [];
  }

  private async loadInBackground(): Promise<void> {
    if (this.loading) return;
    this.loading = true;
    try {
      const list = await this.cache.getOrLoad<readonly Contest[]>('contests', () =>
        this.contestsApi.listAll(),
      );
      this.contests = list;
      this.emitter.fire(undefined);
    } catch (err) {
      this.output.warn('Failed to load contests', { error: String(err) });
    } finally {
      this.loading = false;
    }
  }
}

function labelForStatus(s: Status): string {
  switch (s) {
    case 'active':
      return 'Active';
    case 'upcoming':
      return 'Upcoming';
    case 'past':
      return 'Past';
  }
}

function iconForStatus(s: Status): string {
  switch (s) {
    case 'active':
      return 'pulse';
    case 'upcoming':
      return 'clock';
    case 'past':
      return 'archive';
  }
}

function loadingNode(): Node {
  return { kind: 'contest', contest: makeFakeLoading() };
}
function emptyNode(): Node {
  return { kind: 'contest', contest: makeFakeEmpty() };
}
function makeFakeLoading(): Contest {
  return {
    id: '__loading__',
    slug: '__loading__',
    title: 'Loading contests…',
    description: '',
    start_time: '',
    end_time: '',
    participant_count: 0,
    problem_count: 0,
    status: 'active',
  };
}
function makeFakeEmpty(): Contest {
  return {
    id: '__empty__',
    slug: '__empty__',
    title: 'No contests yet',
    description: '',
    start_time: '',
    end_time: '',
    participant_count: 0,
    problem_count: 0,
    status: 'past',
  };
}
