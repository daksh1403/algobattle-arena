/**
 * _helpers.ts — shared test scaffolding.
 *
 * Each helper returns a fresh instance per call (no shared mutable state).
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';
import { AlgobattleClient, ApiError, type RequestOptions } from '../../src/api/client';
import { OutputChannelService } from '../../src/services/OutputChannelService';
import { ConfigService } from '../../src/util/config';
import { Logger } from '../../src/util/logger';
import type { AuthAPI } from '../../src/api/auth';
import type { ContestCache } from '../../src/services/ContestCache';

export interface FetchCall {
  url: string;
  init: RequestInit | undefined;
  /** Resolved at call time. */
  responded: (status: number, body: unknown) => Response;
}

export class FakeFetch {
  public readonly calls: FetchCall[] = [];
  public nextResponder: (call: FetchCall, idx: number) => Response = () => new Response('{}', { status: 200 });

  /** Pre-seed a single canned response. */
  respondWith(status: number, body: unknown): void {
    this.nextResponder = () => new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    });
  }

  async fetch(url: string, init?: RequestInit): Promise<Response> {
    const call: FetchCall = {
      url,
      init,
      responded: () => new Response('{}', { status: 200 }),
    };
    this.calls.push(call);
    const response = this.nextResponder(call, this.calls.length - 1);
    call.responded = (s, b) => new Response(typeof b === 'string' ? b : JSON.stringify(b), {
      status: s,
      headers: { 'content-type': 'application/json' },
    });
    return response;
  }

  count(): number {
    return this.calls.length;
  }
}

export function makeClient(fetchImpl: typeof fetch, token: string | null = null): AlgobattleClient {
  const cfg = new ConfigService();
  // Pin the config to a fixed API URL via override on each request.
  const log = new Logger('test', { appendLine: () => undefined });
  return new AlgobattleClient(log, cfg, () => token, fetchImpl);
}

export function makeLogger(): Logger {
  return new Logger('test', { appendLine: () => undefined });
}

/**
 * Return a string-only OutputChannel mock — useful when a command or service
 * expects a fully-formed `vscode.OutputChannel`.
 */
export function fakeOutputChannel(): vscode.OutputChannel {
  return {
    name: 'algobattle-test',
    append: () => undefined,
    appendLine: () => undefined,
    clear: () => undefined,
    show: () => undefined,
    hide: () => undefined,
    dispose: () => undefined,
    replace: () => undefined,
  };
}

export function tmpWorkspaceRoot(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'algobattle-test-'));
  return dir;
}

/** A `RequestOptions` exporter for consumers that want to type narrow. */
export type { RequestOptions, ApiError };

/** Re-export for tests that need to construct an AuthService. */
export type { AuthAPI, ContestCache };
