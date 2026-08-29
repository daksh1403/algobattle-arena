/* eslint-disable no-undef */
/**
 * Problem-detail webview script.
 * Reads window.__INITIAL_STATE__ (injected by the extension) and renders
 * the sidebar tree. Talks to the extension host via acquireVsCodeApi().
 */
(function () {
  const vscode = acquireVsCodeApi();
  const state = window.__INITIAL_STATE__ || { problems: [] };
  const el = (id) => document.getElementById(id);

  /** @type {{problems: Array<{id:string,slug:string,title:string,difficulty:string}>}} */
  const ctx = { problems: state.problems || [], selectedSlug: state.selectedSlug || null, detail: null };

  function renderSidebar() {
    const sections = { easy: 'Easy', medium: 'Medium', hard: 'Hard' };
    const order = ['easy', 'medium', 'hard'];
    const root = el('sections');
    root.innerHTML = '';
    if (ctx.problems.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = 'No problems loaded yet. Try Sign in → Browse Problems.';
      root.appendChild(empty);
      return;
    }
    for (const key of order) {
      const list = ctx.problems.filter((p) => p.difficulty === key);
      if (list.length === 0) continue;
      const section = document.createElement('section');
      section.className = 'section';
      const heading = document.createElement('h2');
      heading.textContent = `${sections[key]} (${list.length})`;
      heading.addEventListener('click', () => section.classList.toggle('open'));
      section.appendChild(heading);
      const ul = document.createElement('ul');
      for (const p of list) {
        const li = document.createElement('li');
        li.className = `diff-${p.difficulty}`;
        if (p.slug === ctx.selectedSlug) li.classList.add('selected');
        li.textContent = p.title;
        li.addEventListener('click', () => {
          ctx.selectedSlug = p.slug;
          renderSidebar();
          vscode.postMessage({ type: 'select', slug: p.slug });
        });
        ul.appendChild(li);
      }
      section.classList.add('open');
      section.appendChild(ul);
      root.appendChild(section);
    }
  }

  function showDetail(detail) {
    ctx.detail = detail;
    el('placeholder').hidden = true;
    el('detail').hidden = false;
    el('title').textContent = detail.title;
    const badge = el('difficulty');
    badge.className = `difficulty ${detail.difficulty}`;
    badge.textContent = detail.difficulty;
    el('statement').innerHTML = detail.statement_html || `<p>${escape(detail.statement_md || '')}</p>`;
    const samples = el('samples');
    samples.innerHTML = '';
    for (const s of detail.samples || []) {
      const li = document.createElement('li');
      const inp = document.createElement('strong');
      inp.textContent = 'Input:';
      const out = document.createElement('strong');
      out.textContent = 'Output:';
      const ipre = document.createElement('pre');
      ipre.textContent = s.input;
      const opre = document.createElement('pre');
      opre.textContent = s.expected_output;
      li.append(inp, ipre, out, opre);
      if (s.explanation) {
        const exp = document.createElement('p');
        exp.textContent = s.explanation;
        li.appendChild(exp);
      }
      samples.appendChild(li);
    }
    el('code').value = detail.code || '';
    el('results').hidden = true;
    el('result-list').innerHTML = '';
    el('status').textContent = '';
  }

  function showResults(results, verdict) {
    const wrap = el('result-list');
    wrap.innerHTML = '';
    el('results').hidden = false;
    if (!results || results.length === 0) {
      const li = document.createElement('li');
      li.textContent = `Verdict: ${verdict}`;
      wrap.appendChild(li);
      el('status').textContent = verdict;
      return;
    }
    results.forEach((r, idx) => {
      const li = document.createElement('li');
      li.className = `verdict-${r.verdict}`;
      const head = document.createElement('strong');
      head.textContent = `Test #${idx + 1}: ${r.verdict}`;
      li.appendChild(head);
      if (typeof r.runtime_ms === 'number') {
        const meta = document.createElement('div');
        meta.textContent = `${r.runtime_ms}ms`;
        li.appendChild(meta);
      }
      if (r.actual_output !== undefined) {
        const label = document.createElement('div');
        label.textContent = 'Got:';
        const pre = document.createElement('pre');
        pre.textContent = r.actual_output;
        li.append(label, pre);
      }
      if (r.expected_output !== undefined) {
        const label = document.createElement('div');
        label.textContent = 'Expected:';
        const pre = document.createElement('pre');
        pre.textContent = r.expected_output;
        li.append(label, pre);
      }
      if (r.message) {
        const pre = document.createElement('pre');
        pre.textContent = r.message;
        li.appendChild(pre);
      }
      wrap.appendChild(li);
    });
    el('status').textContent = `${results.length} tests · ${verdict}`;
  }

  function escape(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  el('search').addEventListener('input', (ev) => {
    const q = ev.target.value.toLowerCase();
    const items = Array.from(document.querySelectorAll('.section li'));
    for (const it of items) {
      it.style.display = it.textContent.toLowerCase().includes(q) ? '' : 'none';
    }
  });

  el('run-btn').addEventListener('click', () => {
    if (!ctx.detail) return;
    el('status').textContent = 'Running…';
    el('run-btn').disabled = true;
    vscode.postMessage({ type: 'run', slug: ctx.detail.slug, code: el('code').value });
  });

  el('submit-btn').addEventListener('click', () => {
    if (!ctx.detail) return;
    el('status').textContent = 'Submitting…';
    el('submit-btn').disabled = true;
    vscode.postMessage({ type: 'submit', slug: ctx.detail.slug, code: el('code').value });
  });

  window.addEventListener('message', (ev) => {
    const msg = ev.data;
    if (!msg || typeof msg !== 'object') return;
    if (msg.type === 'detail') {
      showDetail(msg.detail);
    } else if (msg.type === 'problems') {
      ctx.problems = msg.problems || [];
      renderSidebar();
    } else if (msg.type === 'run-result' || msg.type === 'submit-result') {
      el('run-btn').disabled = false;
      el('submit-btn').disabled = false;
      showResults(msg.results, msg.verdict);
    } else if (msg.type === 'error') {
      el('run-btn').disabled = false;
      el('submit-btn').disabled = false;
      el('status').textContent = msg.message;
    }
  });

  renderSidebar();
})();
