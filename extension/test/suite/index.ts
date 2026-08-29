/**
 * suite/index.ts — Mocha root file invoked by `@vscode/test-cli`.
 *
 * Imports every test file; Mocha discovers them via `--require` / globs.
 */

import 'mocha';
import './auth.test';
import './api.test';
import './commands.test';
import './providers.test';
