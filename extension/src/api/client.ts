/**
 * client.ts — `AlgobattleClient`: the single fetch wrapper used by the extension.
 *
 * Responsibilities:
 *  - Read `algobattle.apiUrl` from VS Code config (re-evaluated per call)
 *  - Attach `Authorization: Bearer <jwt>` when a token is present
 *  - JSON-encode request bodies and decode JSON responses
 *  - Surface failures as a typed `ApiError` with `status`, `detail`, `message`
 *  - Log every request/response cycle via the injected logger
 *
 * No `any`. No console.*. Always go through `AlgobattleClient`.
 */

import { ConfigService } from '../util/config';
import { Logger, formatError } from '../util/logger';

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  headers?: Record<string, string>;
  /** Skip Authorization header. Use for /auth/login and /auth/register. */
  skipAuth?: boolean;
  /** Override base URL — useful in tests. */
  baseUrl?: string;
  /** Abort signal forwarded to fetch. */
  signal?: AbortSignal;
  /** Skip logging; useful for the polling endpoint where noise is unhelpful. */
  silent?: boolean;
  /** Treat an empty body as success. */
  expectEmpty?: boolean;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  public readonly url: string;

  constructor(message: string, status: number, url: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.url = url;
    this.detail = detail;
  }
}

export type TokenProvider = () => string | null | Promise<string | null>;

export class AlgobattleClient {
  constructor(
    private readonly logger: Logger,
    private readonly config: ConfigService,
    private readonly tokenProvider: TokenProvider,
    private readonly fetchImpl: typeof fetch = fetch,
  ) {}

  /** GET helper that returns the typed body. */
  async get<T>(path: string, options: Omit<RequestOptions, 'method' | 'body'> = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: 'GET' });
  }

  async post<T>(path: string, body?: unknown, options: Omit<RequestOptions, 'method'> = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: 'POST', body });
  }

  async put<T>(path: string, body?: unknown, options: Omit<RequestOptions, 'method'> = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: 'PUT', body });
  }

  async patch<T>(path: string, body?: unknown, options: Omit<RequestOptions, 'method'> = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: 'PATCH', body });
  }

  async delete<T>(path: string, options: Omit<RequestOptions, 'method' | 'body'> = {}): Promise<T> {
    return this.request<T>(path, { ...options, method: 'DELETE' });
  }

  /** Core request implementation. */
  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const url = this.buildUrl(path, options.query, options.baseUrl);
    const method = options.method ?? 'GET';

    const headers: Record<string, string> = {
      Accept: 'application/json',
      ...(options.headers ?? {}),
    };

    let serializedBody: BodyInit | undefined;
    if (options.body !== undefined && options.body !== null) {
      if (options.body instanceof FormData) {
        serializedBody = options.body;
      } else if (typeof options.body === 'string') {
        serializedBody = options.body;
        if (!headers['Content-Type'] && !headers['content-type']) {
          headers['Content-Type'] = 'text/plain;charset=UTF-8';
        }
      } else if (options.body instanceof URLSearchParams) {
        serializedBody = options.body.toString();
        headers['Content-Type'] = 'application/x-www-form-urlencoded';
      } else {
        headers['Content-Type'] = headers['Content-Type'] ?? 'application/json';
        serializedBody = JSON.stringify(options.body);
      }
    }

    if (!options.skipAuth) {
      const token = await Promise.resolve(this.tokenProvider());
      if (token) headers['Authorization'] = `Bearer ${token}`;
    }

    if (!options.silent) {
      this.logger.debug('http:request', { method, url });
    }

    let response: Response;
    try {
      response = await this.fetchImpl(url, {
        method,
        headers,
        body: serializedBody,
        signal: options.signal ?? null,
      });
    } catch (err) {
      const wrapped = err instanceof Error ? err : new Error(String(err));
      this.logger.warn('http:network-error', { url, message: wrapped.message });
      throw new ApiError(wrapped.message || 'Network error', 0, url);
    }

    if (!response.ok) {
      throw await this.parseError(response, url);
    }

    if (response.status === 204 || options.expectEmpty) {
      return undefined as T;
    }

    const ct = response.headers.get('content-type') ?? '';
    if (ct.includes('application/json')) {
      try {
        return (await response.json()) as T;
      } catch (err) {
        this.logger.warn('http:bad-json', { url, error: formatError(err) });
        throw new ApiError('Server returned invalid JSON', response.status, url);
      }
    }
    // Fallback: return raw text
    return ((await response.text()) as unknown) as T;
  }

  buildUrl(path: string, query?: RequestOptions['query'], baseOverride?: string): string {
    const base = (baseOverride ?? this.config.snapshot().apiUrl).replace(/\/+$/, '');
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    let url = `${base}${cleanPath}`;
    if (query) {
      const params = new URLSearchParams();
      for (const [k, v] of Object.entries(query)) {
        if (v === undefined || v === null) continue;
        params.set(k, String(v));
      }
      const qs = params.toString();
      if (qs) url += `?${qs}`;
    }
    return url;
  }

  /** WebSocket URL derived from the configured API URL. */
  buildWsUrl(path: string): string {
    const api = this.config.snapshot().apiUrl;
    let origin: URL;
    try {
      origin = new URL(api);
    } catch {
      origin = new URL('http://localhost:8000/api');
    }
    const proto = origin.protocol === 'https:' ? 'wss:' : 'ws:';
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    // Derive the WS root from the API origin (strip trailing "/api" if present).
    const wsBase = origin.pathname.replace(/\/?api$/i, '');
    return `${proto}//${origin.host}${wsBase}${cleanPath}`;
  }

  private async parseError(response: Response, url: string): Promise<ApiError> {
    let detail: unknown = undefined;
    let message = response.statusText || `HTTP ${response.status}`;
    try {
      const data = await response.clone().json();
      detail = data;
      if (data && typeof data === 'object') {
        const d = (data as Record<string, unknown>).detail;
        if (typeof d === 'string') message = d;
        else if (Array.isArray(d)) message = d.map((x) => String(x)).join('; ');
        else if (d !== undefined) {
          try {
            message = JSON.stringify(d);
          } catch {
            /* keep statusText */
          }
        }
      }
    } catch {
      // body wasn't JSON — that's fine, statusText is the fallback
    }
    this.logger.warn('http:error', { url, status: response.status, message });
    return new ApiError(message, response.status, url, detail);
  }
}
