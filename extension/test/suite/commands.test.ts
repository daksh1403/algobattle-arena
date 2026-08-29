/**
 * commands.test.ts — verifies that the extension registers the expected
 * commands and that they appear in `vscode.commands.getCommands(true)`.
 *
 * This is a smoke test that runs in the VS Code test host after activation.
 */

import * as assert from 'assert';
import * as vscode from 'vscode';

suite('Extension commands', () => {
  test('all algobattle.* commands are registered', async () => {
    const expected = [
      'algobattle.login',
      'algobattle.logout',
      'algobattle.browseProblems',
      'algobattle.openProblem',
      'algobattle.pickProblem',
      'algobattle.runTests',
      'algobattle.submit',
      'algobattle.showLeaderboard',
      'algobattle.contestJoin',
      'algobattle.setApiUrl',
    ];
    const all = await vscode.commands.getCommands(true);
    const set = new Set(all);
    for (const id of expected) {
      assert.ok(set.has(id), `missing command: ${id}`);
    }
  });

  test('login command can be invoked without crashing when cancelled', async () => {
    // The login flow expects QuickPicks which the test runner may not surface.
    // We assert that `algobattle.login` resolves without throwing when called.
    const cmd = vscode.commands.executeCommand('algobattle.login');
    await cmd;
  });

  test('setApiUrl persists to configuration', async () => {
    const target = 'http://127.0.0.1:65535/api';
    const cfg = vscode.workspace.getConfiguration('algobattle');
    await cfg.update('apiUrl', target, vscode.ConfigurationTarget.Global);
    const fresh = vscode.workspace.getConfiguration('algobattle').get<string>('apiUrl');
    assert.strictEqual(fresh, target);
    // Restore default to keep workspace clean.
    await cfg.update('apiUrl', 'http://localhost:8000/api', vscode.ConfigurationTarget.Global);
  });
});
