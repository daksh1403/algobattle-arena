/* eslint-disable no-undef */
/**
 * leaderboard-main.js — renders a live leaderboard.
 *
 * Initial state comes from `window.__INITIAL_STATE__`. Subsequent updates
 * are posted by the extension host via `window` message events of type
 *   { type: 'update', entries: LeaderboardEntry[] }
 *   { type: 'status', status: 'connected' | 'reconnecting' | 'disconnected' }
 */
(function () {
  const state = window.__INITIAL_STATE__ || { contest: { title: 'Contest' }, entries: [] };
  const el = (id) => document.getElementById(id);

  el('title').textContent = state.contest?.title || 'Leaderboard';

  let prev = new Map();
  function render(entries) {
    const tbody = el('rows');
    const empty = el('empty');
    if (!Array.isArray(entries) || entries.length === 0) {
      tbody.innerHTML = '';
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    const sorted = [...entries].sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9));
    const next = new Map();
    const rows = sorted.map((e) => {
      next.set(e.user_id, e.rank ?? 0);
      const upDown = deltaBadge(prev.get(e.user_id), e.rank);
      const tr = document.createElement('tr');
      tr.dataset.userId = e.user_id;
      const rank = e.rank ?? '—';
      const rankClass = rank === 1 ? 'rank-1' : rank === 2 ? 'rank-2' : rank === 3 ? 'rank-3' : '';
      tr.innerHTML = `
        <td class="rank ${rankClass}">${escape(String(rank))}${upDown}</td>
        <td>${escape(e.username || '')}</td>
        <td>${escape(formatNum(e.score))}</td>
        <td>${escape(formatNum(e.solved_count))}</td>
        <td>${escape(formatNum(e.penalty))}</td>
        <td>${escape(formatNum(e.rating))}</td>
      `;
      return tr;
    });
    tbody.innerHTML = '';
    for (const tr of rows) {
      tbody.appendChild(tr);
      tr.classList.add('flash');
    }
    prev = next;
  }

  function formatNum(n) {
    if (typeof n !== 'number') return '—';
    return Number.isInteger(n) ? String(n) : n.toFixed(2);
  }

  function deltaBadge(prevRank, nextRank) {
    if (typeof prevRank !== 'number' || typeof nextRank !== 'number') return '';
    if (prevRank === nextRank) return '';
    if (nextRank < prevRank) return ` <span class="delta-up">▲${prevRank - nextRank}</span>`;
    return ` <span class="delta-down">▼${nextRank - prevRank}</span>`;
  }

  function escape(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  window.addEventListener('message', (ev) => {
    const msg = ev.data;
    if (!msg || typeof msg !== 'object') return;
    if (msg.type === 'update') {
      render(msg.entries || []);
    } else if (msg.type === 'status') {
      const map = { connected: '🟢 Connected', reconnecting: '🟡 Reconnecting…', disconnected: '⚪ Disconnected' };
      el('status').textContent = map[msg.status] || msg.status;
    }
  });

  render(state.entries || []);
})();
