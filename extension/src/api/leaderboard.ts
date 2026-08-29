/**
 * leaderboard.ts — typed wrappers around /contests/:id/leaderboard.
 *
 * Provides both a one-shot REST snapshot and a live WebSocket subscription.
 */

import { AlgobattleClient } from './client';
import { isLeaderboardEntry } from './types';
import type { LeaderboardEntry } from './types';

export interface LeaderboardSnapshot {
  readonly contestId: string;
  readonly entries: LeaderboardEntry[];
  readonly updatedAt: string;
}

export interface WSMessage<T = unknown> {
  readonly type: string;
  readonly topic?: string;
  readonly payload?: T;
  readonly message?: string;
}

export type LeaderboardListener = (entries: LeaderboardEntry[]) => void;

const LEADERBOARD_PATH = (id: string) => `/contests/${encodeURIComponent(id)}/leaderboard`;
const LEADERBOARD_WS_PATH = (id: string) => `/ws/contests/${encodeURIComponent(id)}/leaderboard`;

export class LeaderboardAPI {
  constructor(private readonly client: AlgobattleClient) {}

  /** GET /contests/:id/leaderboard — snapshot. */
  async get(contestId: string): Promise<LeaderboardEntry[]> {
    const raw = await this.client.request<unknown>(LEADERBOARD_PATH(contestId), { method: 'GET' });
    return asEntries(raw);
  }

  /**
   * Open a WebSocket subscribed to the contest's leaderboard topic.
   * The returned `unsubscribe` function cleans up resources.
   *
   * Uses the global `WebSocket` (available in Node 18+ and the Webview).
   * Pass an alternate factory in tests.
   */
  subscribe(
    contestId: string,
    listener: LeaderboardListener,
    options: {
      token?: string | null;
      socketFactory?: (url: string) => WebSocket;
      maxReconnectMs?: number;
      baseReconnectMs?: number;
    } = {},
  ): () => void {
    const base = this.client.buildWsUrl(LEADERBOARD_WS_PATH(contestId));
    const token = options.token ?? null;
    const url = token ? `${base}${base.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}` : base;

    const makeSocket = options.socketFactory ?? ((u: string) => new WebSocket(u));

    let ws: WebSocket | null = null;
    let reconnectAttempts = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = (): void => {
      if (closed) return;
      try {
        ws = makeSocket(url);
      } catch (err) {
        scheduleReconnect(err);
        return;
      }
      ws.addEventListener('open', () => {
        reconnectAttempts = 0;
      });
      ws.addEventListener('message', (ev) => {
        let msg: WSMessage;
        try {
          msg = JSON.parse(typeof ev.data === 'string' ? ev.data : '') as WSMessage;
        } catch {
          return;
        }
        if (msg.type === 'message' && msg.topic === 'leaderboard') {
          const entries = asEntries(msg.payload);
          listener(entries);
        }
      });
      ws.addEventListener('close', () => scheduleReconnect());
      ws.addEventListener('error', () => {
        try {
          ws?.close();
        } catch {
          /* ignore */
        }
      });
    };

    const scheduleReconnect = (_reason?: unknown): void => {
      if (closed) return;
      const base = options.baseReconnectMs ?? 500;
      const max = options.maxReconnectMs ?? 15_000;
      const expo = Math.min(max, base * Math.pow(2, reconnectAttempts++));
      const delay = Math.floor(Math.random() * expo);
      reconnectTimer = setTimeout(connect, delay);
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) {
        try {
          ws.close();
        } catch {
          /* ignore */
        }
      }
    };
  }
}

function asEntries(payload: unknown): LeaderboardEntry[] {
  let candidate: unknown = payload;
  if (candidate && typeof candidate === 'object' && 'entries' in (candidate as Record<string, unknown>)) {
    candidate = (candidate as { entries: unknown }).entries;
  }
  if (!Array.isArray(candidate)) return [];
  return candidate.filter(isLeaderboardEntry);
}
