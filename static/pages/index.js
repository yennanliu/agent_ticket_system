/* pages/index.js — ticket list page */

let enrichingIds = new Set();
let currentTickets = [];
let showDrafts = true;

// ── Data loading ───────────────────────────────────────────────────────────

async function loadTickets() {
  currentTickets = await apiFetch('/tickets');
  populateRepoFilter(currentTickets);
  updateDraftBadge(currentTickets);
  applyFilters();
  updateStats(currentTickets);
}

function updateDraftBadge(tickets) {
  const count = tickets.filter(t => t.status === 'draft').length;
  const link = document.getElementById('review-nav-link');
  const badge = document.getElementById('header-draft-count');
  if (count > 0) {
    badge.textContent = count;
    link.style.display = '';
  } else {
    link.style.display = 'none';
  }
}

function populateRepoFilter(tickets) {
  const sel = document.getElementById('repo-filter');
  const current = sel.value;
  const visible = showDrafts ? tickets : tickets.filter(t => t.status !== 'draft' && t.status !== 'rejected');
  const repos = [...new Set(visible.map(t => t.source_repo).filter(Boolean))].sort();
  sel.innerHTML = '<option value="">All repos</option>' +
    repos.map(r => `<option value="${esc(r)}"${r === current ? ' selected' : ''}>${esc(repoShort(r))}</option>`).join('');
}

function applyFilters() {
  let filtered = currentTickets;
  const statusFilter = document.getElementById('status-filter').value;
  if (statusFilter) {
    filtered = filtered.filter(t => t.status === statusFilter);
  } else if (!showDrafts) {
    filtered = filtered.filter(t => t.status !== 'draft' && t.status !== 'rejected');
  }
  const typeFilter = document.getElementById('type-filter').value;
  if (typeFilter) filtered = filtered.filter(t => (t.ticket_type || 'task') === typeFilter);
  const repoFilter = document.getElementById('repo-filter').value;
  if (repoFilter) filtered = filtered.filter(t => t.source_repo === repoFilter);
  renderTable(filtered);
}

function updateStats(tickets) {
  document.getElementById('stat-total').textContent = tickets.length;
  document.getElementById('stat-open').textContent = tickets.filter(t => t.status === 'open').length;
  const validated = tickets.filter(t => t.validation_passed !== null && t.validation_passed !== undefined);
  const passed = tickets.filter(t => t.validation_passed === true);
  document.getElementById('stat-validated').textContent = validated.length;
  document.getElementById('stat-passrate').textContent = validated.length
    ? Math.round(passed.length / validated.length * 100) + '%' : '—';
}

// ── Agent actions ──────────────────────────────────────────────────────────

async function generateTickets() {
  const source = document.getElementById('repo-input').value.trim();
  if (!source) { toast('Enter a repo path or GitHub URL', true); return; }
  const btn = document.getElementById('generate-btn');
  await withLoading(btn, 'Generating…', async () => {
    const body = source.startsWith('http') ? { repo_url: source } : { repo_path: source };
    const tickets = await apiFetch('/agents/create-from-repo', { method: 'POST', body });
    toast(`Created ${tickets.length} ticket(s)`);
    loadTickets();
  }).catch(e => toast('Failed: ' + e.message, true));
}

async function enrichAll() {
  const globalSource = document.getElementById('repo-input').value.trim();
  const checked = [...document.querySelectorAll('.row-check:checked')].map(el => el.dataset.id);
  const btn = document.getElementById('enrich-all-btn');
  await withLoading(btn, 'Enriching…', async () => {
    const body = {};
    if (globalSource.startsWith('http')) body.repo_url = globalSource;
    else if (globalSource) body.repo_path = globalSource;
    if (checked.length) body.ticket_ids = checked;
    const tickets = await apiFetch('/agents/enrich-batch', { method: 'POST', body });
    toast(`Enriched ${tickets.length} ticket(s)`);
    loadTickets();
  }).catch(e => toast('Enrich failed: ' + e.message, true));
}

async function enrichTicket(id, fallbackSource) {
  if (enrichingIds.has(id)) return;
  const source = document.getElementById('repo-input').value.trim() || fallbackSource || '';
  enrichingIds.add(id);
  setEnrichLoading(id, true);
  try {
    const body = source.startsWith('http') ? { repo_url: source } : (source ? { repo_path: source } : {});
    await apiFetch(`/agents/enrich/${id}`, { method: 'POST', body });
    toast('Enriched');
    loadTickets();
  } catch(e) { toast('Enrich failed: ' + e.message, true); }
  finally { enrichingIds.delete(id); setEnrichLoading(id, false); }
}

async function deleteTicket(id, title) {
  if (!confirm(`Delete "${title}"?`)) return;
  await apiFetch(`/tickets/${id}`, { method: 'DELETE' }).catch(() => null);
  toast('Deleted');
  loadTickets();
}

async function splitTicket(id) {
  const btn = document.getElementById(`split-btn-${id}`);
  if (btn) { btn.disabled = true; btn.textContent = '⎇ Splitting…'; }
  try {
    const children = await apiFetch(`/agents/split/${id}`, { method: 'POST' });
    toast(`Split into ${children.length} sub-ticket(s) ✓`);
    loadTickets();
  } catch(e) {
    toast('Split failed: ' + e.message, true);
    if (btn) { btn.disabled = false; btn.textContent = '⎇ Split'; }
  }
}

function setEnrichLoading(id, loading) {
  const btn = document.getElementById(`enrich-btn-${id}`);
  if (!btn) return;
  btn.disabled = loading;
  btn.innerHTML = loading ? '<span class="spinner dark"></span>…' : '✦ Enrich';
}

// ── Modals ─────────────────────────────────────────────────────────────────

function openCreate(parentId = '', defaultType = 'task') {
  document.getElementById('modal-title').textContent = 'New Ticket';
  document.getElementById('modal-id').value = '';
  ['f-title','f-business-req','f-stakeholder','f-user-story','f-desc','f-labels','f-repo']
    .forEach(id => { document.getElementById(id).value = ''; });
  document.getElementById('f-status').value = 'open';
  document.getElementById('f-priority').value = 'medium';
  document.getElementById('f-importance').value = 'medium';
  document.getElementById('f-type').value = defaultType;
  document.getElementById('f-parent-id').value = parentId;
  document.getElementById('modal').classList.add('open');
}

function openEdit(t) {
  document.getElementById('modal-title').textContent = 'Edit Ticket';
  document.getElementById('modal-id').value = t.id;
  document.getElementById('f-title').value = t.title;
  document.getElementById('f-business-req').value = t.business_req || '';
  document.getElementById('f-stakeholder').value = t.stakeholder || '';
  document.getElementById('f-user-story').value = t.user_story || '';
  document.getElementById('f-desc').value = t.description || '';
  document.getElementById('f-status').value = t.status;
  document.getElementById('f-priority').value = t.priority;
  document.getElementById('f-importance').value = t.importance || 'medium';
  document.getElementById('f-labels').value = (t.labels || []).join(', ');
  document.getElementById('f-repo').value = t.source_repo || '';
  document.getElementById('f-type').value = t.ticket_type || 'task';
  document.getElementById('f-parent-id').value = t.parent_id || '';
  document.getElementById('modal').classList.add('open');
}

function closeModal() { document.getElementById('modal').classList.remove('open'); }

async function submitTicket() {
  const id = document.getElementById('modal-id').value;
  const ttype = document.getElementById('f-type').value;
  const parentId = document.getElementById('f-parent-id').value.trim();
  const payload = {
    title: document.getElementById('f-title').value.trim(),
    business_req: document.getElementById('f-business-req').value.trim(),
    stakeholder: document.getElementById('f-stakeholder').value.trim(),
    user_story: document.getElementById('f-user-story').value.trim(),
    description: document.getElementById('f-desc').value.trim(),
    status: document.getElementById('f-status').value,
    priority: document.getElementById('f-priority').value,
    importance: document.getElementById('f-importance').value,
    labels: document.getElementById('f-labels').value.split(',').map(s => s.trim()).filter(Boolean),
    source_repo: document.getElementById('f-repo').value.trim(),
    ticket_type: ttype,
    parent_id: parentId || null,
  };
  if (!payload.title) { toast('Title is required', true); return; }
  const willSplit = !id && (ttype === 'epic' || ttype === 'story');
  try {
    const ticket = await apiFetch(id ? `/tickets/${id}` : '/tickets', {
      method: id ? 'PUT' : 'POST', body: payload,
    });
    closeModal();
    if (id) {
      toast('Updated');
      loadTickets();
    } else {
      toast(willSplit ? `Created ${ttype} — splitting & validating…` : (payload.source_repo ? 'Created — enriching & validating…' : 'Created — validating…'));
      loadTickets();
      try {
        await apiFetch(`/agents/kickstart/${ticket.id}`, { method: 'POST' });
        toast(willSplit ? `Split into sub-tickets ✓` : 'Ready ✓');
        loadTickets();
      } catch { /* ignore pipeline errors */ }
    }
  } catch { toast('Save failed', true); }
}

function openBatchCreate() {
  document.getElementById('batch-titles').value = '';
  document.getElementById('batch-repo').value = '';
  document.getElementById('batch-modal').classList.add('open');
}
function closeBatchModal() { document.getElementById('batch-modal').classList.remove('open'); }

async function submitBatch() {
  const raw = document.getElementById('batch-titles').value;
  const titles = raw.split('\n').map(s => s.trim()).filter(Boolean);
  if (!titles.length) { toast('Enter at least one title', true); return; }
  const repo_path = document.getElementById('batch-repo').value.trim() || undefined;
  const body = { titles };
  if (repo_path) body.repo_path = repo_path;
  try {
    const created = await apiFetch('/agents/create-batch', { method: 'POST', body });
    closeBatchModal();
    toast(`Created ${created.length} ticket(s) — ${repo_path ? 'enriching & ' : ''}validating…`);
    loadTickets();
    for (const t of created) {
      try { await apiFetch(`/agents/kickstart/${t.id}`, { method: 'POST' }); } catch { /* ignore */ }
    }
    toast(`${created.length} ticket(s) ready ✓`);
    loadTickets();
  } catch { toast('Batch create failed', true); }
}

// ── Table rendering ────────────────────────────────────────────────────────

function renderTable(tickets) {
  const el = document.getElementById('ticket-container');
  if (!tickets.length) {
    el.innerHTML = '<div class="empty"><strong>No tickets yet</strong>Generate from a repo, batch create, or add one manually.</div>';
    return;
  }

  const rows = tickets.map(t => {
    const dot = (t.acceptance_criteria && t.acceptance_criteria.length)
      ? '<span class="enriched-dot" title="Enriched"></span>' : '';
    const valCell = t.validation_passed === true
      ? `<span class="val-pass">✓ ${pct(t.validation_score)}</span>`
      : t.validation_passed === false
        ? `<span class="val-fail">✗ ${pct(t.validation_score)}</span>`
        : '<span class="val-none">—</span>';
    const labels = (t.labels || []).map(l => `<span class="label-chip">${esc(l)}</span>`).join('');
    const ttype = t.ticket_type || 'task';
    const childPrefix = t.parent_id ? '<span class="child-indent">↳</span> ' : '';
    const repo = t.source_repo ? `<span class="repo-chip">${esc(repoShort(t.source_repo))}</span>` : '';
    const imp = t.importance || 'medium';
    const canSplit = (ttype === 'epic' || ttype === 'story') && !enrichingIds.has('split-' + t.id);
    return `<tr class="${t.status === 'draft' ? 'is-draft' : t.status === 'rejected' ? 'is-rejected' : ''}${t.parent_id ? ' is-child' : ''}">
      <td class="check-col"><input type="checkbox" class="row-check" data-id="${t.id}"></td>
      <td class="title-col">
        ${childPrefix}<a href="/tickets/${t.id}" class="ticket-link">${esc(t.title)}${dot}</a>
        ${repo}
      </td>
      <td><span class="badge ty-${ttype}">${ttype}</span></td>
      <td><span class="badge s-${t.status}">${t.status.replace('_', ' ')}</span></td>
      <td><span class="badge p-${t.priority}">${t.priority}</span></td>
      <td class="num">${valCell}</td>
      <td>${labels}</td>
      <td class="num date-col">${fmtDate(t.created_at)}</td>
      <td>
        <div class="action-btns">
          <button class="btn-xs edit-btn" data-id="${t.id}">Edit</button>
          <button class="btn-xs enrich" id="enrich-btn-${t.id}" data-id="${t.id}" data-repo="${esc(t.source_repo || '')}" ${enrichingIds.has(t.id) ? 'disabled' : ''}>
            ${enrichingIds.has(t.id) ? '<span class="spinner dark"></span>…' : '✦ Enrich'}
          </button>
          ${canSplit ? `<button class="btn-xs split-btn" id="split-btn-${t.id}" data-id="${t.id}">⎇ Split</button>` : ''}
          <button class="btn-xs del" data-id="${t.id}" data-title="${esc(t.title)}">Del</button>
        </div>
      </td>
    </tr>`;
  }).join('');

  el.innerHTML = `<table>
    <thead><tr>
      <th class="check-col"><input type="checkbox" id="select-all" title="Select all"></th>
      <th>Title</th><th>Type</th><th>Status</th><th>Priority</th>
      <th class="num">Validation</th><th>Labels</th><th class="num">Created</th><th>Actions</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
  updateSelectionUI();
}

// ── Selection helpers ──────────────────────────────────────────────────────

function selectAll() {
  const master = document.getElementById('select-all');
  if (master) master.checked = true;
  document.querySelectorAll('.row-check').forEach(cb => { cb.checked = true; });
  updateSelectionUI();
}

function deselectAll() {
  const master = document.getElementById('select-all');
  if (master) master.checked = false;
  document.querySelectorAll('.row-check').forEach(cb => { cb.checked = false; });
  updateSelectionUI();
}

function updateSelectionUI() {
  const n = document.querySelectorAll('.row-check:checked').length;
  const info = document.getElementById('selection-info');
  const btn = document.getElementById('delete-selected-btn');
  if (n > 0) {
    info.textContent = `${n} selected`;
    info.style.display = '';
    btn.textContent = `Delete ${n}`;
    btn.style.display = '';
  } else {
    info.style.display = 'none';
    btn.style.display = 'none';
  }
}

async function deleteSelected() {
  const ids = [...document.querySelectorAll('.row-check:checked')].map(el => el.dataset.id);
  if (!ids.length) return;
  if (!confirm(`Delete ${ids.length} ticket(s)?`)) return;
  const btn = document.getElementById('delete-selected-btn');
  btn.disabled = true;
  btn.textContent = 'Deleting…';
  let deleted = 0;
  for (const id of ids) {
    try { await apiFetch(`/tickets/${id}`, { method: 'DELETE' }); deleted++; } catch { /* skip */ }
  }
  toast(`Deleted ${deleted} ticket(s)`);
  loadTickets();
}

function toggleDrafts() {
  showDrafts = !showDrafts;
  document.getElementById('drafts-toggle').textContent = showDrafts ? 'Hide Drafts' : 'Show Drafts';
  applyFilters();
}

async function eraseAll() {
  if (!currentTickets.length) { toast('No tickets to erase', true); return; }
  if (!confirm(`Permanently delete all ${currentTickets.length} tickets? This cannot be undone.`)) return;
  const btn = document.getElementById('erase-all-btn');
  await withLoading(btn, 'Erasing…', async () => {
    const { deleted } = await apiFetch('/tickets', { method: 'DELETE' });
    toast(`Erased ${deleted} ticket(s)`);
    loadTickets();
  }).catch(e => toast('Erase failed: ' + e.message, true));
}

function downloadCSV() {
  if (!currentTickets.length) { toast('No tickets to export', true); return; }
  const cols = ['id','title','description','status','priority','ticket_type','labels','source_repo',
                 'acceptance_criteria','technical_notes','suggested_assignee','validation_score','created_at'];
  const header = cols.join(',');
  const rows = currentTickets.map(t =>
    cols.map(c => {
      const v = t[c];
      const s = Array.isArray(v) ? v.join('; ') : (v == null ? '' : String(v));
      return `"${s.replace(/"/g, '""')}"`;
    }).join(',')
  );
  const csv = [header, ...rows].join('\n');
  const a = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
    download: `tickets-${new Date().toISOString().slice(0,10)}.csv`,
  });
  a.click();
  URL.revokeObjectURL(a.href);
}

// ── Init ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Modal overlay close on backdrop click
  document.getElementById('modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });
  document.getElementById('batch-modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeBatchModal(); });

  // Button clicks in header / toolbar
  document.getElementById('new-ticket-btn').addEventListener('click', openCreate);
  document.getElementById('batch-create-btn').addEventListener('click', openBatchCreate);
  document.getElementById('erase-all-btn').addEventListener('click', eraseAll);
  document.getElementById('download-csv-btn').addEventListener('click', downloadCSV);
  document.getElementById('generate-btn').addEventListener('click', generateTickets);
  document.getElementById('enrich-all-btn').addEventListener('click', enrichAll);
  document.getElementById('drafts-toggle').addEventListener('click', toggleDrafts);
  document.getElementById('type-filter').addEventListener('change', applyFilters);
  document.getElementById('status-filter').addEventListener('change', applyFilters);
  document.getElementById('repo-filter').addEventListener('change', applyFilters);
  document.getElementById('modal-save-btn').addEventListener('click', submitTicket);
  document.getElementById('modal-cancel-btn').addEventListener('click', closeModal);
  document.getElementById('batch-save-btn').addEventListener('click', submitBatch);
  document.getElementById('batch-cancel-btn').addEventListener('click', closeBatchModal);
  document.getElementById('select-all-btn').addEventListener('click', selectAll);
  document.getElementById('deselect-all-btn').addEventListener('click', deselectAll);
  document.getElementById('delete-selected-btn').addEventListener('click', deleteSelected);

  // Event delegation on the ticket container for dynamic buttons
  const container = document.getElementById('ticket-container');
  container.addEventListener('change', e => {
    if (e.target.classList.contains('row-check')) updateSelectionUI();
    const master = document.getElementById('select-all');
    if (master) {
      const all = document.querySelectorAll('.row-check');
      const checked = document.querySelectorAll('.row-check:checked');
      master.checked = all.length > 0 && all.length === checked.length;
    }
  });
  container.addEventListener('click', e => {
    const editBtn = e.target.closest('.edit-btn');
    if (editBtn) {
      const t = currentTickets.find(x => x.id === editBtn.dataset.id);
      if (t) openEdit(t);
      return;
    }
    const enrichBtn = e.target.closest('.enrich');
    if (enrichBtn) { enrichTicket(enrichBtn.dataset.id, enrichBtn.dataset.repo); return; }
    const splitBtn = e.target.closest('.split-btn');
    if (splitBtn) { splitTicket(splitBtn.dataset.id); return; }
    const delBtn = e.target.closest('.del');
    if (delBtn) { deleteTicket(delBtn.dataset.id, delBtn.dataset.title); return; }
  });
  const masterCb = document.getElementById('select-all');
  if (masterCb) masterCb.addEventListener('change', e => {
    document.querySelectorAll('.row-check').forEach(cb => { cb.checked = e.target.checked; });
    updateSelectionUI();
  });

  loadTickets();
});
