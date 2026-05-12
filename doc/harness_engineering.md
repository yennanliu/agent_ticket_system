# Harness Engineering — Integration Plan

**What is "harness engineering" here?**  
Making this project a first-class citizen inside Claude Code's agent harness: hooks that react to local events, an MCP server so Claude can call ticket APIs as native tools, scheduled autonomous routines, and a Claude API migration so the agents use Claude models instead of GPT-4o.

---

## 1. MCP Server — Expose Ticket APIs as Claude Tools

### What
Wrap the FastAPI endpoints as an MCP (Model Context Protocol) server so any running Claude Code session can create, query, update, and trigger agents on tickets directly — no manual `curl` or UI needed.

### Why
Right now Claude Code has zero awareness of this system at runtime. With an MCP server, Claude can say "create a ticket for X" or "run the healer on ticket Y" as a native tool call. This turns the ticket system from a standalone web app into a first-class tool in every agentic workflow.

### What to implement

**New file: `mcp_server.py`** (FastMCP or the `mcp` Python SDK)

Expose these as tools:
| Tool name | Maps to |
|---|---|
| `list_tickets` | `GET /api/tickets` |
| `get_ticket` | `GET /api/tickets/{id}` |
| `create_ticket` | `POST /api/tickets` |
| `update_ticket` | `PUT /api/tickets/{id}` |
| `delete_ticket` | `DELETE /api/tickets/{id}` |
| `create_from_repo` | `POST /api/agents/create-from-repo` |
| `enrich_ticket` | `POST /api/agents/enrich/{id}` |
| `validate_ticket` | `POST /api/agents/validate/{id}` |
| `heal_ticket` | `POST /api/agents/heal/{id}` |
| `kickstart_ticket` | `POST /api/agents/kickstart/{id}` |
| `split_ticket` | `POST /api/agents/split/{id}` |
| `get_rag_status` | `GET /api/rag/status` |

**Register in `.claude/settings.json`:**
```json
{
  "mcpServers": {
    "ticket-system": {
      "command": "uv",
      "args": ["run", "python", "mcp_server.py"],
      "env": { "OPENAI_API_KEY": "${OPENAI_API_KEY}" }
    }
  }
}
```

### Effort: **Medium** (2–3 days)
- ~200 lines of MCP wrapper code
- Needs `mcp` or `fastmcp` dependency added to `pyproject.toml`
- Tests: one smoke test per tool verifying correct HTTP call is made

### Comments
The server can either call the FastAPI HTTP endpoints (simple, but requires the server to be running) or import and call the storage/agent functions directly (no HTTP round-trip, works standalone). Prefer the direct-import approach so the MCP server works without `uvicorn` running.

---

## 2. Hooks — React to Local Dev Events

### What
Claude Code hooks are shell commands that execute automatically on harness events (tool calls, session start/stop, etc.). Wire this project's agents to those events so tickets get created or updated in response to real engineering activity.

### Why
Today tickets are manually requested. Hooks make ticket creation ambient: a failing test automatically surfaces a ticket, a commit triggers enrichment, session end logs a summary ticket. Zero user friction.

### What to implement

**`.claude/settings.json` hook entries:**

#### 2a. Post-bash hook — auto-create ticket on test failure
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "uv run python scripts/hooks/on_test_failure.py"
      }]
    }]
  }
}
```

**`scripts/hooks/on_test_failure.py`:**  
Reads stdin (Claude Code passes tool result JSON). If the bash command was `pytest` and exit code != 0, POST to `/api/tickets` with a `bug` label and the failure output as description. Idempotent — check if a ticket with the same test name already exists first.

#### 2b. Post-bash hook — auto-enrich on git commit
Trigger enrichment on the most recently modified tickets when `git commit` is detected. Enricher already knows the repo path from `source_repo`.

#### 2c. Stop hook — session summary ticket
```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "uv run python scripts/hooks/on_session_stop.py"
      }]
    }]
  }
}
```

Creates or updates a "session log" ticket summarising what was worked on. Uses the conversation transcript path that Claude Code passes in env.

#### 2d. Pre-bash hook — block work on unvalidated tickets
Optional: before running a bash command on files listed in a ticket's `related_files`, warn if that ticket's `validation_passed` is `False` or `None`. Informational only — does not block.

### Effort: **Low–Medium** (1–2 days total)
- Hook registration: 30 min (config only)
- `on_test_failure.py`: ~80 lines, 1 day including edge cases
- `on_session_stop.py`: ~60 lines, half a day
- Git commit hook: ~50 lines, half a day

### Comments
Hook scripts must be fast (<1 s startup). Import only what you need; avoid loading LangGraph/LangChain in hooks. Use direct `httpx` calls to the running FastAPI server rather than importing agent code. If the server isn't running, the hook should exit silently (graceful degradation — existing CLAUDE.md principle).

---

## 3. Scheduled Autonomous Routines

### What
Use Claude Code's `CronCreate` to schedule periodic runs of the healer, enricher, and validator so the backlog self-improves without manual intervention.

### Why
The heal loop and kickstart agent already exist — they just never run unless a human presses a button. Scheduling them makes the system genuinely autonomous: overnight, stale or low-scoring tickets get re-enriched and healed automatically.

### What to implement

Three routines, each as a Claude Code scheduled agent:

#### 3a. Nightly Healer
**Schedule:** `0 2 * * *` (2 AM daily)  
**Prompt:** "Call `POST /api/agents/heal/{id}` for every ticket where `validation_passed` is false or `validation_score < 0.75`. Log results."

Implemented as a small script `scripts/routines/nightly_heal.py` that the scheduled agent invokes via bash, or the agent uses the MCP `heal_ticket` tool directly.

#### 3b. Hourly Enrichment Queue
**Schedule:** `0 * * * *` (every hour)  
**Prompt:** "Find all tickets with `status=draft` and empty `acceptance_criteria`. Run enrich on each."

#### 3c. Weekly Validation Sweep
**Schedule:** `0 9 * * 1` (Monday 9 AM)  
**Prompt:** "Validate all `open` and `in_progress` tickets that haven't been validated in the past 7 days (check `updated_at`). Print a summary report."

### Effort: **Low** (half a day)
- Scheduling itself is just `CronCreate` calls
- Scripts are thin wrappers (~40 lines each) calling the existing API
- No new agent logic — reuse existing endpoints

### Comments
Scripts should be idempotent and add no state. If the FastAPI server isn't running, they should start a temporary in-process store and run the agents directly via `run_healer` / `run_enricher` imports. Env vars (`OPENAI_API_KEY`) must be set in the cron environment — document in CLAUDE.md.

---

## 4. Claude API Migration — Replace OpenAI/LangChain

### What
Replace `langchain-openai` + GPT-4o in all five agents (creator, enricher, validator, healer, splitter) with the Anthropic SDK calling `claude-sonnet-4-6` directly.

### Why
- **Native to the harness**: Claude Code is Claude — using the same model family reduces context-switching and improves prompt coherence
- **Prompt caching**: Anthropic SDK supports cache breakpoints; the repo context (which can be 50 KB) is a perfect cache candidate — reduces latency and cost on repeated enrichments
- **No LangChain dependency**: removes 15+ transitive packages, simplifies the dependency tree
- **Tool use**: Claude's native tool-use is cleaner than LangChain's wrapper for structured output

### What to implement

**Remove:** `langchain-openai`, `langchain-core` from `pyproject.toml`  
**Add:** `anthropic>=0.40`

**Pattern change in each agent** (same structure, different call):

Before (LangChain):
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
response = llm.invoke(prompt)
content = response.content
```

After (Anthropic SDK with prompt caching):
```python
import anthropic
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": repo_context_block, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": task_prompt},
        ]
    }],
)
content = response.content[0].text
```

**Cache strategy:**
- `repo_context` block → `cache_control: ephemeral` (5-min TTL, reused across multiple enrichments of the same repo)
- System prompt (static) → also cached
- Per-ticket fields (title, description) → NOT cached (changes per request)

**Env var changes:**
| Old | New |
|---|---|
| `OPENAI_API_KEY` | `ANTHROPIC_API_KEY` |
| `OPENAI_MODEL` | `ANTHROPIC_MODEL` (default: `claude-sonnet-4-6`) |

Keep `OPENAI_API_KEY` + `EMBEDDING_MODEL` for the RAG indexer (embeddings still use OpenAI `text-embedding-3-small` — no Claude equivalent yet).

**LangGraph stays:** LangGraph is model-agnostic; keep the graph structure, just swap the LLM call inside each `_llm_*` function.

### Effort: **Medium** (2–3 days)
- 5 agent files × ~20 lines changed each
- Update all tests: mock `anthropic.Anthropic().messages.create` instead of `ChatOpenAI.invoke`
- Update `.env.example`, CLAUDE.md env var table
- Validate JSON parsing still works (Claude returns cleaner JSON, but code-fence stripping stays)

### Comments
Do not remove OpenAI entirely yet — the RAG indexer (`app/indexer.py`) still needs `openai` for embeddings. Can revisit when Anthropic releases an embedding model. Use `ANTHROPIC_API_KEY` env var; the SDK reads it automatically. Enable `prompt_caching` at the client level for automatic savings.

---

## 5. CLAUDE.md — Harness-Aware Documentation

### What
Extend `CLAUDE.md` to document the harness integration: MCP tools available, hook behavior, scheduled routines, and how Claude should interact with the ticket system during a session.

### Why
CLAUDE.md is loaded into every session. Without it, Claude has no awareness of the MCP server, hook scripts, or scheduled routines — it will miss opportunities to use them.

### What to add

**New section: "MCP Tools"** — list all available tools with one-line descriptions.

**New section: "Hooks"** — what each hook does, what events it fires on, where scripts live.

**New section: "Scheduled Routines"** — names, schedules, what they do.

**New section: "Working with Tickets During a Session"** — recommended workflow:
1. At session start, call `list_tickets` to see open work
2. If writing code that relates to an existing ticket, call `get_ticket` for context
3. If a test fails, check if `on_test_failure` hook already created a ticket before manually creating one
4. Call `kickstart_ticket` on newly created manual tickets that have a `source_repo`

**New guidance:** Tell Claude when NOT to use the ticket system (e.g., trivial one-line fixes don't need a ticket).

### Effort: **Low** (2–4 hours)
- Documentation only; no code changes
- Should be written after items 1–4 are implemented

---

## 6. Permissions Configuration

### What
Add an allowlist in `.claude/settings.json` so harness tool calls don't trigger permission prompts for routine read-only and local operations.

### Why
Every unapproved tool call interrupts agentic flow. Hook scripts, scheduled routines, and MCP calls should run silently for safe operations.

### What to add

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run pytest*)",
      "Bash(uv run python scripts/hooks/*)",
      "Bash(uv run python scripts/routines/*)",
      "Bash(git status)",
      "Bash(git log*)",
      "Bash(git diff*)",
      "Read(/Users/jliu/agent_ticket_system/**)"
    ]
  }
}
```

Anything that writes tickets or calls agents keeps the default "ask" behavior to prevent unintended LLM spend.

### Effort: **Very Low** (30 min)

---

## Summary Table

| Item | What | Why | Effort | Priority |
|---|---|---|---|---|
| 1. MCP Server | Expose ticket API as Claude tools | Native tool use in every session | Medium (2–3 days) | **High** |
| 2. Hooks | React to test failures, commits, session end | Ambient ticket creation, zero friction | Low–Medium (1–2 days) | **High** |
| 3. Scheduled Routines | Nightly healer, hourly enrichment, weekly sweep | Autonomous backlog improvement | Low (0.5 days) | Medium |
| 4. Claude API Migration | Replace OpenAI/LangChain with Anthropic SDK | Cache savings, harness alignment, fewer deps | Medium (2–3 days) | Medium |
| 5. CLAUDE.md Updates | Document harness integration | Session-level awareness | Very Low (2–4 hrs) | Low (do last) |
| 6. Permissions Config | Allowlist routine bash + read ops | Uninterrupted agentic flow | Very Low (30 min) | Low |

**Recommended order:** 6 → 2 → 1 → 3 → 4 → 5  
Start with permissions (unblocks everything), then hooks (highest day-to-day value), then MCP (foundational for autonomous routines), then scheduling, then the API migration (most invasive), then doc.
