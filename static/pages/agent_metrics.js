/* pages/agent_metrics.js — agent performance */

let logs = [];

async function loadMetrics() {
  logs = await apiFetch('/logs');
  renderStats();
  renderAgentTable();
  renderBarChart();
  renderErrors();
}

function renderStats() {
  const total = logs.length;
  const errors = logs.filter(l => l.status === 'error').length;
  const withDur = logs.filter(l => l.duration_ms != null);
  const avgMs = withDur.length
    ? Math.round(withDur.reduce((s, l) => s + l.duration_ms, 0) / withDur.length)
    : null;

  document.getElementById('sc-total').textContent  = total.toLocaleString();
  document.getElementById('sc-rate').textContent   = total ? Math.round((total - errors) / total * 100) + '%' : '—';
  document.getElementById('sc-errors').textContent = errors.toLocaleString();
  document.getElementById('sc-avg').textContent    = avgMs != null ? avgMs.toLocaleString() + ' ms' : '—';
}

function byAgent() {
  const map = {};
  for (const l of logs) {
    const a = l.agent || 'unknown';
    if (!map[a]) map[a] = { runs: 0, errors: 0, totalMs: 0, countMs: 0, last: '' };
    map[a].runs++;
    if (l.status === 'error') map[a].errors++;
    if (l.duration_ms != null) { map[a].totalMs += l.duration_ms; map[a].countMs++; }
    if (!map[a].last || l.timestamp > map[a].last) map[a].last = l.timestamp;
  }
  return Object.entries(map).sort((a, b) => b[1].runs - a[1].runs);
}

function renderAgentTable() {
  const stats = byAgent();
  const el = document.getElementById('agent-table-wrap');
  if (!stats.length) {
    el.innerHTML = '<p class="empty-note">No logs yet — run some agents first.</p>';
    return;
  }
  el.innerHTML = `<table class="ins-table">
    <thead><tr>
      <th>Agent</th>
      <th class="num">Runs</th>
      <th class="num">Errors</th>
      <th class="num">Avg ms</th>
      <th>Last run</th>
    </tr></thead>
    <tbody>
      ${stats.map(([name, s]) => `
        <tr>
          <td>${esc(name)}</td>
          <td class="num">${s.runs}</td>
          <td class="num" style="color:${s.errors ? 'var(--danger)' : 'var(--text-dim)'}">${s.errors || '—'}</td>
          <td class="num">${s.countMs ? s.totalMs / s.countMs < 1000
              ? Math.round(s.totalMs / s.countMs) + ' ms'
              : (s.totalMs / s.countMs / 1000).toFixed(1) + ' s'
            : '—'}</td>
          <td style="color:var(--text-dim);font-size:13px">${s.last ? fmtDate(s.last) : '—'}</td>
        </tr>`).join('')}
    </tbody>
  </table>`;
}

function renderBarChart() {
  const stats = byAgent();
  const el = document.getElementById('bar-chart');
  if (!stats.length) { el.innerHTML = '<p class="empty-note">No data.</p>'; return; }
  const max = Math.max(...stats.map(([, s]) => s.runs));
  el.innerHTML = stats.map(([name, s]) => `
    <div class="bar-row">
      <span class="bar-label">${esc(name)}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:${max ? Math.round(s.runs / max * 100) : 0}%"></div>
      </div>
      <span class="bar-count">${s.runs}</span>
    </div>
  `).join('');
}

function renderErrors() {
  const errors = [...logs].filter(l => l.status === 'error').slice(-15).reverse();
  const el = document.getElementById('error-list');
  if (!errors.length) {
    el.innerHTML = '<p class="empty-note">No errors recorded.</p>';
    return;
  }
  el.innerHTML = errors.map(e => `
    <div class="error-item">
      <div class="error-title">${esc(e.agent)} · ${esc(e.event)}</div>
      <div class="error-meta">${e.details ? esc(e.details.slice(0, 120)) : '(no detail)'} &nbsp;·&nbsp; ${fmtDateTime(e.timestamp)}</div>
    </div>
  `).join('');
}

document.addEventListener('DOMContentLoaded', () => {
  loadMetrics();
  document.getElementById('refresh-btn').addEventListener('click', loadMetrics);
});
