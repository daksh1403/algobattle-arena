/**
 * auth.test.ts — verify AuthService persists JWT in SecretStorage.
 *
 * Strategy:
 *   1. Create a real AuthService against an in-memory ExtensionContext-like
 *      shim (SecretStorage + Memento).
 *   2. Stub the underlying AuthAPI using a fetch mock that returns a known
 *      AuthResponse payload.
 *   3. Call `auth.login(user, pw)` and assert:
 *        - SecretStorage holds the token
 *        - GlobalState holds the user JSON
 *        - onAuthChanged fires with `authenticated: true`
 *   4. Call `auth.logout()` and assert the inverse.
 */

import * as assert from 'assert';
import * as vscode from 'vscode';
import { AuthAPI } from '../../src/api/auth';
import { AuthService } from '../../src/services/AuthService';
import { FakeFetch, makeClient } from './_helpers';

interface SecretMap {
  store(key: string, value: string): Thenable<void>;
  get(key: string): Thenable<string | undefined>;
  delete(key: string): Thenable<void>;
  onDidChange: vscode.Event<vscode.SecretStorageChangeEvent>;
}

class MemorySecretStorage implements SecretMap {
  private readonly store_ = new Map<string, string>();
  readonly onDidChange: vscode.SecretStorageChangeEvent;
  private readonly emitter = new vscode.EventEmitter<vscode.SecretStorageChangeEvent>();

  constructor() {
    this.onDidChange = this.emitter.event;
  }

  async store(key: string, value: string): Promise<void> {
    this.store_.set(key, value);
    this.emitter.fire({ key });
  }

  async get(key: string): Promise<string | undefined> {
    return this.store_.get(key);
  }

  async delete(key: string): Promise<void> {
    this.store_.delete(key);
    this.emitter.fire({ key });
  }
}

class MemoryMemento implements vscode.Memento {
  private readonly data_ = new Map<string, unknown>();
  get<T>(key: string): T | undefined;
  get<T>(key: string, defaultValue: T): T;
  get<T>(key: string, defaultValue?: T): T | undefined {
    return (this.data_.get(key) as T | undefined) ?? defaultValue;
  }
  async update(key: string, value: unknown): Promise<void> {
    if (value === undefined) {
      this.data_.delete(key);
    } else {
      this.data_.set(key, value);
    }
  }
  keys(): readonly string[] {
    return Array.from(this.data_.keys());
  }
}

function fakeContext(): vscode.ExtensionContext {
  return {
    secrets: new MemorySecretStorage(),
    globalState: new MemoryMemento(),
    workspaceState: new MemoryMemento(),
    extensionPath: '/tmp/algobattle',
    extensionUri: vscode.Uri.file('/tmp/algobattle'),
    storageUri: vscode.Uri.file('/tmp/algobattle-storage'),
    storagePath: '/tmp/algobattle-storage',
    logUri: vscode.Uri.file('/tmp/algobattle-logs'),
    logPath: '/tmp/algobattle-logs',
    subscriptions: [],
    asAbsolutePath: (p: string) => p,
    extensionMode: vscode.ExtensionMode.Test,
    environmentVariableCollection: {} as vscode.GlobalEnvironmentVariableCollection,
    globalStorageUri: vscode.Uri.file('/tmp/algobattle-global'),
    globalStoragePath: '/tmp/algobattle-global',
    language: 'en',
    extension: {} as vscode.Extension<unknown>,
    storage: undefined,
    workspaceState_fallback: undefined,
  } as unknown as vscode.ExtensionContext;
}

suite('AuthService', () => {
  test('login persists JWT in SecretStorage and fires event', async () => {
    const fake = new FakeFetch();
    fake.respondWith(200, {
      access_token: 'jwt-abc-123',
      token_type: 'bearer',
      user: {
        id: 'u1',
        username: 'alice',
        email: 'alice@example.com',
        rating: 1500,
        avatar_url: null,
        created_at: '2025-01-01T00:00:00Z',
      },
    });

    const client = makeClient((url, init) => fake.fetch(url, init), null);
    const authApi = new AuthAPI(client);
    const ctx = fakeContext();
    const auth = new AuthService(ctx, client, authApi);

    const seen: Array<{ authenticated: boolean; user: string | null }> = [];
    const sub = auth.onAuthChanged((s) => {
      seen.push({ authenticated: s.authenticated, user: s.user?.username ?? null });
    });

    const res = await auth.login('alice', 'secret');
    assert.strictEqual(res.access_token, 'jwt-abc-123');
    assert.strictEqual(res.user.username, 'alice');

    const stored = await ctx.secrets.get('algobattle.jwt');
    assert.strictEqual(stored, 'jwt-abc-123');

    const userJson = ctx.globalState.get<string>('algobattle.user');
    assert.ok(userJson, 'user JSON should be persisted in globalState');
    const parsed = JSON.parse(userJson as string);
    assert.strictEqual(parsed.username, 'alice');

    assert.deepStrictEqual(seen, [{ authenticated: true, user: 'alice' }]);

    sub.dispose();
  });

  test('logout clears SecretStorage and fires event', async () => {
    const fake = new FakeFetch();
    fake.respondWith(204, null);

    const client = makeClient((url, init) => fake.fetch(url, init), 'pre-existing-token');
    const authApi = new AuthAPI(client);
    const ctx = fakeContext();
    const auth = new AuthService(ctx, client, authApi);

    // Pre-populate state by simulating a login first.
    await auth.login('alice', 'pw');
    assert.ok(await ctx.secrets.get('algobattle.jwt'));

    // Now logout. Use a fetch that returns 204.
    await auth.logout();
    assert.strictEqual(await ctx.secrets.get('algobattle.jwt'), undefined);
    assert.strictEqual(ctx.globalState.get('algobattle.user'), undefined);
    assert.strictEqual(auth.snapshot().authenticated, false);
  });

  test('load() recovers credentials from SecretStorage + globalState', async () => {
    const fake = new FakeFetch();
    const client = makeClient((url, init) => fake.fetch(url, init), null);
    const authApi = new AuthAPI(client);
    const ctx = fakeContext();

    // Pre-seed storage as if a previous session had stored them.
    await ctx.secrets.store('algobattle.jwt', 'persisted-jwt');
    await ctx.globalState.update(
      'algobattle.user',
      JSON.stringify({
        id: 'u9',
        username: 'bob',
        email: 'bob@example.com',
        rating: 1700,
        avatar_url: null,
        created_at: '2025-02-01T00:00:00Z',
      }),
    );

    const auth = new AuthService(ctx, client, authApi);
    await auth.load();
    assert.strictEqual(auth.snapshot().authenticated, true);
    assert.strictEqual(auth.snapshot().user?.username, 'bob');
    assert.strictEqual(auth.currentTokenSync(), 'persisted-jwt');
  });

  test('login throws when username is empty', async () => {
    const client = makeClient(() => Promise.resolve(new Response('{}', { status: 200 })));
    const auth = new AuthService(fakeContext(), client, new AuthAPI(client));
    await assert.rejects(() => auth.login('   ', 'pw'), /Username is required/);
  });
});
