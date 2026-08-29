/**
 * problems.ts — typed wrappers around /problems/*.
 */

import { AlgobattleClient } from './client';
import { isProblem, isProblemArray } from './types';
import type { Difficulty, Paginated, Problem, ProblemDetail, Tag } from './types';

export interface ListProblemsParams {
  page?: number;
  pageSize?: number;
  search?: string;
  difficulty?: Difficulty | 'all';
  tag?: string;
  status?: 'solved' | 'attempted' | 'new' | 'all';
  sort?: 'newest' | 'oldest' | 'difficulty' | 'acceptance' | 'solved';
}

interface RawList {
  items: unknown;
  total: number;
  page: number;
  page_size: number;
}

export class ProblemAPI {
  constructor(private readonly client: AlgobattleClient) {}

  /** GET /problems — paginated list of problems. */
  async list(params: ListProblemsParams = {}): Promise<Paginated<Problem>> {
    const raw = await this.client.request<RawList>('/problems', {
      method: 'GET',
      query: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 50,
        search: params.search?.trim() || undefined,
        difficulty:
          params.difficulty && params.difficulty !== 'all' ? params.difficulty : undefined,
        tag: params.tag?.trim() || undefined,
        status: params.status && params.status !== 'all' ? params.status : undefined,
        sort: params.sort ?? 'newest',
      },
    });
    if (!raw || !Array.isArray(raw.items)) {
      return { items: [], total: 0, page: 1, page_size: 0 };
    }
    const items = raw.items.filter(isProblem);
    return {
      items,
      total: typeof raw.total === 'number' ? raw.total : items.length,
      page: typeof raw.page === 'number' ? raw.page : 1,
      page_size: typeof raw.page_size === 'number' ? raw.page_size : items.length,
    };
  }

  /** Convenience: load every problem (up to `cap` pages). */
  async listAll(maxPages: number = 5, pageSize: number = 50): Promise<Problem[]> {
    const out: Problem[] = [];
    for (let page = 1; page <= maxPages; page++) {
      const data = await this.list({ page, pageSize });
      out.push(...data.items);
      if (out.length >= data.total || data.items.length === 0) break;
    }
    return out;
  }

  /** GET /problems/:slug — full problem detail. */
  async get(slugOrId: string): Promise<ProblemDetail> {
    const raw = await this.client.request<ProblemDetail>(
      `/problems/${encodeURIComponent(slugOrId)}`,
      { method: 'GET' },
    );
    if (!isProblem(raw)) {
      throw new Error('Server returned an unexpected problem payload');
    }
    return raw as ProblemDetail;
  }

  /** GET /problems/tags — distinct tags. */
  async listTags(): Promise<Tag[]> {
    const raw = await this.client.request<unknown>('/problems/tags', { method: 'GET' });
    if (Array.isArray(raw)) {
      return raw
        .filter((x): x is Tag =>
          !!x && typeof x === 'object' && typeof (x as { id?: unknown }).id === 'string' && typeof (x as { name?: unknown }).name === 'string',
        )
        .map((x) => ({ id: (x as Tag).id, name: (x as Tag).name }));
    }
    return [];
  }
}

export { isProblemArray };
