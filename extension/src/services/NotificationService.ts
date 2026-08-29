/**
 * NotificationService — uniform surface for user-facing toasts and
 * an in-channel log record so debugging is always possible.
 *
 * The `silent` flag is used by commands to suppress popups during automated
 * polling (e.g. while a submission is being re-checked).
 */

import * as vscode from 'vscode';
import { OutputChannelService } from './OutputChannelService';

export interface NotifyOptions {
  /** Suppress the toast and only log; default false. */
  silent?: boolean;
  /** Extra fields appended to the output channel entry. */
  fields?: Record<string, unknown>;
}

export class NotificationService {
  constructor(private readonly output: OutputChannelService) {}

  info(message: string, opts: NotifyOptions = {}): void {
    this.output.info(message, opts.fields);
    if (!opts.silent) void vscode.window.showInformationMessage(message);
  }

  warn(message: string, opts: NotifyOptions = {}): void {
    this.output.warn(message, opts.fields);
    if (!opts.silent) void vscode.window.showWarningMessage(message);
  }

  error(message: string, opts: NotifyOptions = {}): void {
    this.output.error(message, opts.fields);
    if (!opts.silent) void vscode.window.showErrorMessage(message, 'Show Output').then((action) => {
      if (action === 'Show Output') this.output.reveal(true);
    });
  }

  /** WithProgress helper that keeps the output channel in sync with lifecycle events. */
  async withProgress<T>(
    title: string,
    task: (report: (msg: string, increment?: number) => void) => Promise<T>,
    options: { cancellable?: boolean; silent?: boolean } = {},
  ): Promise<T> {
    return vscode.window.withProgress<T>(
      {
        location: vscode.ProgressLocation.Notification,
        title,
        cancellable: Boolean(options.cancellable),
      },
      async (progress) => {
        const report = (msg: string, increment?: number) => {
          progress.report({ message: msg, increment });
          this.output.debug(`[progress:${title}] ${msg}`);
        };
        try {
          const result = await task(report);
          if (!options.silent) this.info(`${title} complete`);
          return result;
        } catch (err) {
          this.error(`${title} failed: ${formatMsg(err)}`);
          throw err;
        }
      },
    );
  }

  /** Convenience: prompt the user for confirmation. */
  async confirm(message: string, detail?: string): Promise<boolean> {
    const choice = await vscode.window.showInformationMessage(
      message,
      { modal: true, detail },
      'Confirm',
      'Cancel',
    );
    return choice === 'Confirm';
  }
}

function formatMsg(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
