/**
 * config.ts — strongly-typed accessors for the `algobattle.*` settings.
 *
 * Provides:
 *  - ConfigService: thin wrapper around vscode.workspace.getConfiguration
 *  - AlgobattleConfig: frozen snapshot of relevant settings
 *  - onConfigChange(): subscribe helper
 *
 * No `any` is used; missing values fall back to declared defaults.
 */

import * as vscode from 'vscode';

export type SupportedLanguageId = 'python3' | 'javascript' | 'cpp';
export type OutputVerbosity = 'debug' | 'info' | 'warn' | 'error';

export interface AlgobattleConfig {
  readonly apiUrl: string;
  readonly defaultLanguage: SupportedLanguageId;
  readonly autoSubmitOnSave: boolean;
  readonly outputVerbosity: OutputVerbosity;
}

const DEFAULTS: AlgobattleConfig = {
  apiUrl: 'http://localhost:8000/api',
  defaultLanguage: 'python3',
  autoSubmitOnSave: false,
  outputVerbosity: 'info',
};

function readSupportedLanguage(raw: unknown): SupportedLanguageId {
  if (raw === 'python3' || raw === 'javascript' || raw === 'cpp') return raw;
  return DEFAULTS.defaultLanguage;
}

function readVerbosity(raw: unknown): OutputVerbosity {
  if (raw === 'debug' || raw === 'info' || raw === 'warn' || raw === 'error') return raw;
  return DEFAULTS.outputVerbosity;
}

export class ConfigService {
  constructor(private readonly scope: 'application' | 'workspace' = 'application') {}

  /** Read a fully-typed snapshot of the current config. */
  snapshot(): AlgobattleConfig {
    const cfg = vscode.workspace.getConfiguration('algobattle', this.scope === 'workspace' ? undefined : undefined);
    const rawApi = cfg.get<string>('apiUrl', DEFAULTS.apiUrl);
    const rawLang = cfg.get<string>('defaultLanguage', DEFAULTS.defaultLanguage);
    const rawAuto = cfg.get<boolean>('autoSubmitOnSave', DEFAULTS.autoSubmitOnSave);
    const rawVerb = cfg.get<string>('outputVerbosity', DEFAULTS.outputVerbosity);

    return Object.freeze({
      apiUrl: typeof rawApi === 'string' && rawApi.length > 0 ? rawApi : DEFAULTS.apiUrl,
      defaultLanguage: readSupportedLanguage(rawLang),
      autoSubmitOnSave: Boolean(rawAuto),
      outputVerbosity: readVerbosity(rawVerb),
    });
  }

  /** Update `algobattle.apiUrl` at user scope; returns true when VS Code accepted the write. */
  async setApiUrl(value: string): Promise<boolean> {
    const cfg = vscode.workspace.getConfiguration('algobattle');
    const trimmed = value.trim();
    if (trimmed.length === 0) return false;
    await cfg.update('apiUrl', trimmed, vscode.ConfigurationTarget.Global);
    return true;
  }

  /** Subscribe to config changes; returns a disposable. */
  onConfigChange(listener: (next: AlgobattleConfig) => void): vscode.Disposable {
    return vscode.workspace.onDidChangeConfiguration((evt) => {
      if (evt.affectsConfiguration('algobattle')) listener(this.snapshot());
    });
  }
}
