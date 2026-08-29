/**
 * auth.ts — typed wrappers around /auth/*.
 */

import { AlgobattleClient } from './client';
import { isAuthResponse, isUser } from './types';
import type { AuthResponse, User } from './types';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export class AuthAPI {
  constructor(private readonly client: AlgobattleClient) {}

  /** POST /auth/login — returns the JWT + user record. */
  async login(username: string, password: string): Promise<AuthResponse> {
    const body = new URLSearchParams({ username, password });
    const res = await this.client.request<AuthResponse>('/auth/login', {
      method: 'POST',
      body,
      skipAuth: true,
      silent: true,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    if (!isAuthResponse(res)) {
      throw new Error('Server returned an unexpected auth payload');
    }
    return res;
  }

  /** POST /auth/register — creates an account and returns the new user. */
  async register(username: string, email: string, password: string): Promise<User> {
    const res = await this.client.request<User>('/auth/register', {
      method: 'POST',
      body: { username, email, password },
      skipAuth: true,
      silent: true,
    });
    if (!isUser(res)) {
      throw new Error('Server returned an unexpected register payload');
    }
    return res;
  }

  /** POST /auth/logout — best-effort revoke of the current JWT. */
  async logout(): Promise<void> {
    await this.client.request<void>('/auth/logout', {
      method: 'POST',
      expectEmpty: true,
    });
  }

  /** GET /users/me — fetches the authenticated user profile. */
  async me(): Promise<User> {
    const res = await this.client.request<User>('/users/me');
    if (!isUser(res)) {
      throw new Error('Server returned an unexpected /users/me payload');
    }
    return res;
  }
}
