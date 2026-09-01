/**
 * submissions.ts — typed wrappers around /submissions/*.
 */

import { AlgobattleClient } from './client';
import type { Submission, SupportedLanguage, TestCaseResult, Verdict } from './types';

export interface RunRequest {
  problem_id: string;
  language: SupportedLanguage;
  code: string;
  /** Override for the contest context; defaults to null (practice mode). */
  contest_id?: string | null;
}

export interface RunResponse {
  results: TestCaseResult[];
  verdict: Verdict;
  runtime_ms?: number;
  memory_kb?: number;
  compile_error?: string;
}

export interface SubmitRequest extends RunRequest {}

interface RawSubmission {
  id: unknown;
  problem_id: unknown;
  language: unknown;
  code: unknown;
  verdict: unknown;
  results: unknown;
  submitted_at: unknown;
  user?: unknown;
  contest_id?: unknown;
  runtime_ms?: unknown;
  memory_kb?: unknown;
}

const VERDICTS: readonly Verdict[] = [
  'pending',
  'running',
  'accepted',
  'wrong_answer',
  'time_limit',
  'memory_limit',
  'runtime_error',
  'compile_error',
  'judging_error',
];

function isVerdict(v: unknown): v is Verdict {
  return typeof v === 'string' && (VERDICTS as readonly string[]).includes(v);
}

function coerceResults(input: unknown): TestCaseResult[] {
  if (!Array.isArray(input)) return [];
  const out: TestCaseResult[] = [];
  for (const raw of input) {
    if (!raw || typeof raw !== 'object') continue;
    const r = raw as Record<string, unknown>;
    const verdict: Verdict = isVerdict(r.verdict) ? r.verdict : 'judging_error';
    out.push({
      index: typeof r.index === 'number' ? r.index : out.length,
      verdict,
      runtime_ms: typeof r.runtime_ms === 'number' ? r.runtime_ms : undefined,
      memory_kb: typeof r.memory_kb === 'number' ? r.memory_kb : undefined,
      input: typeof r.input === 'string' ? r.input : undefined,
      expected_output: typeof r.expected_output === 'string' ? r.expected_output : undefined,
      actual_output: typeof r.actual_output === 'string' ? r.actual_output : undefined,
      message: typeof r.message === 'string' ? r.message : undefined,
      hidden: typeof r.hidden === 'boolean' ? r.hidden : undefined,
    });
  }
  return out;
}

function coerceUser(input: unknown): Submission['user'] {
  if (!input || typeof input !== 'object') return { id: 0, username: 'unknown' };
  const u = input as Record<string, unknown>;
  return {
    id: typeof u.id === 'string' || typeof u.id === 'number' ? Number(u.id) : 0,
    username: typeof u.username === 'string' ? u.username : 'unknown',
  };
}

export function asSubmission(raw: unknown): Submission {
  if (!raw || typeof raw !== 'object') {
    throw new Error('Server returned an invalid submission payload');
  }
  const r = raw as RawSubmission;
  if (typeof r.id !== 'string') throw new Error('Missing submission id');
  if (typeof r.problem_id !== 'string') throw new Error('Missing problem_id');
  if (typeof r.code !== 'string') throw new Error('Missing code');
  if (typeof r.submitted_at !== 'string') throw new Error('Missing submitted_at');
  if (!isVerdict(r.verdict)) throw new Error('Missing verdict');

  return {
    id: r.id,
    problem_id: r.problem_id,
    contest_id: typeof r.contest_id === 'string' ? r.contest_id : null,
    user: coerceUser(r.user),
    language: (typeof r.language === 'string' && (r.language === 'python' || r.language === 'javascript' || r.language === 'cpp'))
      ? (r.language as SupportedLanguage)
      : 'python',
    code: r.code,
    verdict: r.verdict,
    runtime_ms: typeof r.runtime_ms === 'number' ? r.runtime_ms : undefined,
    memory_kb: typeof r.memory_kb === 'number' ? r.memory_kb : undefined,
    results: coerceResults(r.results),
    submitted_at: r.submitted_at,
  };
}

export class SubmissionAPI {
  constructor(private readonly client: AlgobattleClient) {}

  /** POST /submissions/run — run the code against sample test cases. */
  async run(req: RunRequest): Promise<RunResponse> {
    const raw = await this.client.request<RunResponse>('/submissions/run', {
      method: 'POST',
      body: req,
      silent: true,
    });
    return {
      results: coerceResults(raw?.results),
      verdict: isVerdict(raw?.verdict) ? raw.verdict : 'pending',
      runtime_ms: typeof raw?.runtime_ms === 'number' ? raw.runtime_ms : undefined,
      memory_kb: typeof raw?.memory_kb === 'number' ? raw.memory_kb : undefined,
      compile_error: typeof raw?.compile_error === 'string' ? raw.compile_error : undefined,
    };
  }

  /** POST /submissions — submit for full judging. */
  async submit(req: SubmitRequest): Promise<Submission> {
    const raw = await this.client.request<Submission>('/submissions', {
      method: 'POST',
      body: req,
      silent: true,
    });
    return asSubmission(raw);
  }

  /** GET /submissions/:id — poll a previously created submission. */
  async get(id: string): Promise<Submission> {
    const raw = await this.client.request<Submission>(
      `/submissions/${encodeURIComponent(id)}`,
      { method: 'GET', silent: true },
    );
    return asSubmission(raw);
  }

  /**
   * Poll `get(id)` until the verdict is terminal. Returns the latest known
   * submission. Honours the caller's AbortSignal.
   */
  async pollUntilDone(
    id: string,
    options: { intervalMs?: number; timeoutMs?: number; signal?: AbortSignal } = {},
  ): Promise<Submission> {
    const interval = options.intervalMs ?? 1000;
    const timeout = options.timeoutMs ?? 60_000;
    const deadline = Date.now() + timeout;

    for (;;) {
      const sub = await this.get(id);
      if (isTerminal(sub.verdict)) return sub;
      if (Date.now() > deadline) {
        throw new Error(`Polling for submission ${id} timed out`);
      }
      if (options.signal?.aborted) {
        throw new Error('Polling cancelled');
      }
      await delay(interval, options.signal);
    }
  }
}

function isTerminal(v: Verdict): boolean {
  return v !== 'pending' && v !== 'running';
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new Error('Cancelled'));
      return;
    }
    const handle = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(handle);
        reject(new Error('Cancelled'));
      },
      { once: true },
    );
  });
}
