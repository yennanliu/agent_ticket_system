# Agent Ticket System — Design Plan

## Overview

An AI-powered ticket management system that analyzes a software project and automatically generates and enriches task tickets. The demo project used for testing is `../linkedin-skill` (a local Node.js LinkedIn automation plugin).

---

## Goals

1. **Auto-create** task tickets by analyzing a repo (README, source files, skills, CI config)
2. **Auto-enrich** existing tickets with acceptance criteria, related files, and technical notes
3. **Full CRUD** — view, list, edit, create, delete tickets via a simple web UI
4. **No database or RAG** — in-memory storage persisted to a single JSON file
5. **Simple stack** — Python + uv + FastAPI + LangGraph + plain HTML/JS

---

## Project Structure

```
agent_ticket_system/
├── pyproject.toml          # uv-managed dependencies
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

Reads project context for the LLM agents. Supports two modes:

**Local path** (primary — used for `../linkedin-skill`):
- Walk directory tree (skip `node_modules`, `.git`, `output`)
- Read key files: `README.md`, `SKILL.md`, `CLAUDE.md`, `CHANGELOG.md`, any `.js`/`.py`/`.json` files under `skills/` and `scripts/`
- Cap total content at ~50 KB to stay within LLM context limits
- Return file tree summary + concatenated file contents

**GitHub URL** (secondary — requires `GITHUB_TOKEN`):
- Use `PyGithub` to fetch repo metadata, README, top-level files, and open issues

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
    "langchain-anthropic>=0.1",
    "pydantic>=2.7",
    "python-dotenv>=1.0",
    "pygithub>=2.3",
]
```

---

## Environment Variables

```bash
# .env (copy from .env.example)
ANTHROPIC_API_KEY=sk-ant-...          # required
GITHUB_TOKEN=ghp_...                  # optional, only for GitHub URL mode
```

---

## How to Run

```bash
# 1. Install deps
uv sync

# 2. Copy and fill in env file
cp .env.example .env
# edit .env — add ANTHROPIC_API_KEY

# 3. Start server
uv run uvicorn main:app --reload

# 4. Open browser
open http://localhost:8000
```

---

## Verification Steps

1. Server starts without errors on `http://localhost:8000`
2. `POST /api/agents/create-from-repo` with `{"repo_path": "../linkedin-skill"}` → returns 5–10 generated tickets
3. `GET /api/tickets` → lists all tickets with correct fields
4. `POST /api/agents/enrich/{id}` with `{"repo_path": "../linkedin-skill"}` → ticket now has `acceptance_criteria`, `technical_notes`, `related_files`
5. UI at `http://localhost:8000` renders the ticket table
6. Create, edit, and delete a ticket via the UI — changes persist after page reload
