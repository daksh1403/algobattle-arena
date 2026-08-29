/**
 * setApiUrl.ts — change the `algobattle.apiUrl` setting.
 */

import * as vscode from 'vscode';
import type { ConfigService } from '../util/config';
import type { NotificationService } from '../services/NotificationService';

export async function setApiUrlCommand(
  config: ConfigService,
  notifications: NotificationService,
): Promise<void> {
  const current = config.snapshot().apiUrl;
  const value = await vscode.window.showInputBox({
    title: 'Algobattle: API URL',
    prompt: 'Enter the new API base URL',
    value: current,
    ignoreFocusOut: true,
    validateInput: (v) => {
      try {
        new URL(v.trim());
        return undefined;
      } catch {
        return 'Must be a valid URL (e.g. https://api.algobattle.dev/api)';
      }
    },
  });
  if (!value) return;

  const ok = await config.setApiUrl(value);
  if (ok) {
    notifications.info(`API URL set to ${value}`);
  } else {
    notifications.error('Failed to update algobattle.apiUrl');
  }
}
