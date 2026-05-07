/**
 * Tests for static/pages/index.js — ticket list page logic.
 *
 * We load shared.js + index.js together in a single new Function() call so that
 * index.js functions can close over the shared utilities (esc, pct, repoShort, etc.)
 * and over the module-level let variables (currentTickets, showDrafts, enrichingIds).
 *
 * A setState helper is injected into the combined source so tests can reset state
 * between runs without having to reload the scripts.
 */
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { beforeEach, describe, it, expect, vi, afterEach } from 'vitest';

const __dirname = dirname(fileURLToPath(import.meta.url));

function stripDomInit(src) {
  const idx = src.indexOf("document.addEventListener('DOMContentLoaded'");
  return idx !== -1 ? src.slice(0, idx) : src;
}

/**
 * Load shared.js + index.js into a single isolated Function scope.
 * Returns all public functions plus a setState helper for resetting module state.
 */
function loadIndexFns(doc = document) {
  const sharedSrc = stripDomInit(
    readFileSync(resolve(__dirname, '../../static/shared.js'), 'utf8')
  );
  const indexSrc = stripDomInit(
    readFileSync(resolve(__dirname, '../../static/pages/index.js'), 'utf8')
  );

  const combined = `
    ${sharedSrc}
    ${indexSrc}
    function __setState(s) {
      if (s.currentTickets !== undefined) currentTickets = s.currentTickets;
      if (s.showDrafts !== undefined) showDrafts = s.showDrafts;
      if (s.enrichingIds !== undefined) enrichingIds = s.enrichingIds;
    }
    return {
      renderTable, updateStats, openCreate, openEdit, closeModal,
      openBatchCreate, closeBatchModal, toggleDrafts, updateDraftBadge,
      selectAll, deselectAll, updateSelectionUI,
      setState: __setState,
    };
  `;

  return new Function('document', 'window', 'localStorage', combined)(
    doc, window, localStorage
  );
}

// Minimal HTML skeleton that index.js functions need
function buildDOM() {
  document.body.innerHTML = `
    <div id="ticket-container"></div>
    <input id="repo-input" type="text" />
    <button id="generate-btn">Generate</button>
    <button id="enrich-all-btn">Enrich</button>
    <button id="new-ticket-btn">New</button>
    <button id="batch-create-btn">Batch</button>
    <button id="drafts-toggle">Show Drafts</button>
    <select id="status-filter"><option value="">All</option></select>
    <select id="type-filter"><option value="">All types</option></select>
    <select id="repo-filter"><option value="">All repos</option></select>
    <span id="stat-total">—</span>
    <span id="stat-open">—</span>
    <span id="stat-validated">—</span>
    <span id="stat-passrate">—</span>
    <span id="selection-info" style="display:none"></span>
    <button id="select-all-btn">Select All</button>
    <button id="deselect-all-btn">Deselect</button>
    <button id="delete-selected-btn" style="display:none">Delete</button>
    <div id="modal" class="modal-overlay"></div>
    <input id="modal-id" type="hidden" />
    <input id="f-title" type="text" />
    <textarea id="f-business-req"></textarea>
    <input id="f-stakeholder" type="text" />
    <textarea id="f-user-story"></textarea>
    <textarea id="f-desc"></textarea>
    <select id="f-status"><option value="open">Open</option></select>
    <select id="f-priority">
      <option value="low">Low</option>
      <option value="medium">Medium</option>
      <option value="high">High</option>
    </select>
    <select id="f-importance">
      <option value="low">Low</option>
      <option value="medium">Medium</option>
      <option value="high">High</option>
      <option value="critical">Critical</option>
    </select>
    <select id="f-type"><option value="task">task</option><option value="story">story</option><option value="epic">epic</option></select>
    <input id="f-parent-id" type="text" />
    <input id="f-labels" type="text" />
    <input id="f-repo" type="text" />
    <h2 id="modal-title"></h2>
    <button id="modal-save-btn">Save</button>
    <button id="modal-cancel-btn">Cancel</button>
    <div id="batch-modal" class="modal-overlay"></div>
    <textarea id="batch-titles"></textarea>
    <input id="batch-repo" type="text" />
    <button id="batch-save-btn">Create</button>
    <button id="batch-cancel-btn">Cancel</button>
    <div id="toast"></div>
    <a id="review-nav-link" style="display:none">Review</a>
    <span id="header-draft-count"></span>
    <button id="theme-btn">☀ Bright</button>
  `;
}

// Shared sample ticket factory
const mkTicket = (overrides = {}) => ({
  id: 'id1', title: 'Fix bug', status: 'open', priority: 'medium', importance: 'medium',
  labels: [], source_repo: '', acceptance_criteria: [],
  validation_passed: null, validation_score: null, created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

let fns;

beforeEach(() => {
  buildDOM();
  fns = loadIndexFns(document);
  fns.setState({ currentTickets: [], showDrafts: false, enrichingIds: new Set() });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ── renderTable() ─────────────────────────────────────────────────────────────
describe('renderTable()', () => {
  it('shows empty state when no tickets', () => {
    fns.renderTable([]);
    expect(document.getElementById('ticket-container').innerHTML)
      .toContain('No tickets yet');
  });

  it('renders one table row per ticket', () => {
    fns.renderTable([mkTicket(), mkTicket({ id: 'id2', title: 'T2' })]);
    expect(document.querySelectorAll('tbody tr').length).toBe(2);
  });

  it('shows the ticket title as a link', () => {
    fns.renderTable([mkTicket({ id: 'abc', title: 'My task' })]);
    const link = document.querySelector('.ticket-link');
    expect(link).not.toBeNull();
    expect(link.textContent).toContain('My task');
    expect(link.href).toContain('/tickets/abc');
  });

  it('shows enriched dot when acceptance_criteria present', () => {
    fns.renderTable([mkTicket({ acceptance_criteria: ['AC1'] })]);
    expect(document.querySelector('.enriched-dot')).not.toBeNull();
  });

  it('does NOT show enriched dot when no criteria', () => {
    fns.renderTable([mkTicket({ acceptance_criteria: [] })]);
    expect(document.querySelector('.enriched-dot')).toBeNull();
  });

  it('shows val-pass for validation_passed=true', () => {
    fns.renderTable([mkTicket({ validation_passed: true, validation_score: 0.9 })]);
    expect(document.querySelector('.val-pass')).not.toBeNull();
    expect(document.querySelector('.val-pass').textContent).toContain('90%');
  });

  it('shows val-fail for validation_passed=false', () => {
    fns.renderTable([mkTicket({ validation_passed: false, validation_score: 0.4 })]);
    expect(document.querySelector('.val-fail')).not.toBeNull();
  });

  it('shows val-none when not yet validated', () => {
    fns.renderTable([mkTicket({ validation_passed: null })]);
    expect(document.querySelector('.val-none')).not.toBeNull();
  });

  it('renders label chips for each label', () => {
    fns.renderTable([mkTicket({ labels: ['bug', 'ci', 'docs'] })]);
    const chips = document.querySelectorAll('.label-chip');
    expect(chips.length).toBe(3);
    const texts = [...chips].map(c => c.textContent);
    expect(texts).toContain('bug');
    expect(texts).toContain('ci');
  });

  it('uses data-id on edit button — no JSON.stringify in HTML (XSS prevention)', () => {
    const t = mkTicket({ id: 'safe1', title: '<script>alert(1)</script>' });
    fns.renderTable([t]);
    const editBtn = document.querySelector('.edit-btn');
    expect(editBtn).not.toBeNull();
    expect(editBtn.dataset.id).toBe('safe1');
    const html = document.getElementById('ticket-container').innerHTML;
    // Confirm no JSON.stringify inline event handler pattern
    expect(html).not.toContain('JSON.stringify');
    // The title inside the link text must be HTML-escaped
    const link = document.querySelector('.ticket-link');
    expect(link.innerHTML).toContain('&lt;script&gt;');
    expect(link.textContent).toContain('<script>alert(1)</script>');
  });

  it('adds is-draft class for draft tickets', () => {
    fns.renderTable([mkTicket({ status: 'draft' })]);
    expect(document.querySelector('tr.is-draft')).not.toBeNull();
  });

  it('adds is-rejected class for rejected tickets', () => {
    fns.renderTable([mkTicket({ status: 'rejected' })]);
    expect(document.querySelector('tr.is-rejected')).not.toBeNull();
  });

  it('shows repo chip when source_repo is set', () => {
    fns.renderTable([mkTicket({ source_repo: '../myrepo' })]);
    expect(document.querySelector('.repo-chip')).not.toBeNull();
  });
});

// ── updateStats() ─────────────────────────────────────────────────────────────
describe('updateStats()', () => {
  it('displays total ticket count', () => {
    fns.updateStats([
      { status: 'open', validation_passed: null },
      { status: 'done', validation_passed: true },
    ]);
    expect(document.getElementById('stat-total').textContent).toBe('2');
  });

  it('counts only open tickets', () => {
    fns.updateStats([
      { status: 'open', validation_passed: null },
      { status: 'open', validation_passed: null },
      { status: 'done', validation_passed: true },
    ]);
    expect(document.getElementById('stat-open').textContent).toBe('2');
  });

  it('counts validated tickets', () => {
    fns.updateStats([
      { status: 'open', validation_passed: true },
      { status: 'open', validation_passed: false },
      { status: 'open', validation_passed: null },
    ]);
    expect(document.getElementById('stat-validated').textContent).toBe('2');
  });

  it('calculates pass rate correctly', () => {
    fns.updateStats([
      { status: 'open', validation_passed: true },
      { status: 'open', validation_passed: false },
    ]);
    expect(document.getElementById('stat-passrate').textContent).toBe('50%');
  });

  it('shows — for pass rate when none validated', () => {
    fns.updateStats([{ status: 'open', validation_passed: null }]);
    expect(document.getElementById('stat-passrate').textContent).toBe('—');
  });

  it('handles 100% pass rate', () => {
    fns.updateStats([
      { status: 'open', validation_passed: true },
      { status: 'open', validation_passed: true },
    ]);
    expect(document.getElementById('stat-passrate').textContent).toBe('100%');
  });
});

// ── Selection UI ──────────────────────────────────────────────────────────────
describe('selection UI', () => {
  beforeEach(() => {
    fns.renderTable([
      mkTicket({ id: 'a' }),
      mkTicket({ id: 'b', title: 'T2' }),
    ]);
  });

  it('selectAll checks all checkboxes', () => {
    fns.selectAll();
    document.querySelectorAll('.row-check').forEach(cb => {
      expect(cb.checked).toBe(true);
    });
  });

  it('deselectAll unchecks all checkboxes', () => {
    fns.selectAll();
    fns.deselectAll();
    document.querySelectorAll('.row-check').forEach(cb => {
      expect(cb.checked).toBe(false);
    });
  });

  it('updateSelectionUI hides info when nothing selected', () => {
    fns.deselectAll();
    fns.updateSelectionUI();
    expect(document.getElementById('selection-info').style.display).toBe('none');
    expect(document.getElementById('delete-selected-btn').style.display).toBe('none');
  });

  it('updateSelectionUI shows count when items selected', () => {
    fns.selectAll();
    fns.updateSelectionUI();
    const info = document.getElementById('selection-info').textContent;
    expect(info).toContain('2');
    const btnText = document.getElementById('delete-selected-btn').textContent;
    expect(btnText).toContain('Delete');
    expect(btnText).toContain('2');
  });
});

// ── Modal helpers ─────────────────────────────────────────────────────────────
describe('modal helpers', () => {
  it('openCreate clears all fields', () => {
    document.getElementById('f-title').value = 'existing';
    document.getElementById('f-desc').value = 'existing desc';
    fns.openCreate();
    expect(document.getElementById('f-title').value).toBe('');
    expect(document.getElementById('f-desc').value).toBe('');
  });

  it('openCreate opens the modal', () => {
    fns.openCreate();
    expect(document.getElementById('modal').classList.contains('open')).toBe(true);
  });

  it('openCreate sets modal title to New Ticket', () => {
    fns.openCreate();
    expect(document.getElementById('modal-title').textContent).toBe('New Ticket');
  });

  it('closeModal removes the open class', () => {
    fns.openCreate();
    fns.closeModal();
    expect(document.getElementById('modal').classList.contains('open')).toBe(false);
  });

  it('openEdit populates fields from ticket data', () => {
    const t = {
      id: 'ed1', title: 'Edit me', description: 'Some desc', status: 'open',
      priority: 'high', importance: 'critical',
      labels: ['a', 'b'], source_repo: '/tmp',
      business_req: 'req', stakeholder: 'eng', user_story: 'story',
    };
    fns.openEdit(t);
    expect(document.getElementById('f-title').value).toBe('Edit me');
    expect(document.getElementById('f-priority').value).toBe('high');
    expect(document.getElementById('f-labels').value).toBe('a, b');
    expect(document.getElementById('modal-id').value).toBe('ed1');
    expect(document.getElementById('modal-title').textContent).toBe('Edit Ticket');
  });

  it('openEdit opens the modal', () => {
    fns.openEdit({ id: 'x', title: 'T', description: '', status: 'open',
      priority: 'low', importance: 'low', labels: [], source_repo: '',
      business_req: '', stakeholder: '', user_story: '' });
    expect(document.getElementById('modal').classList.contains('open')).toBe(true);
  });

  it('openBatchCreate clears batch fields', () => {
    document.getElementById('batch-titles').value = 'existing\nlines';
    fns.openBatchCreate();
    expect(document.getElementById('batch-titles').value).toBe('');
  });

  it('closeBatchModal removes open class', () => {
    fns.openBatchCreate();
    fns.closeBatchModal();
    expect(document.getElementById('batch-modal').classList.contains('open')).toBe(false);
  });
});

// ── toggleDrafts() ────────────────────────────────────────────────────────────
describe('toggleDrafts()', () => {
  it('flips showDrafts from false to true', () => {
    fns.setState({ showDrafts: false });
    fns.toggleDrafts();
    expect(document.getElementById('drafts-toggle').textContent).toBe('Hide Drafts');
  });

  it('flips showDrafts from true to false', () => {
    fns.setState({ showDrafts: true });
    fns.toggleDrafts();
    expect(document.getElementById('drafts-toggle').textContent).toBe('Show Drafts');
  });
});

// ── updateDraftBadge() ────────────────────────────────────────────────────────
describe('updateDraftBadge()', () => {
  it('shows review link and badge count when drafts exist', () => {
    fns.updateDraftBadge([
      { status: 'draft' }, { status: 'draft' }, { status: 'open' },
    ]);
    expect(document.getElementById('review-nav-link').style.display).not.toBe('none');
    expect(document.getElementById('header-draft-count').textContent).toBe('2');
  });

  it('hides review link when no drafts', () => {
    fns.updateDraftBadge([{ status: 'open' }, { status: 'done' }]);
    expect(document.getElementById('review-nav-link').style.display).toBe('none');
  });

  it('hides review link for empty ticket list', () => {
    fns.updateDraftBadge([]);
    expect(document.getElementById('review-nav-link').style.display).toBe('none');
  });
});
