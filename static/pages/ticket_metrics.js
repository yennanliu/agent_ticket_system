/* pages/ticket_metrics.js — ticket analytics */

let tickets = [];

async function loadMetrics() {
  tickets = await apiFetch('/tickets');
  renderStats();
  renderCharts();
  renderProjectTable();
  renderAssigneeTable();
}

function countBy(arr, key, val) { return arr.filter(t => t[key] === val).length; }
function mean(nums) { return nums.length ? nums.reduce((a, b) => a + b, 0) / nums.length : null; }

function renderStats() {
  const total = tickets.length;
  const validated = tickets.filter(t => t.validation_passed !== null && t.validation_passed !== undefined);
  const passed = tickets.filter(t => t.validation_passed === true);

  const cards = [
    { label: 'Total',     val: total },
    { label: 'Open',      val: countBy(tickets, 'status', 'open') },
    { label: 'Draft',     val: countBy(tickets, 'status', 'draft') },
    { label: 'Done',      val: countBy(tickets, 'status', 'done') },
    { label: 'Validated', val: validated.length },
    {
      label: 'Pass Rate',
      val: validated.length ? Math.round(passed.length / validated.length * 100) + '%' : '—',
      cls: 'sc-success',
    },
  ];

  document.getElementById('stat-strip').innerHTML = cards.map(c =>
    `<div class="stat-card">
      <span class="sc-label">${c.label}</span>
      <span class="sc-val${c.cls ? ' ' + c.cls : ''}">${c.val}</span>
    </div>`
  ).join('');
}

const BAR_COLORS = {
  open:        'var(--blue)',
  draft:       'var(--purple)',
  in_progress: 'var(--warning)',
  done:        'var(--success)',
  rejected:    'var(--danger)',
  high:        'var(--danger)',
  medium:      'var(--warning)',
  low:         'var(--success)',
  critical:    'var(--accent-alt)',
};

function barRows(items) {
  const max = Math.max(...items.map(i => i.n), 1);
  return items.map(i => `
    <div class="bar-row">
      <span class="bar-label">${esc(i.label)}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:${Math.round(i.n / max * 100)}%;background:${BAR_COLORS[i.label] || 'var(--accent)'}"></div>
      </div>
      <span class="bar-count">${i.n}</span>
    </div>
  `).join('');
}

function renderCharts() {
  const statusItems = ['open','draft','in_progress','done','rejected']
    .map(s => ({ label: s, n: countBy(tickets, 'status', s) })).filter(i => i.n);
  const priItems = ['high','medium','low']
    .map(p => ({ label: p, n: countBy(tickets, 'priority', p) })).filter(i => i.n);
  const impItems = ['critical','high','medium','low']
    .map(v => ({ label: v, n: countBy(tickets, 'importance', v) })).filter(i => i.n);

  document.getElementById('charts-row').innerHTML = `
    <div class="chart-card"><h3>By Status</h3>${barRows(statusItems) || '<p class="empty-note">No data.</p>'}</div>
    <div class="chart-card"><h3>By Priority</h3>${barRows(priItems) || '<p class="empty-note">No data.</p>'}</div>
    <div class="chart-card"><h3>By Importance</h3>${barRows(impItems) || '<p class="empty-note">No data.</p>'}</div>
  `;
}

function groupBy(arr, fn) {
  const map = {};
  for (const item of arr) {
    const k = fn(item);
    (map[k] = map[k] || []).push(item);
  }
  return map;
}

function rowStats(ts) {
  const scores = ts.filter(t => t.validation_score != null).map(t => t.validation_score);
  const validated = ts.filter(t => t.validation_passed !== null && t.validation_passed !== undefined);
  const passed = ts.filter(t => t.validation_passed === true);
  return {
    total: ts.length,
    open: ts.filter(t => t.status === 'open').length,
    avgScore: mean(scores),
    passRate: validated.length ? Math.round(passed.length / validated.length * 100) : null,
  };
}

function renderProjectTable() {
  const groups = groupBy(tickets, t => t.source_repo || '');
  const rows = Object.entries(groups)
    .map(([repo, ts]) => ({ repo, ...rowStats(ts) }))
    .sort((a, b) => b.total - a.total);

  const el = document.getElementById('project-table');
  if (!rows.length) { el.innerHTML = '<p class="empty-note">No tickets yet.</p>'; return; }

  el.innerHTML = `<table class="ins-table">
    <thead><tr>
      <th>Project</th><th class="num">Tickets</th><th class="num">Open</th>
      <th class="num">Avg Score</th><th class="num">Pass Rate</th>
    </tr></thead>
    <tbody>
      ${rows.map(r => `
        <tr>
          <td class="mono" title="${esc(r.repo)}">${r.repo ? esc(repoShort(r.repo)) : '<span style="color:var(--text-dim)">—</span>'}</td>
          <td class="num">${r.total}</td>
          <td class="num">${r.open || '—'}</td>
          <td class="num">${r.avgScore != null ? Math.round(r.avgScore * 100) + '%' : '—'}</td>
          <td class="num">${r.passRate != null ? r.passRate + '%' : '—'}</td>
        </tr>`).join('')}
    </tbody>
  </table>`;
}

function renderAssigneeTable() {
  const groups = groupBy(tickets, t => t.suggested_assignee || '');
  const rows = Object.entries(groups)
    .map(([assignee, ts]) => ({ assignee, ...rowStats(ts) }))
    .sort((a, b) => b.total - a.total);

  const el = document.getElementById('assignee-table');
  if (!rows.length) { el.innerHTML = '<p class="empty-note">No tickets yet.</p>'; return; }

  el.innerHTML = `<table class="ins-table">
    <thead><tr>
      <th>Assignee</th><th class="num">Tickets</th>
      <th class="num">Avg Score</th><th class="num">Pass Rate</th>
    </tr></thead>
    <tbody>
      ${rows.map(r => `
        <tr>
          <td>${r.assignee ? esc(r.assignee) : '<span style="color:var(--text-dim)">(unassigned)</span>'}</td>
          <td class="num">${r.total}</td>
          <td class="num">${r.avgScore != null ? Math.round(r.avgScore * 100) + '%' : '—'}</td>
          <td class="num">${r.passRate != null ? r.passRate + '%' : '—'}</td>
        </tr>`).join('')}
    </tbody>
  </table>`;
}

document.addEventListener('DOMContentLoaded', () => {
  loadMetrics();
  document.getElementById('refresh-btn').addEventListener('click', loadMetrics);
});
