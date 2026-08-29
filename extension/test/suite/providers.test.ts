/**
 * providers.test.ts — verifies TreeProviders return sensible nodes.
 *
 * We bypass the network by injecting a populated ContestCache.
 */

import * as assert from 'assert';
import { ContestCache } from '../../src/services/ContestCache';
import { ProblemTreeProvider } from '../../src/providers/ProblemTreeProvider';
import { ContestTreeProvider } from '../../src/providers/ContestTreeProvider';
import { SubmissionCodeLensProvider } from '../../src/providers/SubmissionCodeLensProvider';
import type { ProblemAPI } from '../../src/api/problems';
import type { ContestAPI } from '../../src/api/contests';
import type { AuthService } from '../../src/services/AuthService';
import type { NotificationService } from '../../src/services/NotificationService';
import type { OutputChannelService } from '../../src/services/OutputChannelService';
import type { Contest, Problem } from '../../src/api/types';

function problemsFixture(): Problem[] {
  return [
    makeProblem('two-sum', 'Two Sum', 'easy'),
    makeProblem('three-sum', '3Sum', 'medium'),
    makeProblem('n-queens', 'N-Queens', 'hard'),
  ];
}

function contestsFixture(): Contest[] {
  return [
    makeContest('weekly-101', 'Weekly 101', 'active'),
    makeContest('biweekly-7', 'Biweekly 7', 'upcoming'),
    makeContest('icpc-mock', 'ICPC Mock', 'past'),
  ];
}

function makeProblem(slug: string, title: string, difficulty: Problem['difficulty']): Problem {
  return {
    id: `id-${slug}`,
    slug,
    title,
    difficulty,
    tags: [],
    acceptance: 0.5,
    solved_count: 100,
    attempts: 200,
    created_at: '2025-01-01T00:00:00Z',
  };
}

function makeContest(slug: string, title: string, status: Contest['status']): Contest {
  return {
    id: `id-${slug}`,
    slug,
    title,
    description: '',
    start_time: '2025-01-01T00:00:00Z',
    end_time: '2025-02-01T00:00:00Z',
    participant_count: 10,
    problem_count: 4,
    status,
  };
}

suite('TreeProviders', () => {
  test('ProblemTreeProvider groups by difficulty', async () => {
    const cache = new ContestCache();
    cache.setProblems(problemsFixture());
    const provider = new ProblemTreeProvider(
      stubAuth(),
      cache,
      {} as ProblemAPI,
      stubNotifications(),
      stubOutput(),
    );
    const roots = await provider.getChildren();
    const labels = roots.map((n) => (n.kind === 'difficulty' ? n.difficulty : (n as { problem: Problem }).problem.slug));
    assert.deepStrictEqual(labels.sort(), ['easy', 'hard', 'medium']);

    const easyChildren = await provider.getChildren({ kind: 'difficulty', difficulty: 'easy' });
    assert.strictEqual(easyChildren.length, 1);
    assert.strictEqual((easyChildren[0] as { problem: Problem }).problem.slug, 'two-sum');
  });

  test('ContestTreeProvider groups by status', async () => {
    const cache = new ContestCache();
    cache.setContests(contestsFixture());
    const provider = new ContestTreeProvider(
      stubAuth(),
      cache,
      {} as ContestAPI,
      stubNotifications(),
      stubOutput(),
    );
    const roots = await provider.getChildren();
    const statuses = roots.map((n) => (n.kind === 'status' ? n.status : 'unknown'));
    assert.deepStrictEqual(statuses.sort(), ['active', 'past', 'upcoming']);

    const active = await provider.getChildren({ kind: 'status', status: 'active' });
    assert.strictEqual(active.length, 1);
    assert.strictEqual((active[0] as { contest: Contest }).contest.slug, 'weekly-101');
  });

  test('ContestCache.getOrLoad dedupes concurrent loads', async () => {
    const cache = new ContestCache();
    let calls = 0;
    const loader = async () => {
      calls++;
      await new Promise((r) => setTimeout(r, 5));
      return problemsFixture();
    };
    const [a, b, c] = await Promise.all([
      cache.getOrLoad<readonly Problem[]>('problems', loader),
      cache.getOrLoad<readonly Problem[]>('problems', loader),
      cache.getOrLoad<readonly Problem[]>('problems', loader),
    ]);
    assert.strictEqual(calls, 1, 'loader should only run once');
    assert.strictEqual(a, b);
    assert.strictEqual(b, c);
  });

  test('SubmissionCodeLensProvider emits two lenses on a python starter', async () => {
    const provider = new SubmissionCodeLensProvider();
    const document = {
      getText: () => 'class Solution:\n    def solve(self, nums): pass\n',
      fileName: '/workspace/.algobattle/two-sum/starter.py',
      positionAt: (offset: number) => {
        const text = 'class Solution:\n    def solve(self, nums): pass\n';
        const before = text.slice(0, offset);
        const lines = before.split('\n');
        return { line: lines.length - 1, character: lines[lines.length - 1]!.length };
      },
      languageId: 'python',
    } as unknown as import('vscode').TextDocument;
    const lenses = provider.provideCodeLenses(document);
    assert.strictEqual(lenses.length, 2);
    assert.strictEqual((lenses[0]!.command as { command: string }).command, 'algobattle.runTests');
    assert.strictEqual((lenses[1]!.command as { command: string }).command, 'algobattle.submit');
  });

  test('SubmissionCodeLensProvider skips files outside .algobattle/', () => {
    const provider = new SubmissionCodeLensProvider();
    const document = {
      getText: () => 'class Solution:\n    pass\n',
      fileName: '/workspace/elsewhere/foo.py',
      positionAt: () => ({ line: 0, character: 0 }),
      languageId: 'python',
    } as unknown as import('vscode').TextDocument;
    const lenses = provider.provideCodeLenses(document);
    assert.strictEqual(lenses.length, 0);
  });
});

function stubAuth(): AuthService {
  return {
    snapshot: () => ({ authenticated: false, user: null }),
    onAuthChanged: new (require('events').EventEmitter)().event,
  } as unknown as AuthService;
}

function stubNotifications(): NotificationService {
  return {} as NotificationService;
}

function stubOutput(): OutputChannelService {
  return {
    info: () => undefined,
    warn: () => undefined,
    error: () => undefined,
    debug: () => undefined,
    appendLine: () => undefined,
  } as unknown as OutputChannelService;
}
