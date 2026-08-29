/**
 * OutputChannelService — owns the "Algobattle" output channel and exposes a
 * `Logger` against it. Created once during activate().
 */

import * as vscode from 'vscode';
import { Logger, LogLevel, LogSink } from '../util/logger';

export class OutputChannelService implements LogSink {
  readonly channel: vscode.OutputChannel;
  readonly logger: Logger;

  private currentMinLevel: LogLevel = 'info';

  constructor(name: string = 'Algobattle') {
    this.channel = vscode.window.createOutputChannel(name);
    this.logger = new Logger('algobattle', this);
  }

  appendLine(line: string): void {
    this.channel.appendLine(line);
  }

  minLevel(): LogLevel {
    return this.currentMinLevel;
  }

  setMinLevel(level: LogLevel): void {
    this.currentMinLevel = level;
  }

  info(message: string, fields?: Record<string, unknown>): void {
    this.logger.info(message, fields);
  }

  warn(message: string, fields?: Record<string, unknown>): void {
    this.logger.warn(message, fields);
  }

  error(message: string, fields?: Record<string, unknown>): void {
    this.logger.error(message, fields);
  }

  debug(message: string, fields?: Record<string, unknown>): void {
    this.logger.debug(message, fields);
  }

  reveal(preserveFocus: boolean = false): void {
    this.channel.show(preserveFocus);
  }

  dispose(): void {
    this.channel.dispose();
  }
}
