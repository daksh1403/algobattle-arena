/**
 * languages.ts — language mapping between VS Code `editor.languageId`,
 * the API's `SupportedLanguage` taxonomy, and file extensions.
 *
 * The API uses 'python', 'javascript', 'cpp'. The extension uses
 * 'python3' for clarity in user-facing config.
 */

export type SupportedLanguage = 'python' | 'javascript' | 'cpp';

export interface LanguageDescriptor {
  /** VS Code language id used by extensions (e.g. 'python', 'javascript', 'cpp'). */
  readonly vscodeId: string;
  /** Wire value sent to the backend. */
  readonly apiId: SupportedLanguage;
  /** File extension including dot, e.g. '.py'. */
  readonly extension: string;
  /** Human-friendly label used in QuickPicks. */
  readonly label: string;
  /** Starter-code filename (without leading dot), e.g. 'starter.py'. */
  readonly starterFilename: string;
}

/**
 * Curated table of supported languages.
 * Order is fixed — used in QuickPick and config validation.
 */
export const LANGUAGES: readonly LanguageDescriptor[] = Object.freeze([
  {
    vscodeId: 'python',
    apiId: 'python',
    extension: '.py',
    label: 'Python 3',
    starterFilename: 'starter.py',
  },
  {
    vscodeId: 'javascript',
    apiId: 'javascript',
    extension: '.js',
    label: 'JavaScript (Node)',
    starterFilename: 'starter.js',
  },
  {
    vscodeId: 'cpp',
    apiId: 'cpp',
    extension: '.cpp',
    label: 'C++ (g++ 17)',
    starterFilename: 'starter.cpp',
  },
]);

/** Map VS Code id (e.g. 'python') → descriptor; undefined when unsupported. */
export function fromVscodeId(id: string): LanguageDescriptor | undefined {
  return LANGUAGES.find((l) => l.vscodeId === id);
}

/** Map API id (e.g. 'python') → descriptor; undefined when unknown. */
export function fromApiId(id: string): LanguageDescriptor | undefined {
  return LANGUAGES.find((l) => l.apiId === id);
}

/**
 * Map extension's display id ('python3' | 'javascript' | 'cpp') → API id.
 * Falls back to 'python' when the display id is unknown.
 */
export function displayToApi(displayId: string): SupportedLanguage {
  if (displayId === 'python3') return 'python';
  if (displayId === 'javascript') return 'javascript';
  if (displayId === 'cpp') return 'cpp';
  return 'python';
}

/** Build a starter-template code block for the given language. */
export function defaultStarterCode(lang: LanguageDescriptor): string {
  switch (lang.apiId) {
    case 'python':
      return [
        'class Solution:',
        '    def solve(self, *args, **kwargs):',
        '        """Replace this with your implementation."""',
        '        raise NotImplementedError',
        '',
      ].join('\n');
    case 'javascript':
      return [
        '/**',
        ' * @param {...any} args',
        ' * @returns {any}',
        ' */',
        'function solve(...args) {',
        '  // Replace this with your implementation.',
        '  throw new Error("Not implemented");',
        '}',
        '',
        'module.exports = { solve };',
        '',
      ].join('\n');
    case 'cpp':
      return [
        '#include <bits/stdc++.h>',
        'using namespace std;',
        '',
        'class Solution {',
        'public:',
        '    // Replace this with your implementation.',
        '    auto solve(/* params */) {',
        '        throw runtime_error("Not implemented");',
        '    }',
        '};',
        '',
      ].join('\n');
    /* c8 ignore next 2 */
    default:
      return '// Unsupported language';
  }
}

/**
 * Heuristic detector: pick the most likely descriptor based on filename.
 * Used when the active editor doesn't expose a reliable `languageId`.
 */
export function detectFromFilename(path: string): LanguageDescriptor | undefined {
  const lower = path.toLowerCase();
  if (lower.endsWith('.py')) return LANGUAGES[0];
  if (lower.endsWith('.js') || lower.endsWith('.mjs') || lower.endsWith('.cjs')) return LANGUAGES[1];
  if (lower.endsWith('.cpp') || lower.endsWith('.cc') || lower.endsWith('.cxx')) return LANGUAGES[2];
  return undefined;
}
