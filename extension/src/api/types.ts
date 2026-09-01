/**
 * types.ts — shared API types matching the Algobattle backend.
 *
 * These mirror the Pydantic models exposed by the backend and the
 * `frontend/src/lib/types.ts` reference. Keep in sync.
 */

export type Difficulty = 'easy' | 'medium' | 'hard';

export type SupportedLanguage = 'python' | 'javascript' | 'cpp';

export interface User {
  id: number;
  username: string;
  email: string;
  rating: number;
  avatar_url?: string | null;
  is_admin?: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  user: User;
}

export interface Tag {
  id: string;
  name: string;
}

export interface Problem {
  id: string;
  slug: string;
  title: string;
  difficulty: Difficulty;
  tags: Tag[];
  /** Acceptance rate 0..1 */
  acceptance: number;
  /** Number of accepted submissions */
  solved_count: number;
  /** Total attempts */
  attempts: number;
  /** Per-user status */
  status?: 'solved' | 'attempted' | 'new';
  created_at: string;
}

export interface SampleTestCase {
  id: string;
  input: string;
  expected_output: string;
  explanation?: string;
}

export interface ProblemDetail extends Problem {
  statement_md: string;
  input_format?: string;
  output_format?: string;
  constraints?: string;
  samples: SampleTestCase[];
  starter_code: Record<SupportedLanguage, string>;
  time_limit_ms: number;
  memory_limit_kb: number;
}

export interface Contest {
  id: number;
  slug: string;
  title: string;
  description: string;
  start_time: string;
  end_time: string;
  participant_count: number;
  problem_count: number;
  status: 'upcoming' | 'active' | 'past';
}

export interface ContestDetail extends Contest {
  problems: Pick<Problem, 'id' | 'slug' | 'title' | 'difficulty'>[];
  rules?: string;
}

export type Verdict =
  | 'pending'
  | 'running'
  | 'accepted'
  | 'wrong_answer'
  | 'time_limit'
  | 'memory_limit'
  | 'runtime_error'
  | 'compile_error'
  | 'judging_error';

export interface TestCaseResult {
  index: number;
  verdict: Verdict;
  runtime_ms?: number;
  memory_kb?: number;
  /** Visible only on samples. */
  input?: string;
  expected_output?: string;
  actual_output?: string;
  /** Error message for runtime/compile errors. */
  message?: string;
  hidden?: boolean;
}

export interface Submission {
  id: string;
  problem_id: string;
  contest_id?: string | null;
  user: Pick<User, 'id' | 'username'>;
  language: SupportedLanguage;
  code: string;
  verdict: Verdict;
  runtime_ms?: number;
  memory_kb?: number;
  results: TestCaseResult[];
  submitted_at: string;
}

export interface LeaderboardEntry {
  user_id: string;
  username: string;
  rating: number;
  avatar_url?: string | null;
  score?: number;
  total_time?: number;
  solved_count?: number;
  penalty?: number;
  rank?: number;
  rank_delta?: number;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------------
// Type guards (used by the client to safely parse 401/204/no-content responses).
// ---------------------------------------------------------------------------------

export function isUser(value: unknown): value is User {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  return (
    (typeof v.id === 'string' || typeof v.id === 'number') &&
    typeof v.username === 'string' &&
    typeof v.email === 'string'
  );
}

export function isAuthResponse(value: unknown): value is AuthResponse {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  return typeof v.access_token === 'string' && isUser(v.user);
}

export function isProblem(value: unknown): value is Problem {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.id === 'string' &&
    typeof v.slug === 'string' &&
    typeof v.title === 'string' &&
    (v.difficulty === 'easy' || v.difficulty === 'medium' || v.difficulty === 'hard')
  );
}

export function isProblemArray(value: unknown): value is Problem[] {
  return Array.isArray(value) && value.every(isProblem);
}

export function isContest(value: unknown): value is Contest {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  // Accept both new format (title/slug) and old format (name/no slug)
  const hasTitle = typeof v.title === 'string';
  const hasName = typeof v.name === 'string';
  const title = hasTitle ? v.title : (hasName ? v.name : undefined);
  const hasSlug = typeof v.slug === 'string';
  const hasId = typeof v.id === 'string' || typeof v.id === 'number';
  const status = v.status ?? (typeof v.is_active === 'boolean' ? (v.is_active ? 'active' : 'past') : undefined);
  return (
    hasId &&
    title !== undefined &&
    (v.status === 'upcoming' || v.status === 'active' || v.status === 'past')
  );
}

export function isLeaderboardEntry(value: unknown): value is LeaderboardEntry {
  if (!value || typeof value !== 'object') return false;
  const v = value as Record<string, unknown>;
  return typeof v.user_id === 'string' && typeof v.username === 'string';
}
