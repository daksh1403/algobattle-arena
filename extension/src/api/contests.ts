/**
 * contests.ts — typed wrappers around /contests/*.
 */

import { AlgobattleClient } from './client';
import { isContest } from './types';
import type { Contest, ContestDetail } from './types';

interface RawList {
  items: unknown;
  total: number;
}

export class ContestAPI {
  constructor(private readonly client: AlgobattleClient) {}

  /** GET /contests — paginated list of contests. */
  async list(params: { page?: number; pageSize?: number } = {}): Promise<{ items: Contest[]; total: number }> {
    const raw = await this.client.request<RawList>('/contests', {
      method: 'GET',
      query: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 50,
      },
    });
    if (!raw || !Array.isArray(raw.items)) {
      return { items: [], total: 0 };
    }
    const items = raw.items.filter(isContest);
    return { items, total: typeof raw.total === 'number' ? raw.total : items.length };
  }

  async listAll(maxPages: number = 5): Promise<Contest[]> {
    const out: Contest[] = [];
    for (let page = 1; page <= maxPages; page++) {
      const data = await this.list({ page });
      out.push(...data.items);
      if (out.length >= data.total || data.items.length === 0) break;
    }
    return out;
  }

  /** GET /contests/:slug — full contest detail. */
  async get(slugOrId: string): Promise<ContestDetail> {
    const raw = await this.client.request<ContestDetail>(
      `/contests/${encodeURIComponent(slugOrId)}`,
      { method: 'GET' },
    );
    if (!isContest(raw)) throw new Error('Server returned an unexpected contest payload');
    return raw;
  }

  /** POST /contests/:id/join — opt the current user in. */
  async join(contestId: string): Promise<void> {
    await this.client.request(`/contests/${encodeURIComponent(contestId)}/join`, {
      method: 'POST',
    });
  }
}
