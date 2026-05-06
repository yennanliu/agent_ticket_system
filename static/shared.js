/* shared.js — utilities loaded on every page */

// ── Theme ──────────────────────────────────────────────────────────────────
function initTheme() {
  applyTheme(localStorage.getItem('ats-theme') || 'dark');
}
function toggleTheme() {
  applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
}
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('ats-theme', theme);
  const btn = document.getElementById('theme-btn');
  if (btn) btn.textContent = theme === 'dark' ? '☀ Bright' : '◗ Dark';
}

// ── Formatting ─────────────────────────────────────────────────────────────
function esc(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function pct(score, fallback = '—') {
  return (score !== null && score !== undefined) ? Math.round(score * 100) + '%' : fallback;
}
function repoShort(s) {
  if (!s) return '';
  if (s.startsWith('http')) {
    try {
      const parts = new URL(s).pathname.split('/').filter(Boolean);
      return '⎇ ' + (parts.length >= 2 ? parts.slice(-2).join('/') : s);
    } catch { return s; }
  }
  return '📁 ' + (s.split('/').pop() || s);
}
function fmtDate(s) {
  return s ? new Date(s).toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: '2-digit' }) : '—';
}
function fmtDateTime(s) {
  return s ? new Date(s).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';
}

// ── Toast ──────────────────────────────────────────────────────────────────
function toast(msg, isError = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'show' + (isError ? ' error' : '');
  setTimeout(() => { el.className = ''; }, 3000);
}

// ── API helpers ────────────────────────────────────────────────────────────
async function apiFetch(path, { method = 'GET', body } = {}) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch('/api' + path, opts);
  if (!res.ok) throw new Error(await res.text());
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : null;
}

async function withLoading(btn, label, fn) {
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>${label}`;
  try { return await fn(); }
  finally { btn.disabled = false; btn.innerHTML = original; }
}

// ── Auto-init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  const themeBtn = document.getElementById('theme-btn');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);
});
