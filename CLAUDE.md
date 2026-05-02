# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install all dependencies (including dev)
uv sync --extra dev

# Run the server (reads .env for OPENAI_API_KEY)
uv run uvicorn main:app --reload

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_storage.py -v

# Run a single test by name
uv run pytest tests/test_api.py::test_create_ticket -v
```

## Architecture

### Request flow

```
HTTP request
  → main.py (FastAPI app assembled via create_app(store))
  → app/api/tickets.py  (CRUD, /api/tickets)
  └→ app/api/agents.py  (agent triggers, /api/agents)
       → app/agents/creator.py   (LangGraph, 3 nodes)
       └→ app/agents/enricher.py (LangGraph, 4 nodes)
            → app/repo_tools.py  (local walk or PyGithub)
            → OpenAI via langchain-openai
            → app/storage.py     (in-memory + data/tickets.json)
```

### Storage

`TicketStore` (`app/storage.py`) is the single source of truth. It keeps an in-memory `dict[str, Ticket]` and writes the full list to `data/tickets.json` on every mutation. A module-level `get_store()` singleton is used by the live app; tests pass an isolated `TicketStore(data_dir=tmp_path)` instance directly.

### Router factory pattern

Both API routers use a factory function (`make_router(store)`) rather than a global dependency. This lets tests inject a fresh `TicketStore` without monkeypatching. `create_app(store)` in `main.py` wires everything together and is also used by the test client fixture.

### LangGraph agents

Each agent is a linear graph compiled inside its `_build_graph(store)` function and invoked synchronously via `run_creator` / `run_enricher`. The `store` is closed over in the save node via a lambda. The LLM functions (`_llm_generate_tickets`, `_llm_enrich_ticket`) are module-level so tests can patch them with `unittest.mock.patch`.

LLM responses are plain JSON strings (code fences stripped manually). The model is read from `OPENAI_MODEL` env var, defaulting to `gpt-4o`.

### Repo context

`read_repo(source)` in `app/repo_tools.py` auto-detects the source type:
- Starts with `http(s)://` → PyGithub (fetches top-level files + README + open issues)
- Otherwise → local filesystem walk

Local walk skips `_SKIP_DIRS`, reads only `_SOURCE_EXTS`, and caps output at 50 KB to stay within LLM context limits.

### Testing approach

TDD: every implementation file has a corresponding `tests/test_*.py`. Agent and API tests mock the LLM and agent calls respectively — no real OpenAI calls are made in tests. `tests/conftest.py` provides `sample_ticket`, `tmp_data_dir`, and `repo_context` fixtures used across test files.

## Environment variables

| Variable | Required | Default |
|---|---|---|
| `OPENAI_API_KEY` | Yes | — |
| `OPENAI_MODEL` | No | `gpt-4o` |
| `GITHUB_TOKEN` | No | — (public repos only) |

Copy `.env.example` to `.env` before running the server.
