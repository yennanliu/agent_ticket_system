# Harness Engineering — What to Build Inside the Ticket System

**Scope:** Infrastructure improvements to the ticket system itself — making it reliable, observable, and production-grade as a platform. Nothing to do with Claude Code runtime.

---

## 1. Async Agent Execution + Task Queue

### Problem
Every agent endpoint (`/api/agents/create-from-repo`, `/api/agents/heal/{id}`, etc.) runs synchronously inside the HTTP request. A creator or healer run takes 10–30 seconds. The HTTP client blocks, timeouts are likely on slow repos, and there is no way to track progress or cancel a run.

### What to implement
Replace the synchronous `run_*(...)` call in each endpoint with a fire-and-forget background task. Return a `task_id` immediately. Add a polling endpoint to check status and fetch the result.

**Option A — FastAPI `BackgroundTasks` (no new deps):**
- Sufficient for single-process deployments
- No persistence: task state lost on restart
- Good enough for the current SQLite + single-worker setup

**Option B — ARQ (async Redis queue):**
- Tasks survive restarts, can be retried, have explicit states
- Requires Redis
- Right choice if you expect concurrent users or multi-worker deployments

**New data model:**
```python
class AgentTask(BaseModel):
    task_id: str        # UUID
    agent: str          # "creator" | "enricher" | ...
    status: str         # "queued" | "running" | "done" | "error"
    ticket_ids: list[str]
    created_at: datetime
    finished_at: datetime | None
    error: str
```

**New endpoints:**
```
POST /api/agents/create-from-repo  →  { task_id: "..." }   (201, returns immediately)
GET  /api/agents/tasks/{task_id}   →  AgentTask + result
GET  /api/agents/tasks             →  list of recent tasks
DELETE /api/agents/tasks/{task_id} →  cancel if queued/running
```

**Effort:** Medium (2–3 days for Option A; 4–5 days for Option B with Redis)  
**Why:** Without this, the system is not usable under any real load. A 30-second blocking HTTP call is unusable in a UI.  
**Start with Option A** — migrate to B only when you need multi-worker or persistence across restarts.

---

## 2. Structured Observability (Metrics + Tracing)

### Problem
The current `AgentLogger` writes JSONL to a file. This is fine for viewing logs in the UI, but there is no way to aggregate durations, compare runs, alert on error rates, or trace a request across multiple agent calls.

### What to implement

#### 2a. Prometheus metrics endpoint
Add `prometheus-fastapi-instrumentator` (1 line of setup). Exposes `GET /metrics` with:
- `agent_runs_total{agent, status}` — counter
- `agent_duration_seconds{agent}` — histogram
- `tickets_total{status}` — gauge (recomputed from DB)
- `validation_score_histogram{agent}` — score distribution

**Effort:** Very Low (half a day, 1 dep, ~20 lines)

#### 2b. Structured logging with correlation IDs
Each agent run gets a `run_id` (already partially done via task_id from item 1). Pass it through every log call. The JSONL logger already exists — extend it to include `run_id` and `parent_run_id` (for healer's nested calls to enricher+validator).

**Effort:** Low (1 day — touch 5 agent files + logger)

#### 2c. OpenTelemetry tracing (optional, higher effort)
Add `opentelemetry-instrumentation-fastapi`. Each agent graph node becomes a span. Useful for seeing where time is spent (fetch_context vs. LLM call vs. save). Export to Jaeger or OTLP.

**Effort:** Medium (2 days)  
**Comment:** Skip for now unless you're debugging performance. Metrics (2a) and correlation IDs (2b) give 80% of the value at 10% of the cost.

---

## 3. Retry + Error Recovery Infrastructure

### Problem
LLM calls fail. GitHub rate-limits. The OpenAI API returns 429s. Right now a single failure aborts the entire agent run and returns a 500 to the caller. There is no retry, no partial recovery, and no distinction between transient and permanent errors.

### What to implement

#### 3a. LLM call retry with exponential backoff
Wrap every `llm.invoke(...)` call in a shared utility:

```python
# app/llm_utils.py
import time

def invoke_with_retry(llm, prompt, max_attempts=3, base_delay=2.0):
    for attempt in range(max_attempts):
        try:
            return llm.invoke(prompt)
        except RateLimitError:
            if attempt == max_attempts - 1:
                raise
            time.sleep(base_delay * (2 ** attempt))
        except (APIConnectionError, APITimeoutError):
            if attempt == max_attempts - 1:
                raise
            time.sleep(base_delay)
```

**Effort:** Low (half a day — one new file, 5 call sites to update)

#### 3b. JSON parse retry
The LLM sometimes returns malformed JSON. Currently this crashes the node. Add a second attempt with an explicit "fix your JSON" prompt:

```python
def parse_json_with_retry(llm, prompt, raw_response):
    try:
        return json.loads(strip_fences(raw_response))
    except json.JSONDecodeError as e:
        fix_prompt = f"Your response was not valid JSON: {e}. Original: {raw_response}\nReturn ONLY valid JSON."
        raw2 = llm.invoke(fix_prompt).content.strip()
        return json.loads(strip_fences(raw2))
```

**Effort:** Very Low (a few hours)

#### 3c. Dead-letter storage for failed tasks
When an agent run fails permanently (all retries exhausted), write the failure to a `failed_tasks` table in SQLite with the full input and error. Expose `GET /api/agents/failed` so you can inspect and replay them.

**Effort:** Low (1 day)

---

## 4. Database Migrations

### Problem
`storage.py` runs `CREATE TABLE IF NOT EXISTS` at startup. Any schema change (new column, renamed field) requires manual SQLite migration or dropping and recreating the table — losing all data. This is already a maintenance problem (the current schema has 23 columns added iteratively with no migration trail).

### What to implement
Add **Alembic** for schema migrations.

```
uv add alembic
alembic init alembic/
```

**Initial migration:** captures the current 23-column schema as `001_initial.py`.  
**Future workflow:** every `Ticket` model field addition generates a migration:
```bash
alembic revision --autogenerate -m "add closure_score"
alembic upgrade head
```

Wire `alembic upgrade head` into the app startup in `main.py` (or a `make migrate` script).

**Effort:** Low (1 day to set up; near-zero per future migration)  
**Why:** Without this, the first schema change in production destroys the ticket history.

---

## 5. Authentication + Authorization

### Problem
Every endpoint is fully open. Anyone who can reach the server can delete all tickets, trigger expensive agent runs, or read all ticket data.

### What to implement
A minimal API key auth layer — not OAuth, not JWT, just a shared secret. This is appropriate for a single-team internal tool.

**New env var:** `API_KEY` (required in production, optional in dev)

**FastAPI dependency:**
```python
# app/auth.py
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def require_api_key(key: str = Security(_header)):
    expected = os.getenv("API_KEY")
    if expected and key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")
```

Apply selectively:
- **Agent endpoints** (`/api/agents/*`): always require key (expensive operations)
- **Write endpoints** (`POST`, `PUT`, `DELETE` on `/api/tickets`): require key
- **Read endpoints** (`GET /api/tickets`): optional (can be open for dashboards)
- **UI pages** (`/`, `/tickets`, etc.): open (browser-facing)

**Effort:** Low (1 day — new file + dependency injection on ~10 endpoints)

---

## 6. Input Validation + Rate Limiting

### Problem
Agent endpoints accept arbitrary `repo_path` values, including paths like `../../../../etc/passwd`. There is no rate limiting — a single caller can trigger 100 concurrent creator runs, each costing real OpenAI tokens.

### What to implement

#### 6a. Path traversal guard
```python
# app/validators.py
def validate_repo_path(path: str) -> str:
    abs_path = os.path.realpath(path)
    # Optionally enforce an allowlist of base dirs
    if not os.path.isdir(abs_path):
        raise ValueError(f"Not a directory: {path}")
    return abs_path
```

Called at the top of every endpoint that accepts `repo_path`.

**Effort:** Very Low (a few hours)

#### 6b. Per-IP rate limiting on agent endpoints
Add `slowapi` (thin wrapper around `limits`):

```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@r.post("/create-from-repo")
@limiter.limit("5/minute")
def create_from_repo(request: Request, body: RepoSource):
    ...
```

**Effort:** Very Low (half a day, 1 dep)

---

## 7. Webhook / Event Emission

### Problem
The ticket system is an island. When a ticket is created, enriched, or healed, nothing else knows. External tools (CI systems, Slack bots, other services) have no way to react to ticket state changes.

### What to implement
An outbound webhook system. On key events, POST a JSON payload to a configured URL.

**New env vars:**
```
WEBHOOK_URL=https://...        # POST target
WEBHOOK_SECRET=...             # HMAC-SHA256 signing key
WEBHOOK_EVENTS=created,healed  # comma-separated allowlist
```

**Events to emit:**
- `ticket.created` — after creator or manual POST
- `ticket.enriched` — after enricher saves
- `ticket.validated` — after validator, includes score
- `ticket.healed` — after healer finishes, includes final score + iteration count
- `ticket.status_changed` — approve, reject, manual status update

**Implementation:**
```python
# app/events.py
def emit(event: str, ticket: Ticket) -> None:
    url = os.getenv("WEBHOOK_URL")
    if not url or event not in _enabled_events():
        return
    payload = {"event": event, "ticket": ticket.model_dump(mode="json")}
    # fire-and-forget in a thread; never blocks agent execution
    threading.Thread(target=_post, args=(url, payload), daemon=True).start()
```

Called from each agent's save node. Silent on failure (existing graceful degradation principle).

**Effort:** Low–Medium (1–2 days including HMAC signing and tests)

---

## 8. Health + Readiness Endpoints

### Problem
There is no health check. A load balancer or container orchestrator (Docker, k8s) cannot determine if the app is up, if the DB is reachable, or if the LLM API key is valid.

### What to implement

```
GET /health        →  { status: "ok" }                         (always 200, liveness only)
GET /ready         →  { status: "ok", db: "ok", llm: "ok" }    (checks dependencies, 503 if any fail)
```

`/ready` checks:
- SQLite: can execute `SELECT 1`
- LLM key: `OPENAI_API_KEY` is set (don't make an actual call — too slow)
- RAG indexer: reports in-progress count if `RAG_ENABLED`

**Effort:** Very Low (2–3 hours)

---

## Summary Table

| # | Item | Why | Effort | Priority |
|---|---|---|---|---|
| 1 | Async execution + task queue | Blocking HTTP on 30s LLM call is unusable | Medium (2–3 days) | **Critical** |
| 2a | Prometheus metrics | Visibility into agent performance and error rates | Very Low (0.5 days) | **High** |
| 2b | Correlation IDs in logs | Trace a ticket across nested agent calls | Low (1 day) | **High** |
| 3a | LLM retry with backoff | Transient 429s and timeouts crash runs today | Low (0.5 days) | **High** |
| 3b | JSON parse retry | Malformed LLM output crashes the node today | Very Low (0.5 days) | **High** |
| 4 | Alembic migrations | Any schema change destroys production data today | Low (1 day) | **High** |
| 5 | API key auth | Agent endpoints are completely open | Low (1 day) | Medium |
| 6a | Path traversal guard | `repo_path` is unsanitized user input | Very Low (0.5 days) | Medium |
| 6b | Rate limiting | Unlimited concurrent agent runs = unbounded cost | Very Low (0.5 days) | Medium |
| 7 | Webhook / event emission | Ticket state changes are invisible to external systems | Low–Medium (1–2 days) | Low |
| 2c | OpenTelemetry tracing | Deep span-level profiling | Medium (2 days) | Low (defer) |
| 3c | Dead-letter storage | Replay failed tasks | Low (1 day) | Low |
| 8 | Health + readiness endpoints | Required for any container deployment | Very Low (2 hrs) | Low |

**Recommended order:** 3b → 3a → 4 → 1 → 2a+2b → 8 → 6a+6b → 5 → 7  
Fix correctness first (retry, migrations), then unblock real usage (async), then add visibility (metrics, logs), then harden (auth, rate limiting, webhooks).
