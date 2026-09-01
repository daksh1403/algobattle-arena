/**
 * showLeaderboard.ts — opens the live leaderboard WebView for the chosen contest.
 */

import * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { ContestCache } from '../services/ContestCache';
import type { NotificationService } from '../services/NotificationService';
import type { LeaderboardAPI } from '../api/leaderboard';
import type { ContestAPI } from '../api/contests';
import type { Contest } from '../api/types';
import { LeaderboardPanel } from '../webviews/leaderboard/panel';

export async function showLeaderboardCommand(
  context: vscode.ExtensionContext,
  auth: AuthService,
  cache: ContestCache,
  leaderboards: LeaderboardAPI,
  contests: ContestAPI,
  notifications: NotificationService,
  preselectedContestId?: string,
): Promise<void> {
  await auth.load();
  if (!auth.snapshot().authenticated) {
    notifications.warn('Sign in to view the leaderboard.', { fields: { hint: 'login-required' } });
    return;
  }

  let contest: Contest | undefined;
  if (preselectedContestId) {
    contest = await resolveById(preselectedContestId, contests, cache);
  }

  if (!contest) {
    const list = await notifications.withProgress('Loading contests', async () =>
      cache.getOrLoad<readonly Contest[]>('contests', () => contests.listAll()),
    );
    if (list.length === 0) {
      notifications.warn('No contests are available right now.');
      return;
    }
    const picked = await vscode.window.showQuickPick(
      list.map((c) => ({
        label: `$(${iconForStatus(c.status)}) ${c.title}`,
        description: c.slug,
        detail: `${c.participant_count} participants · ${c.problem_count} problems`,
        contest: c,
      })),
      {
        title: 'Algobattle: Choose a Contest',
        matchOnDescription: true,
        placeHolder: 'Pick a contest to view its leaderboard',
        ignoreFocusOut: true,
      },
    );
    if (!picked) return;
    contest = picked.contest;
  }

  LeaderboardPanel.revealOrCreate({
    context,
    auth,
    cache,
    leaderboards,
    notifications,
    contest,
  });
}

async function resolveById(
  id: string,
  contests: ContestAPI,
  cache: ContestCache,
): Promise<Contest | undefined> {
  const numericId = Number(id);
  const cached = cache.getContests()?.find((c) => c.id === numericId);
  if (cached) return cached;
  const list = await contests.listAll();
  cache.setContests(list);
  return list.find((c) => c.id === numericId);
}

function iconForStatus(s: Contest['status']): string {
  switch (s) {
    case 'active':
      return 'pulse';
    case 'upcoming':
      return 'clock';
    case 'past':
      return 'archive';
    default:
      return 'question';
  }
}

// Re-export ContestAPI for the importer convenience
export type { ContestAPI };
