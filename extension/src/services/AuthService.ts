/**
 * AuthService — wraps the auth API and persists the JWT in SecretStorage.
 *
 *  - Single source of truth for "is the user authenticated?"
 *  - Emits `onAuthChanged` so views refresh after login/logout
 *  - Safe to call from any context; failures surface typed errors
 */

import * as vscode from 'vscode';
import { AlgobattleClient, ApiError } from '../api/client';
import type { AuthAPI } from '../api/auth';
import type { AuthResponse, User } from '../api/types';

const TOKEN_KEY = 'algobattle.jwt';
const USER_KEY = 'algobattle.user';

export interface AuthSnapshot {
  readonly authenticated: boolean;
  readonly user: User | null;
}

export class AuthService {
  private readonly secretStore: vscode.SecretStorage;
  private readonly memento: vscode.Memento;
  private readonly emitter = new vscode.EventEmitter<AuthSnapshot>();
  private currentToken: string | null = null;
  private currentUser: User | null = null;
  private loaded = false;
  private loading: Promise<AuthSnapshot> | null = null;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly client: AlgobattleClient,
    private readonly authApi: AuthAPI,
  ) {
    this.secretStore = context.secrets;
    this.memento = context.globalState;
    this.emitter.fire(this.snapshot());
  }

  readonly onAuthChanged = this.emitter.event;

  snapshot(): AuthSnapshot {
    return Object.freeze({
      authenticated: this.currentToken !== null && this.currentUser !== null,
      user: this.currentUser,
    });
  }

  /** Lazily load token + user from storage; safe to call multiple times. */
  async load(): Promise<AuthSnapshot> {
    if (this.loaded) return this.snapshot();
    if (this.loading) return this.loading;

    this.loading = (async () => {
      try {
        const [token, userJson] = await Promise.all([
          this.secretStore.get(TOKEN_KEY),
          Promise.resolve(this.memento.get<string>(USER_KEY)),
        ]);
        if (token && typeof token === 'string' && token.length > 0) {
          this.currentToken = token;
        }
        if (userJson) {
          const parsed = safeParseUser(userJson);
          if (parsed) this.currentUser = parsed;
        }
        this.loaded = true;
      } finally {
        this.loading = null;
      }
      this.emitter.fire(this.snapshot());
      return this.snapshot();
    })();
    return this.loading;
  }

  currentTokenSync(): string | null {
    return this.currentToken;
  }

  /** Login flow: exchange credentials, persist token+user, fire event. */
  async login(username: string, password: string): Promise<AuthResponse> {
    if (!username.trim()) throw new Error('Username is required');
    if (!password) throw new Error('Password is required');

    const res = await this.authApi.login(username.trim(), password);
    await this.persist(res.access_token, res.user);
    return res;
  }

  async register(username: string, email: string, password: string): Promise<User> {
    if (!username.trim()) throw new Error('Username is required');
    if (!email.includes('@')) throw new Error('A valid email is required');
    if (password.length < 6) throw new Error('Password must be at least 6 characters');

    const user = await this.authApi.register(username.trim(), email.trim(), password);
    // After registration users typically log in.
    return user;
  }

  /** Clear local credentials; revoke on server best-effort. */
  async logout(): Promise<void> {
    try {
      await this.authApi.logout();
    } catch (err) {
      // Even if the server is unreachable, we still clear local state.
      // ApiError 401 is expected and not worth surfacing.
      if (!(err instanceof ApiError) || err.status !== 401) {
        // ignore but keep type-narrowing
      }
    }
    await this.persist(null, null);
  }

  /** Expose the underlying API client for callers that need it. */
  getClient(): AlgobattleClient {
    return this.client;
  }

  private async persist(token: string | null, user: User | null): Promise<void> {
    if (token === null) {
      await this.secretStore.delete(TOKEN_KEY);
    } else {
      await this.secretStore.store(TOKEN_KEY, token);
    }
    if (user === null) {
      await this.memento.update(USER_KEY, undefined);
    } else {
      await this.memento.update(USER_KEY, JSON.stringify(user));
    }
    this.currentToken = token;
    this.currentUser = user;
    this.loaded = true;
    this.emitter.fire(this.snapshot());
  }
}

function safeParseUser(json: string): User | null {
  try {
    const obj = JSON.parse(json) as Partial<User>;
    if (!obj || typeof obj !== 'object') return null;
    if (typeof obj.id !== 'string' || typeof obj.username !== 'string') return null;
    return {
      id: obj.id,
      username: obj.username,
      email: typeof obj.email === 'string' ? obj.email : '',
      rating: typeof obj.rating === 'number' ? obj.rating : 0,
      avatar_url: typeof obj.avatar_url === 'string' ? obj.avatar_url : null,
      created_at: typeof obj.created_at === 'string' ? obj.created_at : new Date().toISOString(),
    };
  } catch {
    return null;
  }
}
