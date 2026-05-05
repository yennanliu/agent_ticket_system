# Frontend Refactor Plan

## Current State

Five self-contained HTML files, each embedding its own `<style>` block and `<script>` block.
No shared files whatsoever — everything is copy-pasted.

| File | Total lines | Style lines | Script lines |
|---|---|---|---|
| `index.html` | 931 | 407 | 395 |
| `landing.html` | 711 | 520 | 32 |
| `ticket.html` | 802 | 337 | 272 |
| `review.html` | 492 | 287 | 166 |
| `logs.html` | 314 | 166 | 105 |
| **Total** | **3250** | **1717** | **970** |

Rough estimate: **~60 % of that is duplication** that could be eliminated.

---

## 1. Extract Shared CSS → `static/shared.css`

### What is duplicated across all 5 files (verbatim or near-verbatim)

| CSS block | Files | Lines each |
|---|---|---|
| `:root` theme tokens | 5 | ~32 |
| `[data-theme="light"]` override | 5 | ~26 |
| Reset (`* { box-sizing }`, `html`, `body`) | 5 | ~8 |
| Header (`header`, `.logo`, `.header-sep`, `.nav-link`, `.spacer`) | 5 | ~14 |
| `.btn-theme` toggle button | 5 | ~8 |
| `.btn`, `.btn-primary`, `.btn-ghost`, `.btn-secondary`, `.btn-violet` | 4 | ~18 |
| `.badge` + all badge skins (`.s-open`, `.p-high`, `.i-critical`, etc.) | 4 | ~25 |
| `.label-chip` | 4 | ~6 |
| `#toast` + `#toast.show` + `#toast.error` | 4 | ~8 |
| `.spinner` + `@keyframes spin` | 3 | ~8 |
| `.modal-overlay`, `.modal`, `.modal label`, modal inputs | 2 | ~35 |

**Proposed `static/shared.css` sections:**

```
1. CSS custom properties  (:root dark + [data-theme="light"])
2. Reset
3. Typography helpers     (.mono, .mono-sm)
4. Layout primitives      (header, .logo, .header-sep, .nav-link, .spacer)
5. Button system          (.btn, .btn-primary, .btn-ghost, .btn-secondary,
                           .btn-violet, .btn-theme, .btn-xs, .btn-danger)
6. Badge system           (.badge, .s-*, .p-*, .i-*, .label-chip, .repo-chip)
7. Validation cells       (.val-pass, .val-fail, .val-none,
                           .val-badge-pass, .val-badge-fail, .val-badge-pending)
8. Spinner                (.spinner, @keyframes spin)
9. Toast                  (#toast)
10. Modal                 (.modal-overlay, .modal, .modal label, etc.)
11. Empty state           (.empty)
12. Enriched dot          (.enriched-dot)
```

Each HTML file then keeps **only** its page-specific styles (toolbar, stat bar, table, card grid, hero, etc.).

After extraction, estimated per-file style savings:
- `index.html`: ~200 lines removed (of 407)
- `ticket.html`: ~180 lines removed (of 337)
- `review.html`: ~160 lines removed (of 287)
- `logs.html`: ~90 lines removed (of 166)
- `landing.html`: ~80 lines removed (of 520, landing has more unique styles)

---

## 2. Extract Shared JS → `static/shared.js`

### Functions duplicated across files

| Function | Files | Notes |
|---|---|---|
| `initTheme()` | 5 | identical |
| `toggleTheme()` | 5 | identical |
| `applyTheme(theme)` | 5 | identical |
| `esc(s)` | 4 | identical |
| `toast(msg, isError)` | 4 | identical |
| `pct(score)` | 3 | near-identical (minor `''` vs `'—'` difference) |
| `repoShort(s)` | 3 | identical |
| `fmtDate(s)` | 2 | identical |

**Proposed `static/shared.js` contents:**

```js
// 1. API base
const API = '/api';

// 2. Theme
function initTheme() { ... }
function toggleTheme() { ... }
function applyTheme(theme) { ... }

// 3. Formatting utilities
function esc(s) { ... }
function pct(score, fallback = '—') { ... }
function repoShort(s) { ... }
function fmtDate(s) { ... }
function fmtDateTime(s) { ... }   // merge fmtDate + fmt used in ticket.html

// 4. Toast
function toast(msg, isError = false) { ... }

// 5. API helpers
async function apiFetch(path, options = {}) {
  // centralises: Content-Type header, error handling, response parsing
}
```

`apiFetch` eliminates the repeated pattern:
```js
// Currently in every call site:
const res = await fetch(`${API}/agents/enrich/${id}`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body)
});
if (!res.ok) throw new Error(await res.text());
```

Becomes:
```js
await apiFetch(`/agents/enrich/${id}`, { method: 'POST', body });
```

`apiFetch` handles the base URL prefix, `Content-Type`, JSON serialisation, and error extraction in one place. Any future auth headers or base URL change happens in one file.

---

## 3. Use Jinja2 Base Template → `templates/base.html`

This addresses the deepest duplication: the full `<head>`, `<header>` HTML, and `<div id="toast">` are copy-pasted in all 5 files.

### Migration

**Install** (already available in `fastapi[standard]`):
```python
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="templates")
```

**`templates/base.html`** provides:
```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Agent Ticket System{% endblock %}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="...Inter + JetBrains Mono..." rel="stylesheet">
  <link rel="stylesheet" href="/static/shared.css">
  {% block head %}{% endblock %}
</head>
<body>
<header>
  <a href="/" class="logo-link"><span class="logo">⬡ Tickets</span></a>
  <div class="header-sep"></div>
  {% block nav %}
  <a href="/tickets" class="nav-link {% if active == 'tickets' %}active{% endif %}">Tickets</a>
  <a href="/logs"    class="nav-link {% if active == 'logs'    %}active{% endif %}">Logs</a>
  {% endblock %}
  <div class="spacer"></div>
  <button class="btn-theme" id="theme-btn" onclick="toggleTheme()">☀ Bright</button>
  {% block header_actions %}{% endblock %}
</header>

{% block content %}{% endblock %}

<div id="toast"></div>
<script src="/static/shared.js"></script>
{% block scripts %}{% endblock %}
</body>
</html>
```

**`templates/index.html`** becomes:
```html
{% extends "base.html" %}
{% block title %}Tickets — ATS{% endblock %}
{% block head %}<link rel="stylesheet" href="/static/index.css">{% endblock %}
{% block header_actions %}
  <button class="btn btn-ghost" onclick="openBatchCreate()">Batch Create</button>
  <button class="btn btn-primary" onclick="openCreate()">+ New Ticket</button>
{% endblock %}
{% block content %}
  <div id="toolbar">...</div>
  ...
{% endblock %}
{% block scripts %}<script src="/static/index.js"></script>{% endblock %}
```

**`main.py`** route change (minimal):
```python
# Before:
@app.get("/tickets")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

# After:
@app.get("/tickets")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "active": "tickets"})
```

### What gets eliminated from every page

| Element | Current | After |
|---|---|---|
| `<meta charset>` + `<meta viewport>` | ×5 | ×1 in base |
| Google Fonts `<link>` | ×5 | ×1 in base |
| `<link rel="stylesheet" href="shared.css">` | ×5 | ×1 in base |
| Full `<header>` block (~8 lines) | ×5 | ×1 in base |
| `<div id="toast"></div>` | ×4 | ×1 in base |
| `<script src="shared.js"></script>` | ×5 | ×1 in base |

---

## 4. Additional Code Quality Improvements

### 4a. Replace `onclick=` with `addEventListener`

Currently **40 inline `onclick=` handlers** across the 5 files. The pattern:
```html
<button onclick="openCreate()">+ New Ticket</button>
```
should become:
```html
<button id="new-ticket-btn">+ New Ticket</button>
<!-- in the JS file: -->
document.getElementById('new-ticket-btn').addEventListener('click', openCreate);
```

Inline handlers:
- pollute the global scope (every handler must be a global function)
- can't be tested without a browser
- mix structure and behaviour

The event delegation pattern already used in index.html for row checkboxes is the right model — extend it everywhere.

### 4b. Fix the `JSON.stringify` in onclick (XSS risk)

In `index.html`, the Edit button is rendered as:
```js
`<button onclick='openEdit(${JSON.stringify(t)})'>`
```

This is fragile: any ticket with a single-quote or backtick in a field will break the event handler, and it bypasses `esc()`. The fix: store ticket data in a `data-id` attribute, look it up from `currentTickets` by ID in the handler.

```js
// Render:
`<button class="btn-xs edit-btn" data-id="${t.id}">Edit</button>`

// Handler:
container.addEventListener('click', e => {
  const btn = e.target.closest('.edit-btn');
  if (btn) openEdit(currentTickets.find(t => t.id === btn.dataset.id));
});
```

### 4c. Separate page-specific JS into individual files

After creating `shared.js`, each page's logic goes into its own file:

```
static/
  shared.css
  shared.js
  pages/
    index.js       (ticket list, filters, modals, selection)
    ticket.js      (ticket detail, enrich/validate/heal, edit modal)
    review.js      (draft queue, approve/reject)
    logs.js        (log table, filter, clear)
    landing.js     (stats load only — very small)
```

This makes each file ~100–150 lines of pure page logic, easy to read and test.

### 4d. Centralise loading/button state management

The pattern:
```js
btn.disabled = true;
btn.innerHTML = '<span class="spinner"></span>Loading…';
// ... async work ...
btn.disabled = false;
btn.textContent = 'Original label';
```

appears ~12 times across the files. A shared helper in `shared.js`:
```js
async function withLoading(btn, label, fn) {
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>${label}`;
  try { return await fn(); }
  finally { btn.disabled = false; btn.innerHTML = original; }
}
```

Usage:
```js
await withLoading(btn, 'Enriching…', () =>
  apiFetch(`/agents/enrich/${id}`, { method: 'POST', body })
);
```

### 4e. Move inline `style=""` to CSS classes

Currently 42 inline style attributes across the files. Examples:
```html
<!-- index.html -->
<div style="flex:1"></div>
<span id="selection-info" style="display:none;font-family:...;color:var(--accent)">

<!-- ticket.html -->
<div id="draft-banner" style="display:none;background:...;border:...;...">
```

Each should be a named CSS class in the page's stylesheet. Inline styles:
- can't be overridden by themes (they have specificity 1000)
- can't be reused
- make the HTML hard to read

### 4f. Merge `fmtDate` and `fmt` (ticket.html)

`ticket.html` defines `fmt(s)` (date + time) while other files use `fmtDate(s)` (date only). These should both live in `shared.js` as `fmtDate(s)` and `fmtDateTime(s)`.

### 4g. Unify `pct()` return value

`index.html` and `review.html` return `'—'` for null scores; `ticket.html` returns `''`. Pick `'—'` everywhere and centralise.

---

## 5. File Structure After Refactor

```
static/
├── shared.css           ← theme tokens, reset, buttons, badges, spinner, toast, modal
├── shared.js            ← theme, esc, toast, pct, repoShort, fmtDate, apiFetch, withLoading
└── pages/
    ├── index.css        ← toolbar, stat-bar, table, row styles, checkbox, action-btns
    ├── index.js         ← tickets CRUD, filters, selection, modals, kickstart pipeline
    ├── ticket.css       ← hero, page-layout, card, sidebar, val-bar, refs table
    ├── ticket.js        ← ticket detail, enrich/validate/heal/approve/reject
    ├── review.css       ← cards-grid, draft-card, card-top, card-actions
    ├── review.js        ← draft queue, approve/reject, bulk actions
    ├── logs.css         ← log table, event badges, filter bar
    ├── logs.js          ← log load, filter, render, clear
    ├── landing.css      ← hero, features, workflow, stats, CTA
    └── landing.js       ← stats load, theme init only

templates/
├── base.html            ← <head>, <header>, toast div, shared.css + shared.js links
├── index.html           ← extends base, toolbar + table content + modals
├── ticket.html          ← extends base, hero + page-layout + edit modal
├── review.html          ← extends base, toolbar + cards grid
├── logs.html            ← extends base, filter bar + log table
└── landing.html         ← extends base (minimal header), hero + sections
```

---

## 6. Suggested Migration Order

| Phase | Work | Impact |
|---|---|---|
| **1** | Extract `shared.css` + wire in all 5 files; delete duplicated CSS from each | Biggest line reduction, pure CSS, no behaviour risk |
| **2** | Extract `shared.js` (theme + utils + `apiFetch` + `withLoading`); delete from each file | Eliminates all JS duplication; `apiFetch` is the key new abstraction |
| **3** | Move to Jinja2 `base.html` + per-page templates; update `main.py` | Eliminates HTML structural duplication; `active` nav highlighting is a bonus |
| **4** | Per-page JS → `static/pages/*.js`; fix `JSON.stringify` onclick XSS | Separates concerns; pages become readable |
| **5** | Replace `onclick=` with `addEventListener`; move inline styles to classes | Code quality; enables testing |

Each phase is independently shippable — the app stays functional between steps.

---

## Summary of Gains

| Metric | Now | After |
|---|---|---|
| Total HTML/CSS/JS lines | ~3250 | ~1400 |
| Duplicated CSS | ~1000 lines | 0 |
| Duplicated JS utility code | ~150 lines | 0 |
| Files to edit when changing theme | 5 | 1 (`shared.css`) |
| Files to edit when changing header | 5 | 1 (`base.html`) |
| Files to edit when changing `toast()` | 4 | 1 (`shared.js`) |
| Inline `onclick=` handlers | 40 | 0 |
| Inline `style=` attributes | 42 | ~0 |
| `JSON.stringify` in HTML attributes | 1 (XSS risk) | 0 |
