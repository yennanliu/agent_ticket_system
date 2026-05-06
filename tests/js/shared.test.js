/**
 * Tests for static/shared.js utility functions.
 *
 * shared.js is a plain browser script (no ES module exports), so we load it
 * via new Function() with explicit DOM globals passed in, then collect the
 * returned function handles.  This keeps each test suite isolated from DOM state.
 */
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { beforeEach, describe, it, expect, vi, afterEach } from 'vitest';

const __dirname = dirname(fileURLToPath(import.meta.url));

/**
 * Load shared.js in an isolated Function scope.
 * Strips the DOMContentLoaded auto-init block, passes browser globals as
 * parameters, and returns every public function as a named object.
 */
function loadShared({ doc = document, win = window, ls = localStorage } = {}) {
  let src = readFileSync(resolve(__dirname, '../../static/shared.js'), 'utf8');
  const domIdx = src.indexOf("document.addEventListener('DOMContentLoaded'");
  if (domIdx !== -1) src = src.slice(0, domIdx);

  return new Function(
    'document', 'window', 'localStorage',
    `${src}
     return { esc, pct, repoShort, fmtDate, fmtDateTime, toast,
              apiFetch, withLoading, initTheme, toggleTheme, applyTheme };`
  )(doc, win, ls);
}

// ── esc() ──────────────────────────────────────────────────────────────────────
describe('esc()', () => {
  const { esc } = loadShared();

  it('escapes ampersands', () => {
    expect(esc('a & b')).toBe('a &amp; b');
  });
  it('escapes < and >', () => {
    expect(esc('<script>')).toBe('&lt;script&gt;');
  });
  it('escapes double quotes', () => {
    expect(esc('"hello"')).toBe('&quot;hello&quot;');
  });
  it('handles null gracefully', () => {
    expect(esc(null)).toBe('');
  });
  it('handles undefined gracefully', () => {
    expect(esc(undefined)).toBe('');
  });
  it('handles empty string', () => {
    expect(esc('')).toBe('');
  });
  it('coerces non-string values', () => {
    expect(esc(42)).toBe('42');
  });
  it('is idempotent on plain text', () => {
    expect(esc('hello world')).toBe('hello world');
  });
});

// ── pct() ─────────────────────────────────────────────────────────────────────
describe('pct()', () => {
  const { pct } = loadShared();

  it('converts 0.75 to 75%', () => expect(pct(0.75)).toBe('75%'));
  it('converts 1.0 to 100%', () => expect(pct(1.0)).toBe('100%'));
  it('converts 0 to 0%', () => expect(pct(0)).toBe('0%'));
  it('rounds 0.333 to 33%', () => expect(pct(0.333)).toBe('33%'));
  it('rounds 0.666 to 67%', () => expect(pct(0.666)).toBe('67%'));
  it('returns — for null', () => expect(pct(null)).toBe('—'));
  it('returns — for undefined', () => expect(pct(undefined)).toBe('—'));
  it('accepts a custom fallback string', () => expect(pct(null, 'N/A')).toBe('N/A'));
  it('returns 0% for score=0, not the fallback', () => expect(pct(0, 'none')).toBe('0%'));
});

// ── repoShort() ───────────────────────────────────────────────────────────────
describe('repoShort()', () => {
  const { repoShort } = loadShared();

  it('returns empty string for empty input', () => expect(repoShort('')).toBe(''));
  it('returns empty string for null', () => expect(repoShort(null)).toBe(''));
  it('extracts owner/repo from a GitHub URL', () => {
    expect(repoShort('https://github.com/owner/repo')).toBe('⎇ owner/repo');
  });
  it('handles org names correctly', () => {
    expect(repoShort('https://github.com/org/name')).toBe('⎇ org/name');
  });
  it('formats a local relative path', () => {
    expect(repoShort('../my-project')).toBe('📁 my-project');
  });
  it('formats an absolute local path', () => {
    expect(repoShort('/home/user/projects/myapp')).toBe('📁 myapp');
  });
  it('handles a single-segment URL path', () => {
    const result = repoShort('https://example.com/repo');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });
});

// ── fmtDate() ─────────────────────────────────────────────────────────────────
describe('fmtDate()', () => {
  const { fmtDate } = loadShared();

  it('returns — for null', () => expect(fmtDate(null)).toBe('—'));
  it('returns — for empty string', () => expect(fmtDate('')).toBe('—'));
  it('formats an ISO date string', () => {
    const result = fmtDate('2024-06-15T00:00:00Z');
    expect(result).toMatch(/\d{2}\/\d{2}\/\d{2}/);
  });
  it('returns a string', () => {
    expect(typeof fmtDate('2024-01-01T00:00:00Z')).toBe('string');
  });
});

// ── fmtDateTime() ─────────────────────────────────────────────────────────────
describe('fmtDateTime()', () => {
  const { fmtDateTime } = loadShared();

  it('returns — for null', () => expect(fmtDateTime(null)).toBe('—'));
  it('returns — for empty string', () => expect(fmtDateTime('')).toBe('—'));
  it('returns a non-empty string for a valid date', () => {
    const result = fmtDateTime('2024-06-15T12:30:00Z');
    expect(typeof result).toBe('string');
    expect(result).not.toBe('—');
    expect(result.length).toBeGreaterThan(5);
  });
});

// ── toast() ───────────────────────────────────────────────────────────────────
describe('toast()', () => {
  let toastEl;
  let fns;

  beforeEach(() => {
    // Create a fresh DOM element for each test
    toastEl = document.createElement('div');
    toastEl.id = 'toast';
    document.body.appendChild(toastEl);
    fns = loadShared({ doc: document, win: window, ls: localStorage });
    vi.useFakeTimers();
  });

  afterEach(() => {
    document.body.removeChild(toastEl);
    vi.useRealTimers();
  });

  it('sets the text content', () => {
    fns.toast('Hello world');
    expect(toastEl.textContent).toBe('Hello world');
  });
  it('adds the show class', () => {
    fns.toast('Test');
    expect(toastEl.className).toContain('show');
  });
  it('adds error class when isError=true', () => {
    fns.toast('Oops', true);
    expect(toastEl.className).toContain('error');
  });
  it('does not add error class for normal toast', () => {
    fns.toast('OK');
    expect(toastEl.className).not.toContain('error');
  });
  it('clears class after 3 seconds', () => {
    fns.toast('Timed');
    vi.advanceTimersByTime(3000);
    expect(toastEl.className).toBe('');
  });
});

// ── theme functions ────────────────────────────────────────────────────────────
describe('theme functions', () => {
  let themeBtn;
  let fakeDoc;
  let fakeLs;
  let fns;

  beforeEach(() => {
    // Build a minimal fake DOM to avoid polluting shared jsdom state
    themeBtn = document.createElement('button');
    themeBtn.id = 'theme-btn';
    document.body.appendChild(themeBtn);
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.clear();
    fns = loadShared({ doc: document, win: window, ls: localStorage });
  });

  afterEach(() => {
    document.body.removeChild(themeBtn);
  });

  it('applyTheme sets data-theme attribute', () => {
    fns.applyTheme('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });
  it('applyTheme saves to localStorage', () => {
    fns.applyTheme('light');
    expect(localStorage.getItem('ats-theme')).toBe('light');
  });
  it('applyTheme updates button text to ◗ Dark for light theme', () => {
    fns.applyTheme('light');
    expect(themeBtn.textContent).toBe('◗ Dark');
  });
  it('applyTheme updates button text to ☀ Bright for dark theme', () => {
    fns.applyTheme('dark');
    expect(themeBtn.textContent).toBe('☀ Bright');
  });
  it('toggleTheme switches dark → light', () => {
    document.documentElement.setAttribute('data-theme', 'dark');
    fns.toggleTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });
  it('toggleTheme switches light → dark', () => {
    document.documentElement.setAttribute('data-theme', 'light');
    fns.toggleTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });
  it('initTheme reads from localStorage', () => {
    localStorage.setItem('ats-theme', 'light');
    fns.initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });
  it('initTheme defaults to dark when nothing stored', () => {
    localStorage.removeItem('ats-theme');
    fns.initTheme();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });
});

// ── apiFetch() ────────────────────────────────────────────────────────────────
describe('apiFetch()', () => {
  let mockFetch;
  let fns;

  beforeEach(() => {
    mockFetch = vi.fn();
    // Pass a controlled fake fetch so apiFetch uses it
    fns = loadShared({ doc: document, win: window, ls: localStorage });
    // Stub the global fetch that apiFetch calls
    vi.stubGlobal('fetch', mockFetch);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('prefixes the path with /api', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({}),
    });
    await fns.apiFetch('/tickets');
    expect(mockFetch).toHaveBeenCalledWith('/api/tickets', expect.any(Object));
  });

  it('uses GET by default', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => [],
    });
    await fns.apiFetch('/tickets');
    expect(mockFetch.mock.calls[0][1].method).toBe('GET');
  });

  it('serialises body and sets Content-Type for POST', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({}),
    });
    await fns.apiFetch('/tickets', { method: 'POST', body: { title: 'T' } });
    const opts = mockFetch.mock.calls[0][1];
    expect(opts.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(opts.body)).toEqual({ title: 'T' });
  });

  it('throws an error on non-ok response', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      text: async () => 'Internal server error',
    });
    await expect(fns.apiFetch('/bad')).rejects.toThrow('Internal server error');
  });

  it('returns null for non-JSON content-type', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => 'text/plain' },
      text: async () => 'ok',
    });
    const result = await fns.apiFetch('/endpoint', { method: 'DELETE' });
    expect(result).toBeNull();
  });

  it('parses and returns JSON for application/json responses', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => [{ id: '1', title: 'T' }],
    });
    const result = await fns.apiFetch('/tickets');
    expect(result).toEqual([{ id: '1', title: 'T' }]);
  });
});

// ── withLoading() ─────────────────────────────────────────────────────────────
describe('withLoading()', () => {
  const { withLoading } = loadShared();

  it('disables the button while fn runs', async () => {
    const btn = document.createElement('button');
    btn.innerHTML = 'Click me';
    let wasDisabled = false;
    await withLoading(btn, 'Loading…', async () => { wasDisabled = btn.disabled; });
    expect(wasDisabled).toBe(true);
  });

  it('restores the original innerHTML after fn completes', async () => {
    const btn = document.createElement('button');
    btn.innerHTML = 'Go';
    await withLoading(btn, 'Working…', async () => {});
    expect(btn.innerHTML).toBe('Go');
    expect(btn.disabled).toBe(false);
  });

  it('includes the label in the loading HTML', async () => {
    const btn = document.createElement('button');
    btn.innerHTML = 'Save';
    let htmlDuring = '';
    await withLoading(btn, 'Saving…', async () => { htmlDuring = btn.innerHTML; });
    expect(htmlDuring).toContain('Saving…');
    expect(htmlDuring).toContain('spinner');
  });

  it('restores the button even when fn throws', async () => {
    const btn = document.createElement('button');
    btn.innerHTML = 'Original';
    try {
      await withLoading(btn, 'Running…', async () => { throw new Error('boom'); });
    } catch { /* expected */ }
    expect(btn.disabled).toBe(false);
    expect(btn.innerHTML).toBe('Original');
  });

  it('propagates errors from fn', async () => {
    const btn = document.createElement('button');
    btn.innerHTML = 'X';
    await expect(
      withLoading(btn, 'Loading…', async () => { throw new Error('from fn'); })
    ).rejects.toThrow('from fn');
  });

  it('returns the value from fn', async () => {
    const btn = document.createElement('button');
    btn.innerHTML = 'X';
    const result = await withLoading(btn, 'Running…', async () => 42);
    expect(result).toBe(42);
  });
});
