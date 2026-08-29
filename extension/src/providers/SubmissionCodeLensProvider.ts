/**
 * SubmissionCodeLensProvider — adds "▶ Test" and "✓ Submit" CodeLenses
 * above the solution entry-point line in `.algobattle/<slug>/starter.*`.
 *
 * The entry-point pattern is language-aware:
 *   python:      `class Solution:`
 *   javascript:  `function solve(`
 *   cpp:         `class Solution {`
 */

import * as vscode from 'vscode';

interface Pattern {
  readonly regex: RegExp;
  readonly label: string;
}

const PATTERNS: Pattern[] = [
  { regex: /^\s*class\s+Solution\s*[:{]/m, label: 'class Solution' },
  { regex: /^\s*function\s+solve\s*\(/m, label: 'function solve' },
];

export class SubmissionCodeLensProvider implements vscode.CodeLensProvider {
  private readonly emitter = new vscode.EventEmitter<void>();
  readonly onDidChangeCodeLenses = this.emitter.event;

  provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
    const fileName = document.fileName.toLowerCase();
    if (!fileName.includes('/.algobattle/') && !fileName.includes('\\.algobattle\\')) return [];

    const text = document.getText();
    let line: number | undefined;
    for (const p of PATTERNS) {
      const m = p.regex.exec(text);
      if (m) {
        const pos = document.positionAt(m.index);
        line = pos.line;
        break;
      }
    }
    if (line === undefined) {
      // Fallback: top of file
      line = 0;
    }
    const range = new vscode.Range(line, 0, line, 0);

    const testLens = new vscode.CodeLens(range, {
      title: '▶ Test (Algobattle)',
      command: 'algobattle.runTests',
      tooltip: 'Run visible samples',
    });
    const submitLens = new vscode.CodeLens(range, {
      title: '✓ Submit (Algobattle)',
      command: 'algobattle.submit',
      tooltip: 'Submit to the judge',
    });
    return [testLens, submitLens];
  }

  /** Force a refresh — call after file save. */
  invalidate(): void {
    this.emitter.fire();
  }
}
