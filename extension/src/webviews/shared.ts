/**
 * shared.ts — utility for rendering HTML into WebView panels with a
 * strict Content-Security-Policy and a uniform nonce.
 *
 * Inlines the script via a `<script>` tag with `nonce=<value>` so that
 * inline event handlers and JSON-bridged state work safely.
 */

import * as vscode from 'vscode';

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function nonce(): string {
  const data = new Uint8Array(16);
  // node:crypto is not available in the renderer; use WebCrypto via getRandomValues.
  // Fall back to Math.random if WebCrypto is unavailable (older webviews).
  if (typeof globalThis.crypto?.getRandomValues === 'function') {
    globalThis.crypto.getRandomValues(data);
  } else {
    for (let i = 0; i < data.length; i++) data[i] = Math.floor(Math.random() * 256);
  }
  return Array.from(data)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export function safeAttr(value: string): string {
  return escapeHtml(value);
}

export interface RenderOptions {
  title: string;
  body: string;
  /** Optional inline `<style>` content. */
  styles?: string;
  /** Optional initial state serialized as JSON and exposed as `window.__INITIAL_STATE__`. */
  initialState?: unknown;
  /** Optional script source code; will be inlined with the CSP nonce. */
  script?: string;
  /** Optional list of additional resource roots (e.g. fonts). */
  additionalRoots?: vscode.Uri[];
}

export function renderWebviewHtml(options: RenderOptions): string {
  const n = nonce();
  const title = escapeHtml(options.title);
  const initial = options.initialState === undefined ? 'undefined' : safeJson(options.initialState);

  const styleBlock = options.styles
    ? `<style nonce="${n}">${options.styles}</style>`
    : '';
  const scriptBlock = options.script
    ? `<script nonce="${n}">${options.script}</script>`
    : '';

  // Inline bootstrap script exposes the initial state.
  const bootstrap = `<script nonce="${n}">window.__INITIAL_STATE__ = ${initial};</script>`;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline' ${n ? `'nonce-${n}'` : ''}; script-src 'nonce-${n}'; font-src 'self' data:; connect-src 'self';" />
  <title>${title}</title>
  ${styleBlock}
</head>
<body>
${options.body}
${bootstrap}
${scriptBlock}
</body>
</html>`;
}

function safeJson(value: unknown): string {
  // Escape JSON-unsafe characters so the resulting literal can be embedded
  // inside a `<script>` tag without breaking HTML/JS parsing.
  // U+2028 (LINE SEPARATOR) and U+2029 (PARAGRAPH SEPARATOR) are valid JSON
  // characters but illegal in ECMAScript string literals; this makes the
  // generated HTML safe to eval as JSON inside the WebView.
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(new RegExp('\\u2028', 'g'), '\\u2028')
    .replace(new RegExp('\\u2029', 'g'), '\\u2029');
}

/** Render a Markdown string to a minimal HTML subset using Markdown-it. */
export async function renderMarkdown(md: string): Promise<string> {
  // Lazy require so tests can stub `markdown-it`.
  // `markdown-it` ships as CommonJS; the interop shape varies by bundler.
  interface MarkdownItCtor {
    new (options?: Record<string, unknown>): { render: (src: string) => string };
  }
  const mod: unknown = await import('markdown-it');
  const ctor = (mod as { default?: MarkdownItCtor }).default ??
    (mod as MarkdownItCtor);
  const engine = new ctor({ html: false, linkify: true, breaks: true });
  return engine.render(md);
}
