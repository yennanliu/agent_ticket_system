/* pages/ticket.js — single ticket detail page */

const ticketId = window.location.pathname.split('/').pop();
let currentTicket = null;

// ── Data loading ───────────────────────────────────────────────────────────

async function loadTicket() {
  try {
    currentTicket = await apiFetch(`/tickets/${ticketId}`);
    renderTicket(currentTicket);
  } catch {
    document.getElementById('not-found').style.display = 'block';
  }
}

function renderTicket(t) {
  document.getElementById('content').style.display = 'block';
  document.getElementById('header-title').textContent = t.title;
  document.title = t.title + ' — Agent Ticket System';
  document.getElementById('t-title').textContent = t.title;

  const srcInput = document.getElementById('source-input');
  if (!srcInput.value && t.source_repo) srcInput.value = t.source_repo;

  // Draft banner
  const banner = document.getElementById('draft-banner');
  banner.classList.toggle('visible', t.status === 'draft');

  // Split button visibility
  const ttype = t.ticket_type || 'task';
  document.getElementById('split-btn').style.display =
    (ttype === 'epic' || ttype === 'story') ? '' : 'none';

  const imp = t.importance || 'medium';
  const labels = (t.labels || []).map(l => `<span class="label-chip">${esc(l)}</span>`).join(' ');
  document.getElementById('t-meta').innerHTML =
    `<span class="badge ty-${ttype}">${ttype}</span>
     <span class="badge s-${t.status}">${t.status.replace('_', ' ')}</span>
     <span class="badge p-${t.priority}">${t.priority}</span>
     <span class="badge i-${imp}">⚡ ${imp}</span>
     ${labels}`;

  const iters = t.validation_iterations || 0;
  const iterHint = iters > 0 ? ` <span class="iter-hint">(healed ${iters}×)</span>` : '';
  const vb = document.getElementById('t-val-badge');
  if (t.validation_passed === true)
    vb.innerHTML = `<span class="val-badge-pass">✓ VALIDATED ${pct(t.validation_score)}</span>${iterHint}`;
  else if (t.validation_passed === false)
    vb.innerHTML = `<span class="val-badge-fail">✗ FAILED ${pct(t.validation_score)}</span>${iterHint}`;
  else
    vb.innerHTML = `<span class="val-badge-pending">NOT VALIDATED</span>`;

  setField('t-business-req', t.business_req, 'No business requirement — use Enrich to generate.');
  setField('t-stakeholder', t.stakeholder, '—');
  setField('t-user-story', t.user_story, 'No user story — use Enrich to generate.');
  setField('t-desc', t.description, 'No description — use Enrich to generate.');

  const ac = t.acceptance_criteria || [];
  document.getElementById('t-ac').innerHTML = ac.length
    ? `<ul class="criteria-list">${ac.map(c => `<li>${esc(c)}</li>`).join('')}</ul>`
    : '<span class="field-empty">None — use ✦ Enrich to generate.</span>';

  const files = t.related_files || [];
  document.getElementById('t-files').innerHTML = files.length
    ? `<ul class="files-list">${files.map(f => `<li><code class="file">${esc(f)}</code></li>`).join('')}</ul>`
    : '<span class="field-empty">None.</span>';

  setField('t-notes', t.technical_notes, 'None.');
  setField('t-assignee', t.suggested_assignee, '—');

  const refs = t.suggested_change_refs || [];
  document.getElementById('t-refs').innerHTML = refs.length
    ? `<div class="refs-wrap"><table class="refs-table">
        <thead><tr><th>File</th><th>Type</th><th>Reference</th></tr></thead>
        <tbody>${refs.map(r => `
          <tr>
            <td><code class="file">${esc(r.file)}</code></td>
            <td><span class="ref-type-badge ref-${r.ref_type}">${r.ref_type}</span></td>
            <td><a href="${esc(r.ref_url)}" class="ref-link" target="_blank">${esc(r.title || r.ref_url)}</a></td>
          </tr>`).join('')}
        </tbody>
      </table></div>`
    : '<div class="refs-wrap"><span class="field-empty">No refs — Enrich from a GitHub URL to auto-generate.</span></div>';

  renderValidation(t);

  document.getElementById('s-id').textContent = t.id.slice(0, 8) + '…';
  document.getElementById('s-type').innerHTML = `<span class="badge ty-${ttype}">${ttype}</span>`;
  document.getElementById('s-status').innerHTML = `<span class="badge s-${t.status}">${t.status.replace('_', ' ')}</span>`;
  document.getElementById('s-priority').innerHTML = `<span class="badge p-${t.priority}">${t.priority}</span>`;
  document.getElementById('s-importance').innerHTML = `<span class="badge i-${imp}">${imp}</span>`;
  const repo = t.source_repo;
  document.getElementById('s-repo').innerHTML = repo
    ? (repo.startsWith('http')
      ? `<a href="${esc(repo)}" target="_blank" title="${esc(repo)}">${esc(repoShort(repo))}</a>`
      : esc(repoShort(repo)))
    : '—';
  document.getElementById('s-created').textContent = fmtDateTime(t.created_at);
  document.getElementById('s-updated').textContent = fmtDateTime(t.updated_at);

  // Parent link
  const parentRow = document.getElementById('s-parent-row');
  if (t.parent_id) {
    parentRow.style.display = '';
    document.getElementById('s-parent').innerHTML =
      `<a href="/tickets/${esc(t.parent_id)}" style="color:var(--accent);font-family:'JetBrains Mono',monospace;font-size:13px">${t.parent_id.slice(0, 8)}…</a>`;
  } else {
    parentRow.style.display = 'none';
  }

  loadChildren();
}

function setField(id, val, emptyMsg) {
  document.getElementById(id).innerHTML = val
    ? `<span class="field-value">${esc(val)}</span>`
    : `<span class="field-empty">${emptyMsg}</span>`;
}

function renderValidation(t) {
  const el = document.getElementById('t-validation');
  if (t.validation_score === null || t.validation_score === undefined) {
    el.innerHTML = '<span class="field-empty">Not validated yet — click ⬡ Validate.</span>';
    return;
  }
  const p = Math.round(t.validation_score * 100);
  const pass = t.validation_passed;
  el.innerHTML = `
    <div class="val-score-display">
      <span class="val-score-num ${pass ? 'pass' : 'fail'}">${p}%</span>
      <span class="val-score-label ${pass ? 'pass' : 'fail'}">${pass ? '✓ Passed' : '✗ Failed'}</span>
    </div>
    <div class="val-bar-wrap">
      <div class="val-bar ${pass ? 'bar-pass' : 'bar-fail'}" style="width:${p}%"></div>
    </div>
    <p class="val-notes">${esc(t.validation_notes || '')}</p>`;
}

// ── Children ───────────────────────────────────────────────────────────────

async function loadChildren() {
  try {
    const children = await apiFetch(`/tickets/${ticketId}/children`);
    const card = document.getElementById('children-card');
    if (!children.length) { card.style.display = 'none'; return; }
    card.style.display = '';
    document.getElementById('children-count').textContent = children.length;
    const STATUS_ICON = { open: '○', draft: '◌', in_progress: '●', done: '✓', rejected: '✗' };
    document.getElementById('t-children').innerHTML = `
      <div class="children-list">
        ${children.map(c => `
          <div class="child-row">
            <span class="badge ty-${c.ticket_type || 'task'}" style="font-size:11px">${c.ticket_type || 'task'}</span>
            <span class="child-status-icon">${STATUS_ICON[c.status] || '○'}</span>
            <a href="/tickets/${esc(c.id)}" class="child-link">${esc(c.title)}</a>
            <span class="child-meta">${c.validation_passed === true ? '<span style="color:var(--success)">✓ ' + pct(c.validation_score) + '</span>' : c.validation_passed === false ? '<span style="color:var(--danger)">✗ ' + pct(c.validation_score) + '</span>' : ''}</span>
          </div>`).join('')}
      </div>`;
  } catch { /* children endpoint optional */ }
}

// ── Agent actions ──────────────────────────────────────────────────────────

async function enrichTicket() {
  const source = document.getElementById('source-input').value.trim();
  const btn = document.getElementById('enrich-btn');
  await withLoading(btn, 'Enriching…', async () => {
    const body = source.startsWith('http') ? { repo_url: source } : (source ? { repo_path: source } : {});
    currentTicket = await apiFetch(`/agents/enrich/${ticketId}`, { method: 'POST', body });
    renderTicket(currentTicket);
    toast('Enriched');
  }).catch(e => toast('Enrich failed: ' + e.message, true));
}

async function validateTicket() {
  const btn = document.getElementById('validate-btn');
  await withLoading(btn, 'Validating…', async () => {
    currentTicket = await apiFetch(`/agents/validate/${ticketId}`, { method: 'POST' });
    renderTicket(currentTicket);
    toast('Validation complete');
  }).catch(e => toast('Validate failed: ' + e.message, true));
}

async function healTicket() {
  const btn = document.getElementById('heal-btn');
  await withLoading(btn, 'Healing…', async () => {
    currentTicket = await apiFetch(`/agents/heal/${ticketId}`, { method: 'POST' });
    renderTicket(currentTicket);
    const iters = currentTicket.validation_iterations || 0;
    toast(`Healed — score ${pct(currentTicket.validation_score)}${iters ? ` (${iters} iteration${iters > 1 ? 's' : ''})` : ''}`);
  }).catch(e => toast('Heal failed: ' + e.message, true));
}

async function approveTicket() {
  try {
    currentTicket = await apiFetch(`/tickets/${ticketId}/approve`, { method: 'POST' });
    renderTicket(currentTicket);
    toast('Approved — ticket is now open');
  } catch { toast('Approve failed', true); }
}

async function rejectTicket() {
  if (!confirm('Reject this draft ticket?')) return;
  try {
    await apiFetch(`/tickets/${ticketId}/reject`, { method: 'POST' });
    window.location.href = '/review';
  } catch { toast('Reject failed', true); }
}

async function splitTicket() {
  const btn = document.getElementById('split-btn');
  await withLoading(btn, '⎇ Splitting…', async () => {
    const children = await apiFetch(`/agents/split/${ticketId}`, { method: 'POST' });
    toast(`Split into ${children.length} sub-ticket(s) ✓`);
    loadChildren();
  }).catch(e => toast('Split failed: ' + e.message, true));
}

async function deleteTicket() {
  if (!confirm(`Delete "${currentTicket.title}"?`)) return;
  try {
    await apiFetch(`/tickets/${ticketId}`, { method: 'DELETE' });
    window.location.href = '/tickets';
  } catch { toast('Delete failed', true); }
}

// ── Edit modal ─────────────────────────────────────────────────────────────

function openEdit() {
  const t = currentTicket;
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

async function submitEdit() {
  const parentIdVal = document.getElementById('f-parent-id').value.trim();
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
    ticket_type: document.getElementById('f-type').value,
    parent_id: parentIdVal || null,
  };
  if (!payload.title) { toast('Title is required', true); return; }
  try {
    currentTicket = await apiFetch(`/tickets/${ticketId}`, { method: 'PUT', body: payload });
    renderTicket(currentTicket);
    closeModal();
    toast('Updated');
  } catch { toast('Save failed', true); }
}

// ── Init ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('modal').addEventListener('click', e => { if (e.target === e.currentTarget) closeModal(); });
  document.getElementById('edit-btn').addEventListener('click', openEdit);
  document.getElementById('enrich-btn').addEventListener('click', enrichTicket);
  document.getElementById('validate-btn').addEventListener('click', validateTicket);
  document.getElementById('heal-btn').addEventListener('click', healTicket);
  document.getElementById('split-btn').addEventListener('click', splitTicket);
  document.getElementById('delete-btn').addEventListener('click', deleteTicket);
  document.getElementById('approve-btn').addEventListener('click', approveTicket);
  document.getElementById('reject-btn').addEventListener('click', rejectTicket);
  document.getElementById('modal-save-btn').addEventListener('click', submitEdit);
  document.getElementById('modal-cancel-btn').addEventListener('click', closeModal);
  loadTicket();
});
