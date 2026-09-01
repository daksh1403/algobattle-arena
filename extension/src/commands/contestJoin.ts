/**
 * contestJoin.ts — quickpick an active contest and join it.
 */

import * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { ContestCache } from '../services/ContestCache';
import type { NotificationService } from '../services/NotificationService';
import type { ContestAPI } from '../api/contests';
import type { Contest } from '../api/types';

export async function contestJoinCommand(
  auth: AuthService,
  cache: ContestCache,
  contests: ContestAPI,
  notifications: NotificationService,
): Promise<Contest | undefined> {
  await auth.load();
  if (!auth.snapshot().authenticated) {
    notifications.warn('Sign in to join a contest.', { fields: { hint: 'login-required' } });
    return undefined;
  }

  const list = await notifications.withProgress('Loading contests', async () =>
    cache.getOrLoad<readonly Contest[]>('contests', () => contests.listAll()),
  );

  if (list.length === 0) {
    notifications.warn('No contests available right now.');
    return undefined;
  }

  // Prefer active contests in the picker.
  const active = list.filter((c) => c.status === 'active');
  const ordered = active.length > 0 ? active : list;

  const picked = await vscode.window.showQuickPick(
    ordered.map((c) => ({
      label: `$(${iconForStatus(c.status)}) ${c.title}`,
      description: `${c.problem_count} problems · ${c.participant_count} participants`,
      detail: c.description,
      contest: c,
    })),
    {
      title: 'Algobattle: Join Contest',
      placeHolder: 'Pick a contest',
      matchOnDescription: true,
      ignoreFocusOut: true,
    },
  );
  if (!picked) return undefined;

  try {
    await notifications.withProgress(`Joining ${picked.contest.title}`, async () => {
      await contests.join(String(picked.contest.id));
    });
    notifications.info(`Joined ${picked.contest.title}`);
    return picked.contest;
  } catch (err) {
    notifications.error(err instanceof Error ? err.message : String(err));
    return undefined;
  }
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
