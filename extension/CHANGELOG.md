# Changelog

All notable changes to the Algobattle extension are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — 2025-01-15

### Added
- Initial release.
- JWT login / logout, token persisted in VS Code SecretStorage.
- Problems & Contests tree views grouped by difficulty / status.
- CodeLens Test & Submit above solution declarations in `.algobattle/**` files.
- Problem-browser WebView with Markdown statements and sample tests.
- Live leaderboard WebView driven by WebSocket reconnects.
- Run-tests and Submit commands with status-bar progress and output channel.
- Configurable API URL and default language.
- Mocha test suite runnable via `@vscode/test-cli`.
