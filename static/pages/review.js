/* pages/review.js — draft review queue page */

let drafts = [];

async function loadDrafts() {
  const all = await apiFetch('/tickets');
  drafts = all.filter(t => t.status === 'draft');
  renderCards(drafts);
}

function renderCards(tickets) {
  const el = document.getElementById('cards-container');
  const count = tickets.length;
  document.getElementById('draft-count').textContent = count;

  const approveBtn = document.getElementById('approve-all-btn');
  const rejectBtn = document.getElementById('reject-all-btn');
  approveBtn.classList.toggle('visible', count > 0);
  rejectBtn.classList.toggle('visible', count > 0);

  if (!count) {
    el.innerHTML = `<div class="empty">
      <strong>No drafts pending review</strong>
      <p>AI-generated tickets will appear here for approval before entering the active backlog.</p>
      <a href="/tickets" class="btn btn-ghost" style="display:inline-block;font-size:14px;padding:7px 18px;border-radius:4px;text-decoration:none">← Back to Tickets</a>
    </div>`;
    return;
  }
  el.innerHTML = `<div class="cards-grid">${tickets.map(renderCard).join('')}</div>`;
}

function renderCard(t) {
  const imp = t.importance || 'medium';
  const valHtml = t.validation_passed === true
    ? `<span class="val-score-pass">✓ ${pct(t.validation_score)}</span>`
    : t.validation_passed === false
      ? `<span class="val-score-fail">✗ ${pct(t.validation_score)}</span>`
      : `<span class="val-score-none">not validated</span>`;
  const repoHtml = t.source_repo
    ? `<span title="${esc(t.source_repo)}">${esc(repoShort(t.source_repo))}</span>` : '';
  const desc = t.description || t.business_req || '';

  return `<div class="draft-card" id="card-${t.id}">
    <div class="card-top">
      <div class="card-title"><a href="/tickets/${t.id}">${esc(t.title)}</a></div>
      <div class="card-badges">
        <span class="badge b-draft">Draft</span>
        <span class="badge p-${t.priority}">${t.priority}</span>
        <span class="badge i-${imp}">${imp}</span>
      </div>
      ${desc ? `<div class="card-desc">${esc(desc)}</div>` : ''}
      <div class="card-meta">
        <span>val: ${valHtml}</span>
        ${repoHtml ? `<span>${repoHtml}</span>` : ''}
        <span>${fmtDate(t.created_at)}</span>
      </div>
    </div>
    <div class="card-actions">
      <button class="btn btn-approve approve-btn" data-id="${t.id}">✓ Approve</button>
      <button class="btn btn-reject reject-btn" data-id="${t.id}">✗ Reject</button>
      <a href="/tickets/${t.id}" class="btn-view">View →</a>
    </div>
  </div>`;
}

async function approveTicket(id) {
  const card = document.getElementById(`card-${id}`);
  card.classList.add('fading');
  try {
    await apiFetch(`/tickets/${id}/approve`, { method: 'POST' });
    card.remove();
    drafts = drafts.filter(t => t.id !== id);
    renderCards(drafts);
    toast('Approved — ticket is now open');
  } catch {
    card.classList.remove('fading');
    toast('Approve failed', true);
  }
}

async function rejectTicket(id) {
  const card = document.getElementById(`card-${id}`);
  card.classList.add('fading');
  try {
    await apiFetch(`/tickets/${id}/reject`, { method: 'POST' });
    card.remove();
    drafts = drafts.filter(t => t.id !== id);
    renderCards(drafts);
    toast('Rejected');
  } catch {
    card.classList.remove('fading');
    toast('Reject failed', true);
  }
}

async function approveAll() {
  const btn = document.getElementById('approve-all-btn');
  let count = 0;
  await withLoading(btn, 'Approving…', async () => {
    for (const t of [...drafts]) {
      try { await apiFetch(`/tickets/${t.id}/approve`, { method: 'POST' }); count++; } catch { /* skip */ }
    }
  });
  toast(`Approved ${count} ticket(s)`);
  loadDrafts();
}

async function rejectAll() {
  if (!confirm(`Reject all ${drafts.length} draft tickets?`)) return;
  const btn = document.getElementById('reject-all-btn');
  let count = 0;
  await withLoading(btn, 'Rejecting…', async () => {
    for (const t of [...drafts]) {
      try { await apiFetch(`/tickets/${t.id}/reject`, { method: 'POST' }); count++; } catch { /* skip */ }
    }
  });
  toast(`Rejected ${count} ticket(s)`);
  loadDrafts();
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('approve-all-btn').addEventListener('click', approveAll);
  document.getElementById('reject-all-btn').addEventListener('click', rejectAll);

  // Event delegation for per-card approve/reject
  document.getElementById('cards-container').addEventListener('click', e => {
    const approve = e.target.closest('.approve-btn');
    if (approve) { approveTicket(approve.dataset.id); return; }
    const reject = e.target.closest('.reject-btn');
    if (reject) { rejectTicket(reject.dataset.id); }
  });

  loadDrafts();
});
