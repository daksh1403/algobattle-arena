/**
 * runTest.ts — entry point for `@vscode/test-cli`.
 *
 * Boots a fresh VS Code instance with the extension under test loaded,
 * then runs the compiled Mocha suite located in `out/test/suite`.
 */

import * as path from 'path';
import { runTests } from '@vscode/test-electron';

async function main(): Promise<void> {
  try {
    const extensionDevelopmentPath = path.resolve(__dirname, '..');
    const extensionTestsPath = path.resolve(__dirname, './suite/index.js');

    await runTests({
      extensionDevelopmentPath,
      extensionTestsPath,
      launchArgs: [
        // Disable updates & telemetry to keep the headless run deterministic.
        '--disable-gpu',
        '--disable-updates',
        '--skip-welcome',
        '--skip-release-notes',
        '--disable-telemetry',
        // Force the extension to load against a clean state.
        '--user-data-dir',
        path.resolve(__dirname, '..', '.vscode-test-user-data'),
      ],
      version: process.env.VSCODE_TEST_VERSION || undefined,
    });
  } catch (err) {
    console.error('Failed to run tests', err);
    process.exit(1);
  }
}

void main();
