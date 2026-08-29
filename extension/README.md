# Algobattle for VS Code

> Solve LeetCode-style problems and compete, all from VS Code.

Algobattle is a VS Code extension that lets you browse curated algorithmic problems, write solutions in your favourite language, run them against visible samples, submit them to the Algobattle judge, and watch the live contest leaderboard — without ever leaving your editor.

## Features

- 🧩 **Problems tree view** — Easy / Medium / Hard grouping in the Explorer.
- 🏆 **Contests tree view** — Active / Upcoming / Past with one-click join.
- ▶️ **Test & ✓ Submit CodeLenses** above `class Solution:` / `function solve(`.
- 🌐 **Problem Browser WebView** — Markdown statements, samples, in-page editor.
- ⚡ **Live Leaderboard** — WebSocket-driven updates inside VS Code.
- 🔐 **Secure JWT storage** via VS Code SecretStorage.
- 🪶 **Lightweight** — esbuild bundle, native `fetch`, no heavyweight ML deps.

## Quick start

1. Install the extension.
2. Run **Algobattle: Login** — enter your credentials; the JWT is saved to SecretStorage.
3. Run **Algobattle: Browse Problems** or click any entry in the **Problems** explorer view.
4. Run **Algobattle: Run Tests** (`⌘⌃T` / `Ctrl+Shift+T`) to verify on samples.
5. Run **Algobattle: Submit** (`⌘⌃S` / `Ctrl+Shift+S`) to send to the judge.
6. Run **Algobattle: Show Leaderboard** to watch rankings live during a contest.

## Commands

| Command | Keybinding | Purpose |
| --- | --- | --- |
| `algobattle.login` | — | Authenticate and store JWT |
| `algobattle.logout` | — | Clear JWT and refresh views |
| `algobattle.browseProblems` | — | Open the problem-browser WebView |
| `algobattle.openProblem` | — | Quickpick a problem and scaffold it in your workspace |
| `algobattle.runTests` | `Ctrl+Shift+T` | Run visible sample tests for the open file |
| `algobattle.submit` | `Ctrl+Shift+S` | Submit to the judge |
| `algobattle.showLeaderboard` | — | Open the live leaderboard WebView |
| `algobattle.contestJoin` | — | Quickpick an active contest |
| `algobattle.setApiUrl` | — | Change the backend endpoint |

## Configuration

| Setting | Default | Notes |
| --- | --- | --- |
| `algobattle.apiUrl` | `http://localhost:8000/api` | Algobattle REST endpoint |
| `algobattle.defaultLanguage` | `python3` | One of `python3`, `javascript`, `cpp` |
| `algobattle.autoSubmitOnSave` | `false` | Reserved for future use |
| `algobattle.outputVerbosity` | `info` | Log level for the output channel |

## Architecture

```
src/
  api/         ← typed fetch wrappers (auth, problems, submissions, leaderboard)
  services/    ← stateful helpers (Auth, Cache, Notifications, OutputChannel)
  commands/    ← command handler entry points
  providers/   ← TreeView + CodeLens + StatusBar providers
  webviews/    ← problem-detail + leaderboard WebViews
  util/        ← pure utilities (config, logger, languages, problem-storage)
test/          ← Mocha + @vscode/test-cli suite
```

The HTTP client (`api/client.ts`) is the single source for auth headers, error normalization, and structured logging — every request passes through it.

## Development

```bash
npm install
npm run watch           # esbuild bundle into out/extension.js
npm test                # download VS Code & run tests headlessly
npx vsce package        # build .vsix
```

## License

MIT — see [LICENSE](./LICENSE).
