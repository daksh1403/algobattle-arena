/**
 * ProblemStatusBarProvider — small persistent status bar entry that
 * surfaces Algobattle commands on the bottom-right when an editor
 * for a problem file is active.
 */

import * as vscode from 'vscode';
import { slugFromAlgobattlePath } from '../util/problem-storage';

export class ProblemStatusBarProvider implements vscode.Disposable {
  private readonly testItem: vscode.StatusBarItem;
  private readonly submitItem: vscode.StatusBarItem;
  private readonly boardItem: vscode.StatusBarItem;

  constructor() {
    this.testItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    this.testItem.command = 'algobattle.runTests';
    this.testItem.text = '$(play) Algobattle: Test';
    this.testItem.tooltip = 'Run sample tests (Ctrl+Shift+T)';

    this.submitItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 99);
    this.submitItem.command = 'algobattle.submit';
    this.submitItem.text = '$(check) Algobattle: Submit';
    this.submitItem.tooltip = 'Submit to judge (Ctrl+Shift+S)';

    this.boardItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 98);
    this.boardItem.command = 'algobattle.showLeaderboard';
    this.boardItem.text = '$(trophy) Leaderboard';
    this.boardItem.tooltip = 'Open leaderboard';
  }

  bind(): void {
    vscode.window.onDidChangeActiveTextEditor((editor) => this.update(editor));
  }

  update(editor: vscode.TextEditor | undefined): void {
    if (editor && slugFromAlgobattlePath(editor.document.uri)) {
      this.testItem.show();
      this.submitItem.show();
    } else {
      this.testItem.hide();
      this.submitItem.hide();
    }
    // The leaderboard item is always visible.
    this.boardItem.show();
  }

  dispose(): void {
    this.testItem.dispose();
    this.submitItem.dispose();
    this.boardItem.dispose();
  }
}
