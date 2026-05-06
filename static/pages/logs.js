/* pages/logs.js — agent activity logs page */

let allLogs = [];
let currentFilter = 'all';

async function loadLogs() {
  allLogs = await apiFetch('/logs');
  allLogs.reverse();
  renderLogs();
  updateStats();
  document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
}

function updateStats() {
  document.getElementById('stat-total').textContent = allLogs.length;
  document.getElementById('stat-errors').textContent = allLogs.filter(e => e.status === 'error').length;
  const withDur = allLogs.filter(e => e.duration_ms != null);
  const avg = withDur.length ? Math.round(withDur.reduce((s, e) => s + e.duration_ms, 0) / withDur.length) : null;
  document.getElementById('stat-avg').textContent = avg != null ? avg.toLocaleString() + ' ms' : '—';
}

function setFilter(f, btn) {
  currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderLogs();
}

function renderLogs() {
  const filtered = allLogs.filter(e => {
    if (currentFilter === 'all') return true;
    if (currentFilter === 'error') return e.status === 'error';
    return e.event === currentFilter;
  });
  const el = document.getElementById('log-container');
  if (!filtered.length) {
    el.innerHTML = `<div class="empty"><strong>No entries</strong>${currentFilter !== 'all' ? 'No entries for this filter.' : 'Logs appear here as agents run.'}</div>`;
    return;
  }
  const knownEvents = ['create', 'enrich', 'validate', 'heal', 'kickstart', 'create_batch'];
  const rows = filtered.map(e => {
    const evClass = knownEvents.includes(e.event) ? `ev-${e.event}` : 'ev-other';
    const ticketCell = e.ticket_id
      ? `<a href="/tickets/${esc(e.ticket_id)}" class="ticket-link">${esc(e.ticket_id.slice(0, 8))}…</a>`
      : '<span class="no-ticket">—</span>';
    const dur = e.duration_ms != null ? Math.round(e.duration_ms).toLocaleString() + ' ms' : '—';
    return `<tr>
      <td class="mono">${fmtTs(e.timestamp)}</td>
      <td><span class="badge ${evClass}">${esc(e.event)}</span></td>
      <td>${ticketCell}</td>
      <td class="mono" style="color:var(--text-muted)">${esc(e.agent)}</td>
      <td class="num">${dur}</td>
      <td><span class="${e.status === 'success' ? 'st-success' : 'st-error'}">${e.status === 'success' ? '✓' : '✗'} ${e.status}</span></td>
      <td class="details">${esc(e.details || '')}</td>
    </tr>`;
  }).join('');
  el.innerHTML = `<table>
    <thead><tr>
      <th>Timestamp</th><th>Event</th><th>Ticket</th><th>Agent</th><th class="num">Duration</th><th>Status</th><th>Details</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function fmtTs(s) {
  if (!s) return '—';
  const d = new Date(s);
  return d.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit' }) + ' ' +
    d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

async function clearLogs() {
  if (!confirm('Clear all logs?')) return;
  try {
    await apiFetch('/logs', { method: 'DELETE' });
    allLogs = [];
    renderLogs();
    updateStats();
    toast('Logs cleared');
  } catch { toast('Clear failed', true); }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('refresh-btn').addEventListener('click', loadLogs);
  document.getElementById('clear-btn').addEventListener('click', clearLogs);

  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => setFilter(btn.dataset.filter, btn));
  });

  loadLogs();
  setInterval(loadLogs, 15000);
});
