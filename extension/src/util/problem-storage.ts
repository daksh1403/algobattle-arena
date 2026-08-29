/**
 * problem-storage.ts — manage the `.algobattle/<slug>/` folder in a workspace.
 *
 * Each opened problem lives in a sub-folder with:
 *   .algobattle/<slug>/starter.<ext>     ← user's working solution
 *   .algobattle/<slug>/problem.json      ← local cache of last-known detail
 *
 * All filesystem operations are async and surface typed errors.
 */

import * as fs from 'fs/promises';
import * as path from 'path';
import * as vscode from 'vscode';
import type { ProblemDetail, SupportedLanguage } from '../api/types';
import { LANGUAGES, defaultStarterCode, fromApiId } from './languages';

export const ALGOBATTLE_DIR = '.algobattle';

export interface ProblemWorkspacePaths {
  readonly root: vscode.Uri;
  readonly dir: vscode.Uri;
  readonly starter: vscode.Uri;
  readonly meta: vscode.Uri;
}

export interface ScaffoldResult {
  readonly paths: ProblemWorkspacePaths;
  readonly starter: vscode.Uri;
  readonly created: boolean; // true when starter file did not exist before
}

/**
 * Returns the workspace folders that should be considered for problem storage.
 * Empty array when no folder is open.
 */
export function workspaceFolders(): readonly vscode.WorkspaceFolder[] {
  return vscode.workspace.workspaceFolders ?? [];
}

/**
 * Pick the first open workspace folder; throws a friendly error otherwise.
 */
export function requireWorkspaceRoot(): vscode.WorkspaceFolder {
  const folders = workspaceFolders();
  if (folders.length === 0) {
    throw new Error('No workspace folder is open. Open a folder before opening a problem.');
  }
  return folders[0]!;
}

function pathFor(folder: vscode.WorkspaceFolder, ...parts: string[]): vscode.Uri {
  return vscode.Uri.joinPath(folder.uri, ...parts);
}

/** Build the canonical paths for a given problem slug. */
export function pathsFor(slug: string, folder: vscode.WorkspaceFolder): ProblemWorkspacePaths {
  const dir = pathFor(folder, ALGOBATTLE_DIR, slug);
  return {
    root: pathFor(folder, ALGOBATTLE_DIR),
    dir,
    starter: pathFor(folder, ALGOBATTLE_DIR, slug, 'starter'), // suffix added per language
    meta: pathFor(folder, ALGOBATTLE_DIR, slug, 'problem.json'),
  };
}

export interface ScaffoldOptions {
  /** Force a particular starter filename; otherwise inferred from descriptor. */
  preferred?: SupportedLanguage;
}

/**
 * Create (or reuse) the per-problem scaffold inside the workspace.
 * When the starter file already exists it is left untouched and `created=false`.
 */
export async function scaffoldProblem(
  detail: ProblemDetail,
  folder: vscode.WorkspaceFolder,
  opts: ScaffoldOptions = {},
): Promise<ScaffoldResult> {
  const paths = pathsFor(detail.slug, folder);
  const starterLang = pickLanguage(detail, opts.preferred);
  const starterUri = withExt(paths.starter, starterLang.extension);

  await fs.mkdir(paths.dir.fsPath, { recursive: true });

  let created = false;
  try {
    await fs.access(starterUri.fsPath);
  } catch {
    const starter = starterFor(detail, starterLang.apiId);
    await fs.writeFile(starterUri.fsPath, starter, 'utf8');
    created = true;
  }

  // Persist a local cache of the problem metadata; ignore write errors.
  try {
    const json = JSON.stringify(
      {
        id: detail.id,
        slug: detail.slug,
        title: detail.title,
        difficulty: detail.difficulty,
        language: starterLang.apiId,
        synced_at: new Date().toISOString(),
      },
      null,
      2,
    );
    await fs.writeFile(paths.meta.fsPath, json, 'utf8');
  } catch {
    /* non-fatal — cache is best-effort */
  }

  return { paths: { ...paths, starter: starterUri }, starter: starterUri, created };
}

/** Return the language descriptor best matching the problem's starter_code map. */
function pickLanguage(detail: ProblemDetail, preferred?: SupportedLanguage): NonNullable<ReturnType<typeof fromApiId>> {
  if (preferred) {
    const desc = fromApiId(preferred);
    if (desc) return desc;
  }
  // Pick the first language that has a starter code entry.
  for (const lang of LANGUAGES) {
    if (detail.starter_code && detail.starter_code[lang.apiId]) {
      return lang;
    }
  }
  return LANGUAGES[0];
}

/**
 * Build a starter file's content by combining problem-specific starter code with
 * a permissive fallback derived from `defaultStarterCode`.
 */
function starterFor(detail: ProblemDetail, apiId: SupportedLanguage): string {
  const fromProblem = detail.starter_code?.[apiId];
  if (typeof fromProblem === 'string' && fromProblem.length > 0) return fromProblem;
  const desc = fromApiId(apiId);
  return desc ? defaultStarterCode(desc) : '';
}

function withExt(uri: vscode.Uri, ext: string): vscode.Uri {
  if (uri.fsPath.endsWith(ext)) return uri;
  return vscode.Uri.file(uri.fsPath + ext);
}

/**
 * Read the user-authored solution from disk. If the file does not exist, returns
 * an empty string — caller decides whether to surface this.
 */
export async function readSolution(uri: vscode.Uri): Promise<string> {
  try {
    return await fs.readFile(uri.fsPath, 'utf8');
  } catch (err) {
    if (isNotFound(err)) return '';
    throw err;
  }
}

/**
 * Persist the active editor's code back to its scaffold starter file.
 * Returns `true` on success.
 */
export async function writeSolution(uri: vscode.Uri, code: string): Promise<boolean> {
  try {
    await fs.writeFile(uri.fsPath, code, 'utf8');
    return true;
  } catch {
    return false;
  }
}

/** Locate the .algobattle directory given any file path inside it. */
export function findAlgobattleRoot(fileUri: vscode.Uri): vscode.Uri | undefined {
  const parts = fileUri.fsPath.split(path.sep);
  const idx = parts.lastIndexOf(ALGOBATTLE_DIR);
  if (idx < 0) return undefined;
  return vscode.Uri.file(parts.slice(0, idx + 1).join(path.sep));
}

/** Extract problem slug from a `.algobattle/<slug>/...` path. */
export function slugFromAlgobattlePath(fileUri: vscode.Uri): string | undefined {
  const parts = fileUri.fsPath.split(path.sep);
  const idx = parts.lastIndexOf(ALGOBATTLE_DIR);
  if (idx < 0 || idx + 1 >= parts.length) return undefined;
  return parts[idx + 1];
}

function isNotFound(err: unknown): boolean {
  return typeof err === 'object' && err !== null && (err as { code?: string }).code === 'ENOENT';
}
