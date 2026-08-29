/**
 * AlgoBattle API Worker + Static Frontend
 * =======================================
 * Deploys to Cloudflare Workers with [assets] + KV bindings.
 *
 * Architecture:
 *   Browser → Cloudflare Worker
 *                ├─ serves static frontend (env.ASSETS)
 *                ├─ /health — always online (edge)
 *                ├─ /api/leaderboard — reads from KV (cloud-persistent)
 *                ├─ /api/submit — proxies to judge backend via tunnel, caches to KV
 *                └─ /api/submissions — full history from KV
 *
 * Cloudflare Workers cannot run compilers, so the sandbox runs behind a
 * cloudflared tunnel. The leaderboard is cloud-persistent in KV, so it
 * survives backend restarts and stays visible even when judging is offline.
 */

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Max-Age': '86400',
};

const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'no-referrer',
};

const JSON_HEADERS = { 'Content-Type': 'application/json', ...CORS_HEADERS };
const KV_KEY = 'arena:submissions';

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

async function getSubmissions(env) {
  try {
    const raw = await env.ALGOBATTLE.get(KV_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

async function saveSubmissions(env, subs) {
  try {
    await env.ALGOBATTLE.put(KV_KEY, JSON.stringify(subs));
  } catch (e) {
    // best-effort
  }
}

function rank(subs) {
  // Sort: score desc (numeric), efficiency asc, then id asc
  const scored = subs.map(s => ({ ...s, _scoreNum: parseInt(s.score, 10) || 0 }));
  scored.sort((a, b) =>
    b._scoreNum - a._scoreNum ||
    a.efficiency - b.efficiency ||
    a.id - b.id
  );
  return scored.map((s, i) => ({ ...s, rank: i + 1 }));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // ---- SSE live standings: pass through as a real stream ----
    if (url.pathname.endsWith('/standings/stream')) {
      const origin = env.TUNNEL_URL || env.BACKEND_URL || 'http://127.0.0.1:8080';
      try {
        const target = new URL(url.pathname + url.search, origin);
        const headers = new Headers(request.headers);
        headers.set('Host', new URL(origin).host);
        const upstream = await fetch(target.toString(), {
          method: 'GET',
          headers,
          redirect: 'follow',
        });
        const respHeaders = new Headers(upstream.headers);
        respHeaders.set('Content-Type', 'text/event-stream');
        respHeaders.set('Cache-Control', 'no-cache');
        respHeaders.set('X-Accel-Buffering', 'no');
        Object.entries(CORS_HEADERS).forEach(([k, v]) => respHeaders.set(k, v));
        return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
      } catch (e) {
        return json({ error: 'judge_backend_unreachable' }, 502);
      }
    }

    // ---- Generic backend proxy for API routes ----
    // Auth, contests, standings, plagiarism, problems, compiler, submit
    // all live on the judge backend (tunnel). When it's unreachable, the
    // KV-backed endpoints (/health, /api/leaderboard, /api/submissions)
    // still respond from the edge.
    const backendOnly = url.pathname.startsWith('/api/') && ![
      '/api/leaderboard', '/api/submissions',
    ].includes(url.pathname);
    if (backendOnly || url.pathname === '/health') {
      const origin = env.TUNNEL_URL || env.BACKEND_URL || 'http://127.0.0.1:8080';
      try {
        const target = new URL(url.pathname + url.search, origin);
        const headers = new Headers(request.headers);
        headers.set('Host', new URL(origin).host);
        const upstream = await fetch(target.toString(), {
          method: request.method,
          headers,
          body: request.method === 'GET' ? undefined : await request.arrayBuffer(),
          redirect: 'follow',
        });
        const body = await upstream.arrayBuffer();
        // Tunnel-up but backend is dead: 404 with empty body. Surface as 502.
        if (upstream.status === 404 && body.byteLength === 0){
          return json({ error: 'judge_backend_unreachable',
                        detail: 'Judge sandbox is offline. Restart the Codespace judge.' }, 502);
        }
        const respHeaders = new Headers(upstream.headers);
        Object.entries(CORS_HEADERS).forEach(([k, v]) => respHeaders.set(k, v));
        Object.entries(SECURITY_HEADERS).forEach(([k, v]) => respHeaders.set(k, v));
        return new Response(body, { status: upstream.status, headers: respHeaders });
      } catch (e) {
        // Fall back to edge-only behavior for health/leaderboard
        if (url.pathname === '/health') {
          const subs = await getSubmissions(env);
          return json({ status: 'degraded', app: 'algobattle', worker: 'online',
                        backend: 'offline', submissions: subs.length });
        }
        return json({ error: 'judge_backend_unreachable',
                      detail: 'Judge sandbox is offline. Restart the Codespace judge.' }, 502);
      }
    }

    // Health — always online at the edge
    if (url.pathname === '/health') {
      const subs = await getSubmissions(env);
      return json({ status: 'ok', app: 'algobattle', worker: 'online',
                    submissions: subs.length });
    }

    // Leaderboard — cloud-persistent, works even when judge is offline
    if (url.pathname === '/api/leaderboard') {
      const subs = await getSubmissions(env);
      return json(rank(subs));
    }

    // Submission history
    if (url.pathname === '/api/submissions') {
      const subs = await getSubmissions(env);
      subs.sort((a, b) => b.id - a.id);
      return json(subs.slice(0, 100));
    }

    // Submit — proxy to judge backend, then persist result to KV
    if (url.pathname === '/api/submit' && request.method === 'POST') {
      const origin = env.TUNNEL_URL || env.BACKEND_URL || 'http://127.0.0.1:8080';

      // Forward to the judge backend
      let upstream;
      try {
        const target = new URL('/api/submit', origin);
        const headers = new Headers(request.headers);
        headers.set('Host', new URL(origin).host);
        upstream = await fetch(target.toString(), {
          method: 'POST',
          headers,
          body: await request.arrayBuffer(),
          redirect: 'follow',
        });
      } catch (e) {
        return json({ error: 'judge_backend_unreachable',
                      detail: 'Judge sandbox is offline. Start it and tunnel it.' }, 502);
      }

      const result = await upstream.json();

      // Persist accepted/rejected submissions to KV leaderboard
      if (result && result.verdict) {
        const subs = await getSubmissions(env);
        const id = subs.reduce((m, s) => Math.max(m, s.id || 0), 0) + 1;
        subs.push({
          id,
          participant: result.participant || 'Anonymous',
          problem: result.problem_slug || 'unknown',
          language: result.language || 'python',
          verdict: result.verdict,
          score: result.score || '0/0',
          efficiency: result.efficiency ?? 99,
          runtime_ms: result.runtime_ms || 0,
          cpu_time_ms: result.cpu_time_ms || 0,
          created_at: Date.now(),
        });
        await saveSubmissions(env, subs);
        result.submission_id = id;
      }

      return new Response(JSON.stringify(result), {
        status: upstream.status,
        headers: JSON_HEADERS,
      });
    }

    // Compiler — dedicated Programiz-style endpoint (no scoring, no KV)
    if (url.pathname === '/api/compiler/run' && request.method === 'POST') {
      const origin = env.TUNNEL_URL || env.BACKEND_URL || 'http://127.0.0.1:8080';
      try {
        const target = new URL('/api/compiler/run', origin);
        const headers = new Headers(request.headers);
        headers.set('Host', new URL(origin).host);
        const upstream = await fetch(target.toString(), {
          method: 'POST',
          headers,
          body: await request.arrayBuffer(),
          redirect: 'follow',
        });
        const body = await upstream.arrayBuffer();
        const respHeaders = new Headers(upstream.headers);
        Object.entries(CORS_HEADERS).forEach(([k, v]) => respHeaders.set(k, v));
        return new Response(body, { status: upstream.status, headers: respHeaders });
      } catch (e) {
        return json({ error: 'compiler_backend_unreachable',
                      detail: 'The judge sandbox is offline. Start the backend and tunnel it.' }, 502);
      }
    }

    // Backwards-compat alias
    if (url.pathname === '/api/run' && request.method === 'POST') {
      const origin = env.TUNNEL_URL || env.BACKEND_URL || 'http://127.0.0.1:8080';
      try {
        const target = new URL('/api/run', origin);
        const headers = new Headers(request.headers);
        headers.set('Host', new URL(origin).host);
        const upstream = await fetch(target.toString(), {
          method: 'POST',
          headers,
          body: await request.arrayBuffer(),
          redirect: 'follow',
        });
        const body = await upstream.arrayBuffer();
        const respHeaders = new Headers(upstream.headers);
        Object.entries(CORS_HEADERS).forEach(([k, v]) => respHeaders.set(k, v));
        return new Response(body, { status: upstream.status, headers: respHeaders });
      } catch (e) {
        return json({ error: 'judge_backend_unreachable',
                      detail: 'Judge sandbox is offline. Start it and tunnel it.' }, 502);
      }
    }

    // Custom problems — proxy all /api/problems/* and /api/submit/custom to backend
    if (url.pathname.startsWith('/api/problems/') || url.pathname === '/api/submit/custom') {
      const origin = env.TUNNEL_URL || env.BACKEND_URL || 'http://127.0.0.1:8080';
      try {
        const target = new URL(url.pathname + url.search, origin);
        const headers = new Headers(request.headers);
        headers.set('Host', new URL(origin).host);
        const upstream = await fetch(target.toString(), {
          method: request.method,
          headers,
          body: request.method === 'GET' ? undefined : await request.arrayBuffer(),
          redirect: 'follow',
        });
        const body = await upstream.arrayBuffer();

        // Persist custom submissions to KV leaderboard too
        if (url.pathname === '/api/submit/custom' && request.method === 'POST') {
          try {
            const text = new TextDecoder().decode(body);
            const result = JSON.parse(text);
            if (result && result.verdict) {
              const subs = await getSubmissions(env);
              const id = subs.reduce((m, s) => Math.max(m, s.id || 0), 0) + 1;
              subs.push({
                id,
                participant: result.participant || 'Anonymous',
                problem: result.problem_slug || 'custom',
                language: result.language || 'python',
                verdict: result.verdict,
                score: result.score || '0/0',
                efficiency: result.efficiency ?? 99,
                runtime_ms: result.runtime_ms || 0,
                cpu_time_ms: result.cpu_time_ms || 0,
                created_at: Date.now(),
              });
              await saveSubmissions(env, subs);
            }
          } catch (e) { /* best-effort */ }
        }

        const respHeaders = new Headers(upstream.headers);
        Object.entries(CORS_HEADERS).forEach(([k, v]) => respHeaders.set(k, v));
        return new Response(body, { status: upstream.status, headers: respHeaders });
      } catch (e) {
        return json({ error: 'judge_backend_unreachable',
                      detail: 'Judge sandbox is offline. Start it and tunnel it.' }, 502);
      }
    }

    // Static frontend from the [assets] binding
    if (env.ASSETS && typeof env.ASSETS.fetch === 'function') {
      const res = await env.ASSETS.fetch(request);
      const headers = new Headers(res.headers);
      Object.entries(SECURITY_HEADERS).forEach(([k, v]) => headers.set(k, v));
      return new Response(res.body, { status: res.status, headers });
    }

    return new Response('AlgoBattle Arena', { headers: { 'Content-Type': 'text/plain' } });
  },
};
