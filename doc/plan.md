# Agent Ticket System — Design Plan

## Overview

An AI-powered ticket management system that analyzes a software project and automatically generates and enriches task tickets. The demo project used for testing is `../linkedin-skill` (a local Node.js LinkedIn automation plugin).

---

## Goals

1. **Auto-create** task tickets by analyzing a repo (README, source files, skills, CI config)
2. **Auto-enrich** existing tickets with acceptance criteria, related files, and technical notes
3. **Full CRUD** — view, list, edit, create, delete tickets via a simple web UI
4. **No database or RAG** — in-memory storage persisted to a single JSON file
5. **Simple stack** — Python + uv + FastAPI + LangGraph + OpenAI + plain HTML/JS

---

## Development Approach: TDD

We follow **Red → Green → Refactor**:
1. Write a failing test for each unit
2. Write the minimum implementation to make it pass
3. Refactor if needed

Test runner: `pytest` + `httpx` (for async FastAPI test client). Agent nodes are tested with mocked LLM calls (no real API calls in unit tests).

---

## Project Structure

```
agent_ticket_system/
├── pyproject.toml          # uv-managed dependencies (includes pytest, httpx)
├── main.py                 # FastAPI app: mounts static files, includes routers
├── .env.example            # Template for required environment variables
├── app/
│   ├── models.py           # Pydantic Ticket model
│   ├── storage.py          # In-memory dict + JSON file persistence
│   ├── repo_tools.py       # Read local repo path or GitHub URL
│   ├── agents/
│   │   ├── creator.py      # LangGraph agent: repo → list of tickets
│   │   └── enricher.py     # LangGraph agent: ticket → enriched ticket
│   └── api/
│       ├── tickets.py      # CRUD router (/api/tickets)
│       └── agents.py       # Agent trigger router (/api/agents)
├── tests/
│   ├── conftest.py         # Shared fixtures (test client, sample tickets, tmp data dir)
│   ├── test_models.py      # Ticket model validation tests
│   ├── test_storage.py     # Storage CRUD + persistence tests
│   ├── test_repo_tools.py  # Local path + GitHub URL reader tests (mocked)
│   ├── test_creator.py     # Creator agent tests (LLM mocked)
│   ├── test_enricher.py    # Enricher agent tests (LLM mocked)
│   └── test_api.py         # Full API endpoint tests via FastAPI test client
├── static/
│   └── index.html          # Frontend: ticket list, modals, auto-generate panel
├── data/                   # Auto-created at runtime; holds tickets.json
└── doc/
    └── plan.md             # This file
```

---

## Data Model

```python
class Ticket(BaseModel):
    id: str                       # UUID4, auto-generated
    title: str
    description: str
    status: str                   # "open" | "in_progress" | "done"
    priority: str                 # "low" | "medium" | "high"
    labels: list[str] = []
    source_repo: str = ""         # local path or GitHub URL used to generate it
    created_at: datetime
    updated_at: datetime
    # Populated by the enricher agent
    acceptance_criteria: list[str] = []
    related_files: list[str] = []
    technical_notes: str = ""
    suggested_assignee: str = ""
```

---

## Storage

- **In-memory**: `dict[str, Ticket]` for fast access
- **Persistence**: load from `data/tickets.json` on startup; write on every create/update/delete
- **Functions**: `get_all()`, `get(id)`, `create(ticket)`, `update(id, fields)`, `delete(id)`

---

## Repo Tools (`app/repo_tools.py`)

Reads project context for the LLM agents. Auto-detects mode from the input:

**Local path** (e.g. `../linkedin-skill` or `/Users/jliu/myproject`):
- Walk directory tree (skip `node_modules`, `.git`, `output`, `__pycache__`)
- Read key files: `README.md`, `SKILL.md`, `CLAUDE.md`, `CHANGELOG.md`, source files (`.js`, `.py`, `.ts`, `.json`) under relevant subdirs
- Cap total content at ~50 KB to stay within LLM context limits
- Return file tree summary + concatenated file contents

**GitHub URL** (e.g. `https://github.com/owner/repo`):
- Use `PyGithub` to fetch repo metadata, README, top-level file listing, and open issues (first 20)
- Requires `GITHUB_TOKEN` in `.env` for private repos; works without it for public repos

**Detection logic**: if the input starts with `http://` or `https://`, treat as GitHub URL; otherwise treat as local path.

**Output**: a `RepoContext` dict with keys `name`, `file_tree`, `readme`, `file_contents`.

---

## LangGraph Agents

### Creator Agent (`app/agents/creator.py`)

**Purpose:** Analyze a repo and generate a list of actionable task tickets.

**Graph:**
```
fetch_context → generate_tickets → save_tickets → END
```

**State:**
```python
class CreatorState(TypedDict):
    repo_path: str
    repo_context: dict
    ticket_drafts: list[dict]
    created_tickets: list[str]   # ticket IDs
```

**LLM call (`generate_tickets` node):**
- Prompt: "Given this project context, generate 5–10 actionable development task tickets as JSON."
- Use `with_structured_output` to get a typed list of ticket drafts directly
- Each draft: `{title, description, priority, labels}`

---

### Enricher Agent (`app/agents/enricher.py`)

**Purpose:** Take an existing ticket and add enrichment fields.

**Graph:**
```
fetch_ticket → fetch_context → enrich → save_ticket → END
```

**State:**
```python
class EnricherState(TypedDict):
    ticket_id: str
    repo_path: str
    ticket: dict
    repo_context: dict
    enriched_fields: dict
```

**LLM call (`enrich` node):**
- Prompt: "Given this ticket and repo context, fill in acceptance criteria, related files, and technical notes."
- Returns: `{acceptance_criteria: [...], related_files: [...], technical_notes: "...", suggested_assignee: "..."}`

---

## API Endpoints

| Method | Path | Request Body | Description |
|--------|------|-------------|-------------|
| GET | `/api/tickets` | — | List all tickets |
| GET | `/api/tickets/{id}` | — | Get one ticket |
| POST | `/api/tickets` | `{title, description, status, priority, labels}` | Create ticket manually |
| PUT | `/api/tickets/{id}` | any Ticket fields | Update a ticket |
| DELETE | `/api/tickets/{id}` | — | Delete a ticket |
| POST | `/api/agents/create-from-repo` | `{repo_path?, repo_url?}` | Auto-generate tickets from repo |
| POST | `/api/agents/enrich/{ticket_id}` | `{repo_path?, repo_url?}` | Auto-enrich one ticket |
| GET | `/` | — | Serve the HTML frontend |

---

## Frontend (`static/index.html`)

Single self-contained HTML file — no build step, no framework.

**Sections:**
- **Header bar** — app title + "New Ticket" button + "Generate from Repo" button
- **Repo panel** — input for local path or GitHub URL, "Generate Tickets" button (calls `POST /api/agents/create-from-repo`), shows spinner while running
- **Ticket table** — columns: Title, Status (color badge), Priority, Labels, Created, Actions
- **Actions per ticket** — Edit (pencil icon), Enrich (sparkle icon, calls `POST /api/agents/enrich/{id}`), Delete (trash icon)
- **Create/Edit modal** — form with all editable fields; submits to `POST` or `PUT`
- **Toast notifications** — success/error feedback without page reload

All data fetched via `fetch()` calls to the API. No page reloads.

---

## Dependencies (`pyproject.toml`)

```toml
[project]
name = "agent-ticket-system"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "langgraph>=0.2",
    "langchain-openai>=0.1",
    "openai>=1.30",
    "pydantic>=2.7",
    "python-dotenv>=1.0",
    "pygithub>=2.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",        # async FastAPI test client
]
```

---

## Environment Variables

```bash
# .env (copy from .env.example)
OPENAI_API_KEY=sk-...                 # required
OPENAI_MODEL=gpt-4o                   # optional, defaults to gpt-4o
GITHUB_TOKEN=ghp_...                  # optional, only needed for private GitHub repos
```

---

## How to Run

```bash
# 1. Install deps
uv sync

# 2. Copy and fill in env file
cp .env.example .env
# edit .env — add OPENAI_API_KEY

# 3. Start server
uv run uvicorn main:app --reload

# 4. Open browser
open http://localhost:8000
```

---

## TDD Implementation Order

Each layer follows **write test → implement → pass test**:

| Step | Test file | Implementation file |
|------|-----------|---------------------|
| 1 | `tests/test_models.py` | `app/models.py` |
| 2 | `tests/test_storage.py` | `app/storage.py` |
| 3 | `tests/test_repo_tools.py` | `app/repo_tools.py` |
| 4 | `tests/test_creator.py` | `app/agents/creator.py` |
| 5 | `tests/test_enricher.py` | `app/agents/enricher.py` |
| 6 | `tests/test_api.py` | `app/api/tickets.py`, `app/api/agents.py`, `main.py` |

### What each test file covers

**`test_models.py`** — Ticket creation, default values, field validation (invalid status/priority), datetime auto-set

**`test_storage.py`** — get_all returns list, get by id, create persists to file, update merges fields, delete removes entry, file reloads correctly on re-init

**`test_repo_tools.py`** — local path returns RepoContext with correct keys, skips excluded dirs, caps at 50KB; GitHub URL branch uses mocked PyGithub; detection logic picks correct branch

**`test_creator.py`** — graph runs end-to-end with mocked LLM returning fixture ticket drafts; tickets are saved to storage; returned IDs are valid UUIDs

**`test_enricher.py`** — loads existing ticket, merges enriched fields, saves updated ticket; mocked LLM returns acceptance_criteria + technical_notes

**`test_api.py`** — GET /api/tickets returns 200 + list; POST /api/tickets creates and returns ticket; PUT updates; DELETE removes; 404 on missing id; agent endpoints return created/enriched tickets (agents mocked)

---

## How to Run Tests

```bash
uv run pytest tests/ -v
```

---

## Verification Steps (manual, after all tests pass)

1. Server starts without errors: `uv run uvicorn main:app --reload`
2. `POST /api/agents/create-from-repo` with `{"repo_path": "../linkedin-skill"}` → returns 5–10 generated tickets
3. `GET /api/tickets` → lists all tickets with correct fields
4. `POST /api/agents/enrich/{id}` with `{"repo_path": "../linkedin-skill"}` → ticket now has `acceptance_criteria`, `technical_notes`, `related_files`
5. UI at `http://localhost:8000` renders the ticket table
6. Create, edit, and delete a ticket via the UI — changes persist after page reload

---

---

# Sprint 2 — Feature Roadmap

> Status: **Planning** — no code written yet.
> Priority order: Feature 1 → 2 → 3 → 4. Features 1–2 are pure backend-first; 3–4 need both.

---

## Feature 1: Self-healing Validation Loop

### Problem

The current validator runs once and stops. A ticket that scores 0.55 stays at 0.55 forever — the user has to manually re-enrich and re-validate. The validation notes already contain actionable feedback (e.g. "missing acceptance criteria", "description too vague") but nothing acts on them.

### Goal

After validation, if the score is below a threshold, automatically feed the validation notes back into the enricher as additional context and re-validate. Repeat up to a fixed cap. This makes the system self-improving without human intervention.

### Design

**New concept: heal loop**

```
validate
  → if score >= threshold OR iterations >= max: done
  → else: enrich_with_feedback → validate again
```

**Threshold and cap** (configurable via env or constants):
- `HEAL_THRESHOLD = 0.75` — below this, trigger a heal iteration
- `HEAL_MAX_ITERATIONS = 3` — hard cap to prevent infinite loops

**Data model changes** (add to `Ticket`):
- `validation_iterations: int = 0` — how many heal loops have run on this ticket
- No other model changes needed; existing `validation_notes`, `validation_score`, `validation_passed` already store the latest result

**New agent: `app/agents/healer.py`**

LangGraph graph:
```
load_ticket → validate_node → check_threshold (conditional) → enrich_with_feedback → validate_node → ... → save_ticket → END
```

Key detail: the `enrich_with_feedback` node calls the enricher with an augmented prompt that includes the previous `validation_notes` as explicit instructions. Example extra context injected: *"The previous validation flagged: 'acceptance criteria too vague'. Please improve them."*

**New API endpoint:**
- `POST /api/agents/heal/{ticket_id}` — runs the full self-healing loop and returns the final ticket
- The existing `POST /api/agents/validate/{ticket_id}` can optionally auto-trigger heal (with a query param `?auto_heal=true`) — this keeps backward compatibility

**UI changes:**
- Ticket detail page: "Heal" button next to "Validate"
- Shows `validation_iterations` count as a small label (e.g. "healed 2×")
- After healing, re-renders the validation score bar and notes

### Edge cases / open questions

- If the ticket has no `source_repo`, the heal loop cannot re-enrich (no repo context). In this case, skip the enrich step and just log that healing is limited.
- The heal loop should only run on tickets that have been enriched at least once (have `acceptance_criteria`). On bare tickets, direct the user to enrich first.
- Should manual re-validation also auto-heal? Propose: no by default, opt-in via button.

---

## Feature 2: Draft Status + Human Approval Flow

### Problem

AI-generated tickets (from repo, batch, or inbox) go directly to `open` status. Teams can't trust or audit AI output without a review gate. There's no way to distinguish "AI suggested, unreviewed" from "human approved, ready to work on."

### Goal

AI-generated tickets land in `draft` status. A dedicated Review Queue lets a human quickly approve, edit, or reject each draft before it enters the active backlog.

### Design

**Data model changes:**

Extend the `status` enum to include `draft` and `rejected`:
```
status: "draft" | "open" | "in_progress" | "done" | "rejected"
```

- `draft` — AI-generated, awaiting human review
- `rejected` — reviewed and dismissed (soft-delete; stays queryable but hidden by default)

**Which creation paths produce drafts:**
- `POST /api/agents/create-from-repo` → all tickets created as `draft`
- `POST /api/agents/inbox-import` (Feature 4) → all tickets as `draft`
- `POST /api/agents/create-batch` → `draft`
- `POST /api/tickets` (manual) → `open` (human created, no review needed)

**New API endpoints:**
- `POST /api/tickets/{id}/approve` — sets status `draft → open`, optionally triggers auto-enrich+validate
- `POST /api/tickets/{id}/reject` — sets status `draft → rejected`
- `GET /api/tickets?status=draft` — filter endpoint (extend existing list query)

**UI changes:**

1. **Header badge** — a count indicator on the nav: `Drafts (4)` in accent color, links to the Review Queue
2. **Review Queue page** (`/review` or a tab on the main page)
   - Card grid layout (not a table) — each card shows: title, source repo, creation timestamp, a short excerpt of description
   - Three actions per card: **Approve** (green, sets to open), **Edit** (opens edit modal), **Reject** (red, soft-deletes)
   - Bulk action bar at top: "Approve All" and "Reject All" for power users
   - Empty state: "No drafts pending review"
3. **Main ticket table** — by default hides `draft` and `rejected` tickets; a toggle to show them
4. **Ticket detail page** — if the ticket is in draft, show a prominent banner: *"This ticket is a draft — Approve or Edit before starting work."* with inline Approve / Reject buttons

**Approval flow with auto-actions (optional):**

On approval, offer a checkbox: *"Auto-enrich and validate after approving."* If checked, the system runs `enrich → validate` (and heal if score low) in the background and updates the ticket. The ticket is immediately `open`; enrichment result arrives asynchronously and the page refreshes.

### Edge cases / open questions

- What happens if a draft is manually edited? It stays `draft` until explicitly approved. Editing is not approving.
- Should rejected tickets be permanently deletable? Yes — a "Delete rejected" bulk action can clean them up. But they're not auto-deleted, so the history is preserved.
- The existing stats bar (Total, Open, Validated, Pass rate) should exclude drafts and rejected tickets from its counts. Add a separate draft count display.

---

## Feature 3: Ticket Closure Verification

### Problem

After a developer marks a ticket `done`, there's no way to verify the work actually satisfies the acceptance criteria. This is purely a human judgement call today.

### Goal

The developer (or team lead) pastes a brief summary of what was done — a few sentences, commit messages, or a paste of the relevant diff. An agent checks it against the ticket's acceptance criteria and returns a breakdown: which criteria are covered, which are missing, and an overall coverage score.

**Deliberately simple:** no GitHub integration, no PR fetching. Just text input → structured verdict.

### Design

**New fields on `Ticket`:**
- `closure_summary: str = ""` — the text the user provided ("what was done")
- `closure_score: float | None = None` — 0.0–1.0 coverage score
- `closure_verified: bool | None = None` — True if score >= threshold (e.g. 0.8)
- `closure_notes: str = ""` — agent's free-text assessment
- `closure_criteria_status: list[dict] = []` — per-criterion result:
  ```
  [{"criterion": "...", "covered": true, "evidence": "..."}]
  ```

**New agent: `app/agents/closure_verifier.py`**

LangGraph graph:
```
load_ticket → verify_closure (LLM call) → save_closure_result → END
```

LLM call details:
- Input: ticket title, description, acceptance criteria list, user-provided `completion_text`
- If no acceptance criteria exist, fall back to evaluating against the description
- Output (structured): per-criterion covered/not, evidence snippet, overall score, notes
- If the ticket has no acceptance_criteria AND no description, return an error (nothing to verify against)

**New API endpoint:**
- `POST /api/agents/verify-closure/{ticket_id}` — body: `{completion_text: str}`
- Returns the updated ticket with closure fields populated

**UI changes (ticket detail page):**

A new "Closure Verification" card below the Validation card:
- **Input area:** text area labeled *"What was done — paste commit messages, a summary, or a diff excerpt"*
- **Verify button** — calls the API, shows spinner
- **Result display** (after verification):
  - Overall score as a progress bar (green/red like the validation bar)
  - Criteria table: each acceptance criterion with ✓ Covered / ✗ Missing and an evidence snippet
  - Agent's free-text notes
  - A "Re-verify" button to run again with updated text

**Closure-driven status change:**
- If `closure_verified` is true, the UI suggests (but does not force): *"All criteria covered — mark this ticket Done?"* with a one-click confirm button.

### Edge cases / open questions

- Tickets without acceptance criteria: the verifier falls back to checking the description. Warn the user: *"No acceptance criteria found — verifying against description only."*
- The `completion_text` is stored on the ticket. A second verification overwrites it. This is intentional — the last run's input is what matters.
- Closure verification is independent of validation. A ticket can be "validated" (well-defined) but not yet "closure-verified" (not yet done).

---

## Feature 4: Batch Import Inbox

### Problem

The current "Batch Create" takes just a list of titles — it's a mechanical operation, not intelligent. There's no way to paste a bunch of raw requirement text (e.g., copied from a meeting notes doc, Slack thread, or spec) and let the system turn it into proper tickets automatically.

### Goal

A simple **Inbox** where the user pastes unstructured requirement text. The system:
1. Intelligently splits it into individual requirements
2. For each requirement, generates a proper title + description using an LLM
3. Creates tickets (in `draft` status)
4. Optionally auto-validates each one

This is "AI-powered intake" — the front door for capturing work before it's been refined.

### Design

**Inbox input format — keep it flexible:**
The user can paste:
- One sentence per line: `Fix the login page\nAdd dark mode\n...`
- A numbered/bulleted list (LLM handles parsing)
- Full paragraphs: *"We need to improve the onboarding flow. Users are dropping off at step 3..."*
- Mixed (LLM splits intelligently)

The user can also optionally paste a **context block** (e.g., project name, sprint goal) that the LLM uses to disambiguate vague requirements.

**New API endpoint:**
- `POST /api/agents/inbox-import`
- Request body:
  ```
  {
    "raw_text": str,              # the pasted requirements blob
    "context": str = "",          # optional project context
    "repo_path": str | None,      # for enrichment (optional)
    "repo_url": str | None,       # for enrichment (optional)
    "auto_validate": bool = true  # validate each ticket after creation
  }
  ```
- Response: list of created draft tickets

**New agent: `app/agents/inbox_processor.py`**

LangGraph graph:
```
parse_requirements (LLM) → for each: create_ticket → [validate] → save → END
```

Step 1 — **Parse** (`parse_requirements` node):
- LLM receives `raw_text` + optional `context`
- Outputs a structured list: `[{title: str, description: str, priority: str}]`
- The LLM is instructed to: split, clean up titles to be imperative/actionable, write a one-paragraph description for each, and infer priority from language cues ("urgent", "critical", "nice to have")

Step 2 — **Create** (loop over parsed items):
- Creates each ticket with `status = "draft"`
- Sets `source_repo` if provided

Step 3 — **Validate** (if `auto_validate=True`):
- Runs the validator on each created ticket
- Heal loop is NOT triggered automatically here (would be too slow for large batches); user can heal individually from the Review Queue

**UI changes:**

1. **New "Inbox" button** in the main header (or a dedicated `/inbox` page)
2. **Inbox modal:**
   - Title: *"Import Requirements"*
   - Large text area: *"Paste requirements, meeting notes, or a feature list..."*
   - Optional text area: *"Project context (optional) — e.g., 'Mobile app sprint 4, user onboarding focus'"*
   - Repo source input (same as the main toolbar — optional, for enrichment later)
   - Toggle: *"Auto-validate after creating"* (default: on)
   - Submit button: *"Import & Create Drafts"*
3. **Progress indicator:**
   - After submit, show a list of parsed requirement titles with status icons: ⏳ Creating… → ✓ Created → ✓ Validated
   - If any fail, show ✗ with error message
4. **After completion:**
   - Toast: *"Imported N tickets — review them in the Draft Queue"*
   - Link directly to the Review Queue filtered to the just-created tickets

### Interaction with Feature 2 (Draft Flow)

Inbox import is the primary source of drafts. The full intended flow is:
```
Inbox Import → Draft Queue → [Edit?] → Approve → Enrich → Heal/Validate → In Progress → Done → Closure Verify
```

### Edge cases / open questions

- **Empty parse result:** if the LLM can't identify any discrete requirements (e.g., user pasted random text), return a 422 with message *"Could not extract any requirements from the provided text."*
- **Large inputs:** cap `raw_text` at 10,000 characters. Longer inputs should be broken into multiple inbox submissions.
- **Duplicate detection:** if a parsed title is semantically very similar to an existing ticket, flag it in the result (don't block creation, just warn). This is a light version of the backlog deduplication idea.
- **Rate limiting for large batches:** if > 20 requirements are parsed, warn the user that validation will take a while. Offer to skip auto-validate and do it later from the Review Queue.

---

## Backlog (not in current sprint)

| Feature | Reason for deferral |
|---|---|
| **RAG from past tickets** | Requires a vector store (infra overhead). Worth revisiting after the ticket corpus grows large enough to make retrieval meaningful. |
| **Jira / Linear integration** | Pure plumbing — doesn't improve AI quality. High effort, low learning. Add when there's a real integration request. |
| **Story point estimation** | No historical completion data yet to calibrate against. Revisit after 3+ months of usage data. |
| **Ticket deduplication (embeddings)** | Partially addressed in inbox import (light warning). Full embedding-based dedup needs a vector store — same blocker as RAG. |

---

## Revised Data Model (after all Sprint 2 features)

```python
class Ticket(BaseModel):
    # Core (unchanged)
    id: str
    title: str
    description: str
    status: Literal["draft", "open", "in_progress", "done", "rejected"]
    priority: str
    importance: str
    labels: list[str]
    source_repo: str
    business_req: str
    stakeholder: str
    user_story: str
    created_at: datetime
    updated_at: datetime

    # Enrichment (unchanged)
    acceptance_criteria: list[str]
    related_files: list[str]
    technical_notes: str
    suggested_assignee: str
    suggested_change_refs: list[dict]

    # Validation (unchanged)
    validation_score: float | None
    validation_passed: bool | None
    validation_notes: str

    # Feature 1: Heal loop (new)
    validation_iterations: int          # how many heal cycles have run

    # Feature 3: Closure verification (new)
    closure_summary: str                # user-provided "what was done" text
    closure_score: float | None         # 0.0–1.0 coverage
    closure_verified: bool | None       # True if score >= 0.8
    closure_notes: str                  # agent's free-text assessment
    closure_criteria_status: list[dict] # per-criterion {criterion, covered, evidence}
```

---

## Revised API Surface (after all Sprint 2 features)

| Method | Path | Description |
|---|---|---|
| GET | `/api/tickets` | List tickets (supports `?status=draft\|open\|...`) |
| GET | `/api/tickets/{id}` | Get one ticket |
| POST | `/api/tickets` | Create manually (status: open) |
| PUT | `/api/tickets/{id}` | Update ticket |
| DELETE | `/api/tickets/{id}` | Delete ticket |
| POST | `/api/tickets/{id}/approve` | Draft → Open |
| POST | `/api/tickets/{id}/reject` | Draft → Rejected |
| POST | `/api/agents/create-from-repo` | Generate tickets from repo (status: draft) |
| POST | `/api/agents/create-batch` | Batch create by title (status: draft) |
| POST | `/api/agents/enrich/{id}` | Enrich one ticket |
| POST | `/api/agents/enrich-batch` | Enrich selected tickets |
| POST | `/api/agents/validate/{id}` | Validate one ticket |
| **POST** | **`/api/agents/heal/{id}`** | **Self-healing loop (Feature 1)** |
| **POST** | **`/api/agents/verify-closure/{id}`** | **Closure verification (Feature 3)** |
| **POST** | **`/api/agents/inbox-import`** | **Batch import from raw text (Feature 4)** |
| GET | `/api/logs` | Agent run logs |
