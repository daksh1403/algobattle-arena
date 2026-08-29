/**
 * login.ts — Algobattle login command.
 *
 *  1. QuickPick to choose between login / register / cancel
 *  2. Username prompt → Password prompt
 *  3. POST /auth/login → store JWT in SecretStorage via AuthService
 *  4. Refresh dependent TreeProviders
 */

import * as vscode from 'vscode';
import type { AuthService } from '../services/AuthService';
import type { NotificationService } from '../services/NotificationService';

type Action = { id: 'login' | 'register'; label: string };

export async function loginCommand(
  context: vscode.ExtensionContext,
  auth: AuthService,
  notifications: NotificationService,
): Promise<void> {
  // Make sure any cached credentials are loaded before we ask the user.
  await auth.load();
  if (auth.snapshot().authenticated) {
    const username = auth.snapshot().user?.username ?? 'current user';
    const choice = await vscode.window.showQuickPick(
      [
        { id: 'switch', label: `Sign in as a different user (currently ${username})` },
        { id: 'logout', label: 'Logout' },
        { id: 'cancel', label: 'Cancel' },
      ] as { id: string; label: string }[],
      { title: 'Algobattle: You are already signed in', ignoreFocusOut: true },
    );
    if (!choice || choice.id === 'cancel') return;
    if (choice.id === 'logout') {
      await vscode.commands.executeCommand('algobattle.logout');
      return;
    }
  }

  const actionPick = await vscode.window.showQuickPick<Action>(
    [
      { id: 'login', label: '$(sign-in) Login' },
      { id: 'register', label: '$(add) Register a new account' },
    ],
    { title: 'Algobattle', placeHolder: 'How would you like to sign in?', ignoreFocusOut: true },
  );
  if (!actionPick) return;

  if (actionPick.id === 'register') {
    await registerFlow(auth, notifications);
    return;
  }

  await loginFlow(auth, notifications);
}

async function loginFlow(auth: AuthService, notifications: NotificationService): Promise<void> {
  const username = await vscode.window.showInputBox({
    title: 'Algobattle: Username',
    prompt: 'Enter your username or email',
    ignoreFocusOut: true,
    validateInput: (v) => (v.trim().length > 0 ? undefined : 'Username is required'),
  });
  if (!username) return;

  const password = await vscode.window.showInputBox({
    title: 'Algobattle: Password',
    prompt: 'Enter your password',
    password: true,
    ignoreFocusOut: true,
    validateInput: (v) => (v.length > 0 ? undefined : 'Password is required'),
  });
  if (!password) return;

  try {
    const res = await auth.login(username, password);
    notifications.info(`Signed in as ${res.user.username}`, {
      fields: { user_id: res.user.id },
    });
    await vscode.commands.executeCommand('setContext', 'algobattle.authed', true);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    notifications.error(`Login failed: ${message}`);
  }
}

async function registerFlow(auth: AuthService, notifications: NotificationService): Promise<void> {
  const username = await vscode.window.showInputBox({
    title: 'Algobattle: Choose a username',
    prompt: 'Letters, numbers, and underscores',
    ignoreFocusOut: true,
    validateInput: (v) => (v.trim().length >= 3 ? undefined : 'Username must be at least 3 characters'),
  });
  if (!username) return;

  const email = await vscode.window.showInputBox({
    title: 'Algobattle: Email',
    prompt: 'Enter a valid email address',
    ignoreFocusOut: true,
    validateInput: (v) => (v.includes('@') ? undefined : 'Email must contain "@"'),
  });
  if (!email) return;

  const password = await vscode.window.showInputBox({
    title: 'Algobattle: Password',
    prompt: 'At least 6 characters',
    password: true,
    ignoreFocusOut: true,
    validateInput: (v) => (v.length >= 6 ? undefined : 'Password must be at least 6 characters'),
  });
  if (!password) return;

  try {
    const user = await auth.register(username, email, password);
    notifications.info(`Account created for ${user.username}. Signing you in…`);
    await auth.login(username, password);
    await vscode.commands.executeCommand('setContext', 'algobattle.authed', true);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    notifications.error(`Registration failed: ${message}`);
  }
}
