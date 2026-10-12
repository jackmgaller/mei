// The workboard page: polls /api/state and draws one of five views. No libraries.
'use strict';

const POLL_MS = 5000;
const OLD_HOURS = 3;            // finished cards older than this are hidden unless asked
const STATE_LABEL = {queued: 'Queued', working: 'Working', blocked: 'Blocked', review: 'Review',
                     done: 'Done', merged: 'Merged', stopped: 'Stopped'};
let snap = null;
let ui = loadUi();
let openCard = null;

function loadUi() {
  const d = {view: 'board', filter: '', group: '', showOld: false, assetGroup: 'level', assetState: '',
             showCol: false, world: ''};
  try { return Object.assign(d, JSON.parse(localStorage.getItem('workboard') || '{}')); } catch (e) { return d; }
}
function saveUi() { try { localStorage.setItem('workboard', JSON.stringify(ui)); } catch (e) { /* private window */ } }

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const now = () => Date.now() / 1000;

function ago(t) {
  if (!t) return '-';
  const s = Math.max(0, now() - t);
  if (s < 90) return Math.round(s) + 's';
  if (s < 5400) return Math.round(s / 60) + 'm';
  if (s < 172800) return (s / 3600).toFixed(1) + 'h';
  return Math.round(s / 86400) + 'd';
}
function dur(s) {
  if (s == null || s < 0) return '-';
  if (s < 5400) return Math.round(s / 60) + 'm';
  return (s / 3600).toFixed(1) + 'h';
}
function clock(t) {
  if (!t) return '-';
  const d = new Date(t * 1000);
  return d.toLocaleDateString(undefined, {month: 'short', day: 'numeric'}) + ' ' +
         d.toLocaleTimeString(undefined, {hour: '2-digit', minute: '2-digit'});
}
function hue(str) {
  let h = 0;
  for (const c of String(str)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % 360;
}
function cardColour(key) { return `hsl(${hue(key)} 55% 45%)`; }
function modelBadge(m) {
  const k = (m || '').toLowerCase();
  const cls = ['opus', 'sonnet', 'haiku'].find((x) => k.includes(x)) || 'unknown';
  return `<span class="b model ${cls}" title="model">${esc(m || 'model ?')}</span>`;
}
function cardFinished(c) { return ['done', 'merged', 'stopped'].includes(c.state); }

function visibleCards() {
  if (!snap) return [];
  const f = ui.filter.trim().toLowerCase();
  return snap.agents.filter((c) => {
    if (ui.group && c.group !== ui.group) return false;
    if (!ui.showOld && cardFinished(c) && now() - (c.activity || 0) > OLD_HOURS * 3600) return false;
    if (!f) return true;
    return [c.title, c.branch, c.kind, c.model, c.lead, c.key, c.id, c.step, c.state]
      .some((x) => String(x || '').toLowerCase().includes(f));
  });
}

async function poll() {
  try {
    const r = await fetch('/api/state', {cache: 'no-store'});
    snap = await r.json();
  } catch (e) {
    $('#clock').textContent = 'server unreachable';
    return;
  }
  render();
}

function render() {
  if (!snap || !snap.agents) return;
  const groups = [...new Set(snap.agents.map((c) => c.group))].sort();
  const sel = $('#group');
  const cur = ui.group;
  sel.innerHTML = '<option value="">All batches</option>' +
    groups.map((g) => `<option ${g === cur ? 'selected' : ''}>${esc(g)}</option>`).join('');
  const open = snap.questions.filter((q) => !q.answer);
  $('#qcount').textContent = open.length || '';
  $('#clock').textContent = 'scanned ' + ago(snap.generated) + ' ago';
  const cards = visibleCards();
  const by = (s) => cards.filter((c) => c.state === s).length;
  const staleN = cards.filter((c) => c.stale).length;
  const running = cards.filter((c) => c.git.running).length;
  $('#summary').innerHTML =
    `<span><b>${cards.length}</b> shown of ${snap.agents.length} agents (${snap.worktrees_total} worktrees)</span>` +
    `<span><b>${by('working')}</b> working, <b>${running}</b> with a live process</span>` +
    `<span><b>${by('blocked')}</b> blocked</span><span><b>${by('review')}</b> in review</span>` +
    (staleN ? `<span><b style="color:var(--warn)">${staleN}</b> stale (no activity for ${snap.stale_minutes} min)</span>` : '') +
    `<span><b>${open.length}</b> open questions</span>` +
    `<span class="muted">scan ${snap.took}s</span>` +
    (snap.error ? `<span class="err">scan failed: ${esc(snap.error)}</span>` : '');
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.view === ui.view));
  const views = {board: renderBoard, assets: renderAssets, level: renderLevel, questions: renderQuestions, stats: renderStats};
  const keep = document.activeElement && document.activeElement.closest('#view form') ? document.activeElement : null;
  if (keep) return;   // don't redraw under someone typing an answer
  $('#view').innerHTML = views[ui.view]();
  if (openCard) drawCard(openCard, false);
}

/* ---------- board ---------- */
function renderBoard() {
  const cards = visibleCards();
  return '<div class="board">' + snap.states.map((s) => {
    const list = cards.filter((c) => c.state === s);
    return `<section class="col"><h3><span><span class="dot" style="background:var(--${s === 'queued' ? 'q' : s})"></span>${STATE_LABEL[s]}</span><span class="muted">${list.length}</span></h3>` +
      list.map(cardHtml).join('') + '</section>';
  }).join('') + '</div>';
}

function cardHtml(c) {
  const g = c.git;
  const step = c.step || (g.last_commit && g.commit_count ? 'last commit: ' + g.last_commit.subject : '');
  const ver = assetSummary(c.key);
  const openQ = c.questions.filter((q) => !q.answer).length;
  return `<div class="card ${c.stale ? 'stale' : ''}" data-card="${esc(c.key)}">
    <div class="t">${esc(c.title)}</div>
    <div class="badges">${modelBadge(c.model)}<span class="b">${esc(c.kind)}</span>
      ${c.reported ? '' : '<span class="b inf" title="no status record: everything here is inferred from git and the build folders">inferred</span>'}
      ${g.running ? '<span class="b run" title="the worktree is locked by a live Claude process">live</span>' : ''}
      ${c.stale ? '<span class="b stale">stale ' + ago(c.activity) + '</span>' : ''}
      ${openQ ? `<span class="b q">${openQ} question${openQ > 1 ? 's' : ''}</span>` : ''}
      ${ver}</div>
    ${step ? `<div class="step">${esc(step)}</div>` : ''}
    ${c.percent != null ? `<div class="pct" title="${c.percent}%"><i style="width:${c.percent}%"></i></div>` : ''}
    <div class="meta"><span title="last activity">${ago(c.activity)} ago</span>
      ${c.lead ? `<span>lead ${esc(c.lead)}</span>` : ''}
      ${g.commit_count ? `<span>${g.commit_count} commit${g.commit_count > 1 ? 's' : ''}</span>` : ''}
      ${g.dirty_count ? `<span>${g.dirty_count} uncommitted</span>` : ''}
      ${c.branch && c.branch !== c.title ? `<span>${esc(c.branch)}</span>` : ''}</div>
  </div>`;
}

function assetSummary(key) {
  const list = snap.assets.filter((a) => a.card === key && !a.collision);
  if (!list.length) return '';
  const pass = list.filter((a) => a.state === 'verified').length;
  const fail = list.filter((a) => a.state === 'failing').length;
  return `<span class="b" title="assets: verified / all">${pass}/${list.length} assets</span>` +
    (fail ? `<span class="b fail">${fail} failing</span>` : '');
}

/* ---------- detail drawer ---------- */
async function drawCard(key, fetchHistory = true) {
  const c = snap.agents.find((x) => x.key === key);
  if (!c) return;
  openCard = key;
  const g = c.git;
  const assets = snap.assets.filter((a) => a.card === key);
  const body = $('#drawerBody');
  const histHtml = body.dataset.key === key && !fetchHistory ? (body.querySelector('#hist') || {}).innerHTML : 'loading...';
  body.dataset.key = key;
  body.innerHTML = `<h2>${esc(c.title)}</h2>
    <div class="badges">${modelBadge(c.model)}<span class="b">${esc(c.kind)}</span><span class="b">${esc(c.state)} (${esc(c.state_source)})</span>
      ${c.stale ? '<span class="b stale">stale</span>' : ''}${g.running ? '<span class="b run">live</span>' : ''}</div>
    <div class="kv">
      <div>Status id</div><div>${c.id ? esc(c.id) : '<span class="muted">none: inferred card</span>'}</div>
      <div>Step</div><div>${esc(c.step) || '-'}</div>
      <div>Percent</div><div>${c.percent ?? '-'}</div>
      <div>Lead</div><div>${esc(c.lead) || '-'}</div>
      <div>Branch</div><div><code>${esc(c.branch) || '-'}</code></div>
      <div>Worktree</div><div><code>${esc(c.worktree) || '-'}</code></div>
      <div>Started</div><div>${clock(c.started)}</div>
      <div>Last activity</div><div>${clock(c.activity)} (${ago(c.activity)} ago)</div>
      <div>Ended</div><div>${clock(c.ended)}</div>
      <div>Inferred state</div><div>${esc(c.inferred_state)}</div>
      <div>Lock</div><div>${esc(g.locked) || '-'}</div>
      <div>Head</div><div><code>${esc(g.head) || '-'}</code>${g.merged ? ' (in ' + esc(snap.base) + ')' : ''}</div>
    </div>
    ${c.items.length ? `<h4>Items</h4><table><tr><th>Name</th><th>State</th><th>Size</th><th>Note</th></tr>${
      c.items.map((i) => `<tr><td>${esc(i.name)}</td><td>${esc(i.state)}</td><td>${esc(i.size) || ''}</td><td>${esc(i.note)}</td></tr>`).join('')}</table>` : ''}
    ${c.questions.length ? `<h4>Questions</h4>${c.questions.map((q) => `<div class="qitem ${q.answer ? 'answered' : ''}"><div class="text">${q.n}. ${esc(q.text)}</div>
      ${q.answer ? `<div class="muted">answer: ${esc(q.answer)}</div>` : ''}</div>`).join('')}` : ''}
    ${c.notes.length ? `<h4>Notes</h4>${c.notes.map((n) => `<div>${clock(n.t)} ${esc(n.text)}</div>`).join('')}` : ''}
    ${assets.length ? `<h4>Assets (${assets.length})</h4><div class="tiles">${assets.map(tileHtml).join('')}</div>` : ''}
    <h4>Commits on this branch (${g.commit_count || 0})</h4>
    ${g.commits.length ? `<table>${g.commits.map((x) => `<tr><td><code>${esc(x.sha)}</code></td><td>${esc(x.subject)}</td><td class="n">${x.files} files</td><td class="n">${ago(x.t)}</td></tr>`).join('')}</table>` : '<div class="muted">none</div>'}
    <h4>Uncommitted (${g.dirty_count})</h4>
    ${g.dirty.length ? `<div class="files">${g.dirty.map((d) => esc(d.code + ' ' + d.path)).join('<br>')}</div>` : '<div class="muted">none</div>'}
    ${c.world_reports.length ? `<h4>World reports</h4>${c.world_reports.map((w) => `<div>${esc(w.name || 'world check')}: ${w.ok ? 'ok' : 'not ok'}${w.check_ok != null ? ', World Checker ' + (w.check_ok ? 'ok' : 'failures') : ''} <span class="muted">${esc(w.report || w.check)} ${ago(w.time)} ago</span></div>`).join('')}` : ''}
    <h4>History</h4><div class="hist" id="hist">${histHtml}</div>`;
  $('#drawer').hidden = false;
  if (fetchHistory) {
    try {
      const ev = await (await fetch('/api/history?key=' + encodeURIComponent(key))).json();
      const el = $('#hist');
      if (el && openCard === key) {
        el.innerHTML = ev.map((e) => `<div>${clock(e.t)} <b>${esc(e.op)}</b> ${esc(
          Object.entries(e).filter(([k]) => !['t', 'op', 'source'].includes(k)).map(([k, v]) => k === 'text' ? v : k + '=' + v).join(' '))}
          <span class="muted">${esc(e.source)}</span></div>`).join('') || '<span class="muted">nothing yet</span>';
      }
    } catch (e) { /* server gone */ }
  }
}

/* ---------- assets ---------- */
function tileHtml(a) {
  const img = a.images.contact || a.images.cameras;
  const tri = a.triangles != null ? a.triangles : null;
  const pct = tri != null && a.budget ? Math.min(100, 100 * tri / a.budget) : null;
  const cls = pct == null ? '' : tri > a.budget ? 'over' : pct > 90 ? 'hi' : '';
  const ver = a.verify === 'pass' ? '<span class="b pass">verified</span>' : a.verify === 'fail' ? '<span class="b fail">verify failed</span>' :
    `<span class="b">${esc(a.state)}</span>`;
  return `<div class="tile" data-asset="${esc(a.card)}|${esc(a.name)}">
    <div class="img">${img ? `<img loading="lazy" src="${esc(img)}" alt="">` : 'no preview yet'}</div>
    <div class="body"><div class="name">${esc(a.name)}</div>
      <div class="badges">${ver}${a.size ? `<span class="b">${esc(a.size)}</span>` : ''}${a.collision ? '<span class="b">collision</span>' : ''}
        ${a.committed ? '<span class="b">committed</span>' : a.dirty ? '<span class="b">uncommitted</span>' : ''}</div>
      ${tri != null ? `<div class="tri"><span>${tri}${a.budget ? ' / ' + a.budget : ''} tris</span><span class="track"><i class="${cls}" style="width:${pct ?? 0}%"></i></span></div>` : ''}
    </div></div>`;
}

function renderAssets() {
  const keys = new Set(visibleCards().map((c) => c.key));
  let list = snap.assets.filter((a) => keys.has(a.card) && (ui.showCol || !a.collision));
  if (ui.assetState) list = list.filter((a) => a.state === ui.assetState);
  const cardOf = Object.fromEntries(snap.agents.map((c) => [c.key, c]));
  const keyFn = {
    level: (a) => a.level || 'no recipe',
    batch: (a) => cardOf[a.card].group,
    agent: (a) => cardOf[a.card].title,
    size: (a) => a.size || 'size unknown',
    state: (a) => a.state,
  }[ui.assetGroup];
  const groups = {};
  for (const a of list) (groups[keyFn(a)] ||= []).push(a);
  const states = ['verified', 'failing', 'built', 'recipe', 'queued', 'working', 'done', 'dropped'];
  const head = `<div class="bar">Group by <select id="assetGroup">${['level', 'batch', 'agent', 'size', 'state'].map((g) =>
      `<option ${g === ui.assetGroup ? 'selected' : ''}>${g}</option>`).join('')}</select>
    State <select id="assetState"><option value="">any</option>${states.map((s) => `<option ${s === ui.assetState ? 'selected' : ''}>${s}</option>`).join('')}</select>
    <label class="check"><input type="checkbox" id="showCol" ${ui.showCol ? 'checked' : ''}> collision assets</label>
    <span>${list.length} assets: ${list.filter((a) => a.state === 'verified').length} verified, ${list.filter((a) => a.state === 'failing').length} failing</span></div>`;
  if (!list.length) return head + '<div class="empty-note">No assets found in the shown worktrees.</div>';
  return head + Object.keys(groups).sort().map((g) => {
    const items = groups[g].sort((a, b) => (!(b.images.contact || b.images.cameras) - !(a.images.contact || a.images.cameras)) ||
      a.name.localeCompare(b.name));
    const tris = items.reduce((s, a) => s + (a.triangles || 0), 0);
    return `<div class="group"><h3>${esc(g)} <span>${items.length} assets, ${tris.toLocaleString()} triangles</span></h3>
      <div class="tiles">${items.map(tileHtml).join('')}</div></div>`;
  }).join('');
}

function showAsset(id) {
  const [card, name] = id.split('|');
  const a = snap.assets.find((x) => x.card === card && x.name === name);
  if (!a) return;
  const c = snap.agents.find((x) => x.key === card);
  const lb = $('#lightbox');
  lb.innerHTML = `<button class="close" aria-label="Close">&times;</button><h2>${esc(a.name)}</h2>
    <div class="kv">
      <div>Agent</div><div>${esc(c.title)} ${c.model ? '(' + esc(c.model) + ')' : ''}</div>
      <div>State</div><div>${esc(a.state)}${a.item_state ? ' (reported: ' + esc(a.item_state) + ')' : ''}</div>
      <div>Triangles</div><div>${a.triangles ?? '-'}${a.budget ? ' of ' + a.budget : ''}${a.vertices != null ? ', ' + a.vertices + ' vertices' : ''}</div>
      <div>Size</div><div>${esc(a.size) || '-'}${a.extent ? ' (' + a.extent + ' units across)' : ''}</div>
      <div>Verification</div><div>${esc(a.verdict || a.verify || 'not run')}</div>
      <div>GPU, worst view</div><div>${a.gpu_percent != null ? a.gpu_percent.toFixed(2) + ' % of the frame' : '-'}</div>
      <div>Recipe</div><div><code>${esc(a.recipe) || '-'}</code></div>
      <div>Report</div><div><code>${esc(a.report) || '-'}</code> ${a.report_time ? ago(a.report_time) + ' ago' : ''}</div>
    </div>
    ${a.images.contact ? `<img src="${esc(a.images.contact)}" alt="contact sheet">` : ''}
    ${a.images.cameras ? `<img src="${esc(a.images.cameras)}" alt="camera views">` : ''}`;
  lb.hidden = false;
}

/* ---------- level ---------- */
function renderLevel() {
  const worlds = snap.worlds;
  if (!worlds.length) return '<div class="empty-note">No world recipes found.</div>';
  const w = worlds.find((x) => x.path === ui.world) || worlds[0];
  const head = `<div class="bar">World <select id="world">${worlds.map((x) =>
      `<option value="${esc(x.path)}" ${x === w ? 'selected' : ''}>${esc(x.name)} (${esc(x.path)})${x.touched_by.length ? ' - ' + x.touched_by.length + ' agents' : ''}</option>`).join('')}</select>
    <span>${w.cells.length} cells${w.cell_size ? ' of ' + w.cell_size + ' units' : ''}${w.regions.length ? ', regions ' + esc(w.regions.join(', ')) : ''}</span></div>`;
  if (!w.cells.length) return head + '<div class="empty-note">This world has no cells yet.</div>';
  const xs = w.cells.map((c) => c.at[0]), zs = w.cells.map((c) => c.at[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), z0 = Math.min(...zs), z1 = Math.max(...zs);
  const at = {};
  for (const c of w.cells) at[c.at[0] + ',' + c.at[1]] = c;
  const cardOf = Object.fromEntries(snap.agents.map((c) => [c.key, c]));
  let cells = '';
  for (let z = z1; z >= z0; z--) {       // +Z up, as the Asset Kit's top view
    for (let x = x0; x <= x1; x++) {
      const c = at[x + ',' + z];
      if (!c) { cells += '<div class="cell empty"></div>'; continue; }
      const t = c.touched_by[c.touched_by.length - 1];
      const unc = c.touched_by.some((u) => u.how === 'uncommitted');
      const style = t ? `background-color:${cardColour(t.card)}` : '';
      const who = c.touched_by.map((u) => (cardOf[u.card] || {}).title + ' (' + u.how + ', ' + u.state + ')').join('\n');
      cells += `<div class="cell ${t ? 'touched' : ''} ${unc ? 'uncommitted' : ''}" style="${style}" title="${esc(c.file + (who ? '\n' + who : ''))}">
        <span class="id">${esc(c.id)}</span>
        <span>${c.placements} placed${c.entities ? ', ' + c.entities + ' ent' : ''}${c.triangles != null ? '<br>' + c.triangles.toLocaleString() + ' tris' : ''}</span>
        <span>${t ? esc(((cardOf[t.card] || {}).title || t.card).slice(0, 18)) : '<span class="muted">untouched</span>'}</span></div>`;
    }
  }
  const legend = w.touched_by.map((u) => {
    const c = cardOf[u.card] || {title: u.card, state: '?'};
    return `<tr><td><span class="sw" style="background:${cardColour(u.card)}"></span>${esc(c.title)}</td><td>${esc(c.state)}${c.stale ? ', stale' : ''}</td>
      <td class="n">${u.cells}</td><td class="n">${u.assets}</td><td class="n">${u.files}</td></tr>`;
  }).join('');
  return head + `<div class="level"><div><div class="axis">+Z up, +X right; cell (${x0}, ${z1}) top left</div>
      <div class="grid" style="grid-template-columns:repeat(${x1 - x0 + 1}, 92px)">${cells}</div></div>
    <div class="legend panel"><h3>Agents touching this world</h3>
      ${legend ? `<table><tr><th>Agent</th><th>State</th><th class="n">Cells</th><th class="n">Recipes</th><th class="n">Files</th></tr>${legend}</table>` : '<div class="muted">none on the shown branches</div>'}
      <p class="muted">A cell takes the colour of the agent that touched its cell file (the last listed when several did);
      striped: the change is not committed yet.${w.report ? ` Triangles from the world report in ${esc(w.report.card)} (${ago(w.report.time)} ago).` : ''}</p></div></div>`;
}

/* ---------- questions ---------- */
function renderQuestions() {
  const qs = snap.questions;
  if (!qs.length) return '<div class="empty-note">No questions. Agents ask with <code>python3 tools/work_status.py ask ID "..."</code>.</div>';
  return '<div class="qs">' + qs.map((q) => `<div class="qitem ${q.answer ? 'answered' : ''}">
      <div class="badges">${modelBadge(q.model)}<span class="b">${esc(q.title)}</span><span class="muted">${ago(q.asked)} ago</span></div>
      <div class="text">${esc(q.text)}</div>
      ${q.answer ? `<div class="muted">Answered ${ago(q.answered)} ago: ${esc(q.answer)}</div>` :
        `<form data-id="${esc(q.id || '')}" data-n="${q.n}"><input name="a" placeholder="Answer (written to the agent's status record)"><button>Answer</button></form>`}
    </div>`).join('') + '</div>';
}

/* ---------- stats ---------- */
function renderStats() {
  const cards = visibleCards();
  const t = now();
  const rows = cards.map((c) => {
    const end = c.ended || (cardFinished(c) || c.state === 'review' ? c.activity : t);
    return {c, start: c.started, end, d: c.started ? end - c.started : null,
            assets: snap.assets.filter((a) => a.card === c.key && !a.collision).length};
  }).sort((a, b) => (a.start || 0) - (b.start || 0));
  const starts = rows.map((r) => r.start).filter(Boolean);
  // the last day at most, so one long-lived worktree doesn't squash the rest
  const t0 = Math.max(t - 86400, starts.length ? Math.min(...starts) : t - 3600), span = Math.max(600, t - t0);
  const tl = rows.filter((r) => r.start && r.end > t0).map((r) => {
    const s0 = Math.max(r.start, t0);
    const left = 100 * (s0 - t0) / span, width = 100 * (r.end - s0) / span;
    return `<div class="row"><span class="lab" title="${esc(r.c.title)}">${esc(r.c.title)}</span><span class="track">
      <i style="left:${left}%;width:${width}%;background:var(--${r.c.state === 'queued' ? 'q' : r.c.state})" title="${esc(r.c.state)}: ${clock(r.start)} to ${clock(r.end)}, ${dur(r.d)}"></i></span></div>`;
  }).join('');
  const table = rows.map((r) => `<tr><td>${esc(r.c.title)}</td><td>${esc(r.c.model || '?')}</td><td>${esc(r.c.kind)}</td><td>${esc(r.c.state)}</td>
      <td>${clock(r.start)}</td><td>${cardFinished(r.c) || r.c.state === 'review' ? clock(r.end) : '-'}</td><td class="n">${dur(r.d)}</td>
      <td class="n">${r.c.git.commit_count || 0}</td><td class="n">${r.assets}</td></tr>`).join('');
  const agg = {};
  for (const r of rows) {
    const k = (r.c.model || '?') + '|' + r.c.kind;
    const a = (agg[k] ||= {model: r.c.model || '?', kind: r.c.kind, n: 0, fin: 0, ds: [], commits: 0, assets: 0});
    a.n++; a.commits += r.c.git.commit_count || 0; a.assets += r.assets;
    if (['done', 'merged', 'review'].includes(r.c.state)) { a.fin++; if (r.d != null) a.ds.push(r.d); }
  }
  const med = (xs) => { if (!xs.length) return null; const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
  const aggRows = Object.values(agg).sort((a, b) => (a.model + a.kind).localeCompare(b.model + b.kind)).map((a) =>
    `<tr><td>${esc(a.model)}</td><td>${esc(a.kind)}</td><td class="n">${a.n}</td><td class="n">${a.fin}</td><td class="n">${dur(med(a.ds))}</td>
      <td class="n">${a.commits}</td><td class="n">${a.assets}</td><td class="n">${a.fin ? (a.assets / a.n).toFixed(1) : '-'}</td></tr>`).join('');
  return `<div class="stats">
    <div class="panel"><h3>By model and kind</h3><table><tr><th>Model</th><th>Kind</th><th class="n">Agents</th><th class="n">Finished</th>
      <th class="n">Median duration</th><th class="n">Commits</th><th class="n">Assets</th><th class="n">Assets per agent</th></tr>${aggRows}</table>
      <p class="muted">"Finished": review, done or merged. Durations run from the worktree's creation (or the reported start) to the reported end or the last activity. A model shows as ? until the agent's record names it.</p></div>
    <div class="panel"><h3>Timeline</h3><div class="tl">${tl}</div><div class="axis">${clock(t0)} to now</div></div>
    <div class="panel"><h3>Agents</h3><table><tr><th>Agent</th><th>Model</th><th>Kind</th><th>State</th><th>Started</th><th>Ended</th>
      <th class="n">Duration</th><th class="n">Commits</th><th class="n">Assets</th></tr>${table}</table></div></div>`;
}

/* ---------- events ---------- */
document.addEventListener('click', (e) => {
  const tab = e.target.closest('#tabs button');
  if (tab) { ui.view = tab.dataset.view; saveUi(); render(); return; }
  if (e.target.closest('#drawerClose')) { $('#drawer').hidden = true; openCard = null; return; }
  if (e.target.closest('#lightbox')) { $('#lightbox').hidden = true; return; }
  const tile = e.target.closest('[data-asset]');
  if (tile) { showAsset(tile.dataset.asset); return; }
  const card = e.target.closest('[data-card]');
  if (card) { drawCard(card.dataset.card); }
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') { $('#lightbox').hidden = true; $('#drawer').hidden = true; openCard = null; }
});
document.addEventListener('change', (e) => {
  const id = e.target.id;
  if (id === 'group') ui.group = e.target.value;
  else if (id === 'showOld') ui.showOld = e.target.checked;
  else if (id === 'assetGroup') ui.assetGroup = e.target.value;
  else if (id === 'assetState') ui.assetState = e.target.value;
  else if (id === 'showCol') ui.showCol = e.target.checked;
  else if (id === 'world') ui.world = e.target.value;
  else return;
  saveUi(); render();
});
$('#filter').addEventListener('input', (e) => { ui.filter = e.target.value; saveUi(); render(); });
document.addEventListener('submit', async (e) => {
  const f = e.target.closest('.qitem form');
  if (!f) return;
  e.preventDefault();
  const text = f.querySelector('input').value.trim();
  if (!text || !f.dataset.id) return;
  const r = await fetch('/api/answer', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id: f.dataset.id, n: Number(f.dataset.n), text})});
  if (!r.ok) { alert('Not saved: ' + ((await r.json()).error || r.status)); return; }
  f.querySelector('input').blur();
  setTimeout(poll, 400);
});

$('#filter').value = ui.filter;
$('#showOld').checked = ui.showOld;
const params = new URLSearchParams(location.search);
if (params.get('view')) ui.view = params.get('view');
if (params.get('old')) ui.showOld = params.get('old') === '1';
if (params.get('world')) ui.world = params.get('world');
poll();
setInterval(poll, POLL_MS);
