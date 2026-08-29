/**
 * extension.ts — Algobattle activation entry point.
 *
 * Wires up:
 *   - ConfigService / OutputChannelService / NotificationService
 *   - AlgobattleClient + feature APIs
 *   - AuthService (SecretStorage-backed)
 *   - TreeProviders (problems & contests)
 *   - CodeLens & StatusBar providers
 *   - All commands
 */

import * as vscode from 'vscode';

import { AlgobattleClient } from './api/client';
import { AuthAPI } from './api/auth';
import { ProblemAPI } from './api/problems';
import { SubmissionAPI } from './api/submissions';
import { ContestAPI } from './api/contests';
import { LeaderboardAPI } from './api/leaderboard';

import { AuthService } from './services/AuthService';
import { ContestCache } from './services/ContestCache';
import { NotificationService } from './services/NotificationService';
import { OutputChannelService } from './services/OutputChannelService';

import { ProblemTreeProvider } from './providers/ProblemTreeProvider';
import { ContestTreeProvider } from './providers/ContestTreeProvider';
import { SubmissionCodeLensProvider } from './providers/SubmissionCodeLensProvider';
import { ProblemStatusBarProvider } from './providers/ProblemStatusBarProvider';

import { ConfigService } from './util/config';

import { loginCommand } from './commands/login';
import { logoutCommand } from './commands/logout';
import { browseProblemsCommand } from './commands/browseProblems';
import { openProblemCommand } from './commands/openProblem';
import { runTestsCommand } from './commands/runTests';
import { submitCommand } from './commands/submit';
import { showLeaderboardCommand } from './commands/showLeaderboard';
import { contestJoinCommand } from './commands/contestJoin';
import { setApiUrlCommand } from './commands/setApiUrl';

let outputChannel: OutputChannelService | undefined;
let problemTree: ProblemTreeProvider | undefined;
let contestTree: ContestTreeProvider | undefined;
let statusBar: ProblemStatusBarProvider | undefined;
let codeLens: SubmissionCodeLensProvider | undefined;
let auth: AuthService | undefined;
let cache: ContestCache | undefined;
let problemsApi: ProblemAPI | undefined;
let submissionsApi: SubmissionAPI | undefined;
let contestsApi: ContestAPI | undefined;
let leaderboardsApi: LeaderboardAPI | undefined;
let notifications: NotificationService | undefined;
let config: ConfigService | undefined;

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const output = new OutputChannelService('Algobattle');
  outputChannel = output;
  output.info('Activating Algobattle extension');

  notifications = new NotificationService(output);
  cache = new ContestCache();
  config = new ConfigService();

  // Configure verbosity from settings.
  output.setMinLevel(config.snapshot().outputVerbosity);
  context.subscriptions.push(
    config.onConfigChange((next) => {
      output.setMinLevel(next.outputVerbosity);
    }),
  );

  const client = new AlgobattleClient(output.logger, config, () => auth?.currentTokenSync() ?? null);
  const authApi = new AuthAPI(client);
  problemsApi = new ProblemAPI(client);
  submissionsApi = new SubmissionAPI(client);
  contestsApi = new ContestAPI(client);
  leaderboardsApi = new LeaderboardAPI(client);

  auth = new AuthService(context, client, authApi);
  context.subscriptions.push(
    auth.onAuthChanged((snap) => {
      void vscode.commands.executeCommand('setContext', 'algobattle.authed', snap.authenticated);
    }),
  );

  // Build providers.
  const outputForProviders = output;
  const notificationsForProviders = notifications;
  problemTree = new ProblemTreeProvider(auth, cache, problemsApi, notificationsForProviders, outputForProviders);
  contestTree = new ContestTreeProvider(auth, cache, contestsApi, notificationsForProviders, outputForProviders);
  problemTree.bind();
  codeLens = new SubmissionCodeLensProvider();
  statusBar = new ProblemStatusBarProvider();
  statusBar.bind();
  statusBar.update(vscode.window.activeTextEditor);

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('algobattle.problems', problemTree),
    vscode.window.registerTreeDataProvider('algobattle.contests', contestTree),
    vscode.languages.registerCodeLensProvider({ pattern: '**/.algobattle/**' }, codeLens),
    vscode.window.onDidChangeActiveTextEditor((editor) => statusBar?.update(editor)),
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (doc.uri.fsPath.includes('/.algobattle/')) {
        codeLens?.invalidate();
      }
    }),
  );

  // Register commands.
  context.subscriptions.push(
    vscode.commands.registerCommand('algobattle.login', () => {
      if (auth && notifications) return loginCommand(context, auth, notifications);
      return undefined;
    }),
    vscode.commands.registerCommand('algobattle.logout', () => {
      if (auth && cache && notifications && problemTree && contestTree) {
        return logoutCommand(auth, cache, notifications, problemTree, contestTree);
      }
      return undefined;
    }),
    vscode.commands.registerCommand('algobattle.browseProblems', () => {
      if (auth && cache && problemsApi && notifications) {
        return browseProblemsCommand(context, auth, cache, problemsApi, notifications);
      }
      return undefined;
    }),
    vscode.commands.registerCommand('algobattle.openProblem', (problem) => {
      if (auth && cache && problemsApi && notifications) {
        return openProblemCommand(auth, cache, problemsApi, notifications, { problem });
      }
      return undefined;
    }),
    vscode.commands.registerCommand('algobattle.pickProblem', async () => {
      if (auth && cache && problemsApi && notifications) {
        await openProblemCommand(auth, cache, problemsApi, notifications);
      }
    }),
    vscode.commands.registerCommand('algobattle.runTests', () => {
      if (auth && problemsApi && submissionsApi && notifications && outputChannel) {
        return runTestsCommand(auth, problemsApi, submissionsApi, notifications, outputChannel);
      }
      return undefined;
    }),
    vscode.commands.registerCommand('algobattle.submit', () => {
      if (auth && problemsApi && submissionsApi && notifications && outputChannel) {
        return submitCommand(auth, problemsApi, submissionsApi, notifications, outputChannel, context);
      }
      return undefined;
    }),
    vscode.commands.registerCommand('algobattle.showLeaderboard', (contestId) => {
      if (auth && cache && leaderboardsApi && contestsApi && notifications) {
        return showLeaderboardCommand(
          context,
          auth,
          cache,
          leaderboardsApi,
          contestsApi,
          notifications,
          typeof contestId === 'string' ? contestId : undefined,
        );
      }
      return undefined;
    }),
    vscode.commands.registerCommand('algobattle.contestJoin', () => {
      if (auth && cache && contestsApi && notifications) {
        return contestJoinCommand(auth, cache, contestsApi, notifications);
      }
      return undefined;
    }),
    vscode.commands.registerCommand('algobattle.setApiUrl', () => {
      if (config && notifications) return setApiUrlCommand(config, notifications);
      return undefined;
    }),
  );

  // Kick off background loads.
  await auth.load();
  problemTree.refresh();
  contestTree.refresh();

  await vscode.commands.executeCommand('setContext', 'algobattle.authed', auth.snapshot().authenticated);
  output.info('Algobattle activated');
}

export function deactivate(): void {
  outputChannel?.info('Algobattle deactivated');
  problemTree?.dispose();
  codeLens = undefined;
  statusBar?.dispose();
  outputChannel?.dispose();
  outputChannel = undefined;
}
