/**
 * ContestCache — in-memory, time-bounded cache for problems & contests.
 *
 * Features:
 *  - 60-second TTL by default
 *  - Per-key invalidation (`invalidateProblems`, `invalidateContests`)
 *  - Stores the latest fetch promise so concurrent callers share work
 *  - Event emission via `onDidChange` so TreeProviders can refresh
 */

import { EventEmitter } from 'events';
import type { Contest, Problem } from '../api/types';

export interface CacheEntry<T> {
  readonly value: T;
  readonly fetchedAt: number;
}

export interface CacheListener {
  (key: 'problems' | 'contests' | 'leaderboard', value: unknown): void;
}

export const DEFAULT_TTL_MS = 60_000;

export class ContestCache {
  private readonly ttlMs: number;
  private readonly entries = new Map<string, CacheEntry<unknown>>();
  private readonly inFlight = new Map<string, Promise<unknown>>();
  private readonly emitter = new EventEmitter();

  constructor(ttlMs: number = DEFAULT_TTL_MS) {
    this.ttlMs = ttlMs;
  }

  /** Subscribe to cache mutations. Returns an unsubscribe function. */
  onDidChange(listener: CacheListener): () => void {
    this.emitter.on('change', listener);
    return () => this.emitter.off('change', listener);
  }

  /** True when the entry exists and is fresher than the TTL. */
  isFresh(key: string): boolean {
    const e = this.entries.get(key);
    if (!e) return false;
    return Date.now() - e.fetchedAt < this.ttlMs;
  }

  get<T>(key: string): T | undefined {
    const e = this.entries.get(key);
    if (!e) return undefined;
    if (Date.now() - e.fetchedAt >= this.ttlMs) return undefined;
    return e.value as T;
  }

  set<T>(key: string, value: T): void {
    this.entries.set(key, { value, fetchedAt: Date.now() });
    this.emitter.emit('change', key, value);
  }

  invalidate(key: string): void {
    if (this.entries.delete(key)) {
      this.emitter.emit('change', key, undefined);
    }
  }

  invalidateAll(): void {
    for (const k of Array.from(this.entries.keys())) this.invalidate(k);
  }

  /** Returns the cached value OR runs `loader` once and caches the result. */
  async getOrLoad<T>(key: string, loader: () => Promise<T>): Promise<T> {
    const cached = this.get<T>(key);
    if (cached !== undefined) return cached;

    const inFlight = this.inFlight.get(key);
    if (inFlight) return inFlight as Promise<T>;

    const promise = (async () => {
      try {
        const value = await loader();
        this.set(key, value);
        return value;
      } finally {
        this.inFlight.delete(key);
      }
    })();
    this.inFlight.set(key, promise);
    return promise;
  }

  // Typed convenience accessors ----------------------------------------------------

  setProblems(value: readonly Problem[]): void {
    this.set<readonly Problem[]>('problems', value);
  }

  getProblems(): readonly Problem[] | undefined {
    return this.get<readonly Problem[]>('problems');
  }

  invalidateProblems(): void {
    this.invalidate('problems');
  }

  setContests(value: readonly Contest[]): void {
    this.set<readonly Contest[]>('contests', value);
  }

  getContests(): readonly Contest[] | undefined {
    return this.get<readonly Contest[]>('contests');
  }

  invalidateContests(): void {
    this.invalidate('contests');
  }

  setLeaderboard(contestId: string, value: unknown): void {
    this.set(`leaderboard:${contestId}`, value);
    this.emitter.emit('change', 'leaderboard', { contestId, value });
  }

  getLeaderboard<T>(contestId: string): T | undefined {
    return this.get<T>(`leaderboard:${contestId}`);
  }
}
