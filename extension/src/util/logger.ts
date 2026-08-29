/**
 * logger.ts — structured logger writing to a VS Code OutputChannel.
 *
 * - Single-channel writer registered via OutputChannelService.
 * - Strings are formatted `[LEVEL] [ISO-8601] message`.
 * - No console.* calls anywhere else should be necessary.
 */

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

const LEVEL_RANK: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

export interface LogSink {
  appendLine(line: string): void;
  /** Optional minimum level filter; default accepts everything. */
  minLevel?(): LogLevel | undefined;
}

export class Logger {
  private readonly sink: LogSink;
  private readonly tag: string;

  constructor(tag: string, sink: LogSink) {
    this.tag = tag;
    this.sink = sink;
  }

  debug(message: string, fields?: Record<string, unknown>): void {
    this.write('debug', message, fields);
  }

  info(message: string, fields?: Record<string, unknown>): void {
    this.write('info', message, fields);
  }

  warn(message: string, fields?: Record<string, unknown>): void {
    this.write('warn', message, fields);
  }

  error(message: string, fields?: Record<string, unknown>): void {
    this.write('error', message, fields);
  }

  private write(level: LogLevel, message: string, fields?: Record<string, unknown>): void {
    const min = this.sink.minLevel?.();
    if (min && LEVEL_RANK[level] < LEVEL_RANK[min]) return;

    const ts = new Date().toISOString();
    const head = `[${level.toUpperCase()}] [${ts}] [${this.tag}]`;
    let line = `${head} ${message}`;
    if (fields && Object.keys(fields).length > 0) {
      try {
        line += ' ' + JSON.stringify(fields);
      } catch {
        line += ' [unserializable fields]';
      }
    }
    this.sink.appendLine(line);
  }
}

/**
 * Format any thrown value as an error string suitable for logs.
 * Returns `[Error] message\nstack` when given an Error, or `String(err)` otherwise.
 */
export function formatError(err: unknown): string {
  if (err instanceof Error) {
    const stack = err.stack ?? '';
    return stack ? `${err.name}: ${err.message}\n${stack}` : `${err.name}: ${err.message}`;
  }
  if (typeof err === 'string') return err;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}
