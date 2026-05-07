# RAG Ideas for Improving LLM Performance

## Current LLM Context Quality: The Core Problem

Every agent invocation dumps the **same 50KB brute-force slice** of the repo into the prompt, regardless of what's relevant:

- `creator.py`: `README[:3000]` + `file_contents[:5000]` — fixed, arbitrary window
- `enricher.py`: `README[:2000]` + `file_contents[:4000]` — same dump, not ticket-aware
- `repo_tools.py`: walks up to `_MAX_BYTES = 50_000` and then hard-stops, so for large repos you get the first 50KB alphabetically
- `find_refs` in `search_tools.py`: for **local repos**, falls back to DuckDuckGo web search as a proxy for semantic search — a known hack that often returns irrelevant results

RAG directly addresses all four.

---

## RAG Approaches

### Option A — Semantic chunk retrieval for enricher (targeted, high ROI)

**What**: Embed all repo files in chunks (~300–500 tokens). When the enricher runs for a specific ticket, retrieve the top-k most semantically relevant chunks using the ticket title + description as the query, instead of dumping 4KB of arbitrary file contents.

**Stack**: OpenAI `text-embedding-3-small` + in-memory cosine similarity (no new deps — `openai` is already in the project)

**Effort**: Medium (3–5 days)
- New `app/indexer.py` to chunk, embed, cache, and retrieve
- Patch `enricher._node_fetch_context` to call indexer instead of brute-forcing `read_repo`

**Pros**:
- Direct fix for the enricher's most critical weakness — it currently doesn't know which files matter for a given ticket
- `technical_notes`, `related_files`, and `acceptance_criteria` quality improves significantly
- Scales to large repos (current 50KB cap silently truncates big codebases)

**Cons**:
- Adds embedding latency (~1–3s per enrichment call for retrieval, plus upfront indexing time)
- Index can go stale if repo files change between indexing and enrichment

---

#### Implementation Design: Async with graceful fallback

Indexing a repo takes 5–30s (embedding API calls). Three approaches were considered:

| # | Approach | Verdict |
|---|---|---|
| 1 | Sync with persistent cache — index once, block first call | First call blocks HTTP response; bad UX for an API |
| 2 | **Background indexing with fallback** — async thread, brute-force until ready | **Chosen — zero disruption, quality improves silently** |
| 3 | Separate service (Celery/worker) — dedicated indexer process | Overkill; adds ops complexity for no benefit at this scale |

**Chosen design (Option 2):**

```
Enrichment call
  ├─ index READY?  → semantic chunks → LLM          ✓ quality path
  └─ index NOT YET? → submit background job
                    → brute-force read_repo → LLM   ✓ fallback path
```

**Key properties:**
- `RAG_ENABLED=false` (default) — zero behaviour change; opt-in via env var
- `IndexService` runs a `ThreadPoolExecutor`; `submit()` is fire-and-forget
- Cache keyed by `abs_path + mtime fingerprint` — auto-invalidates on file changes
- No new dependencies — pure-Python cosine similarity over OpenAI embeddings
- Eager trigger: index is also submitted when enrichment first misses, warming it for the next call

---

### Option B — Replace `find_refs` local search with vector similarity (small, well-scoped)

**What**: `find_refs` currently calls DuckDuckGo for local repos (`ref_type == "code"`), which returns web results unrelated to the local codebase. Replace this with a local vector similarity search: given a file path and repo name, retrieve the most semantically related local files and their actual snippets.

**Stack**: FAISS (lightweight, no server) or reuse the index from Option A

**Effort**: Low–Medium (1–2 days)
- Narrow change: only touches `search_tools.py:find_refs`
- If Option A's index exists, this is nearly free

**Pros**:
- Fixes a concrete quality bug (DuckDuckGo returning random web docs for local repos)
- `suggested_change_refs` becomes actually useful for local dev workflows
- Low risk, isolated change

**Cons**:
- Doesn't improve the main LLM generation quality
- Requires at least a basic embedding index to be built first

---

### Option C — Persistent repo index with change detection (performance + quality)

**What**: The same repo gets fully re-read and re-embedded on **every single** creator + enricher invocation. Cache the vector index keyed by repo path + file mtimes. Only re-index changed files (incremental).

**Stack**: ChromaDB (supports upsert/delete per document), file mtime tracking

**Effort**: Medium–High (4–7 days)
- New `app/repo_cache.py` managing mtime fingerprinting
- ChromaDB collection per repo path
- Invalidation logic when files change

**Pros**:
- Dramatically reduces latency on repeated enrichment (warm cache = no embedding cost)
- Enables many tickets to share one index build
- Opens the door to "background indexing" on repo add

**Cons**:
- Most complex option independently; best done as a layer on top of Option A
- Stale index edge cases need careful handling (file deletes, renames)
- Adds operational overhead (ChromaDB persistence, disk usage)

---

### Option D — Ticket similarity search / deduplication

**What**: Embed ticket `title + description` as they're created. Before saving new tickets, retrieve the top-k most similar existing tickets. Surface them in the API response or use them to avoid generating duplicates.

**Stack**: SQLite `sqlite-vec` extension or ChromaDB (separate collection for tickets)

**Effort**: Low–Medium (2–3 days)
- Only needs to embed tickets, not code files — much smaller corpus
- Existing `TicketStore` CRUD is the only integration point
- `sqlite-vec` would keep it all in-process with no new server

**Pros**:
- Valuable feature: "find similar tickets" and deduplication are common pain points
- Small, self-contained corpus (tickets, not entire codebases)
- No latency concern — embedding ~100-char titles is fast
- Doesn't depend on Options A–C at all

**Cons**:
- Doesn't improve generation quality (the core LLM problem)
- Only pays off once there are enough tickets (~50+) to make similarity meaningful

---

### Option E — Full RAG pipeline replacing `read_repo` for creator (highest impact, highest effort)

**What**: Replace the `read_repo` brute-force dump in `creator.py` with a two-phase approach: (1) generate a candidate list of ticket topics from README + file tree only (small, cheap), (2) for each candidate ticket topic, retrieve relevant code chunks to ground the full ticket generation.

**Stack**: ChromaDB + OpenAI embeddings

**Effort**: High (7–10 days)
- Requires multi-step creator graph (topic extraction → retrieval → generation)
- Significantly changes the LangGraph flow in `creator.py`
- Needs index to exist before creator runs

**Pros**:
- Scales to repos of any size (currently breaks on repos > 50KB)
- Tickets are grounded in actual relevant code, not a random early slice
- Best overall quality improvement

**Cons**:
- Most complex and risky change
- Creator currently works acceptably for small/medium repos — biggest benefit is for large repos
- Multi-step graph is harder to test and debug
- Requires the index to always be fresh before creation can run

---

## Summary Comparison

| Option | Effort | Quality Impact | Risk | Best For |
|---|---|---|---|---|
| A — Enricher retrieval | Medium | High | Medium | Better acceptance criteria / technical notes |
| B — Fix `find_refs` | Low | Low–Medium | Low | Fixing a concrete quality bug, quick win |
| C — Persistent index | Med–High | Medium (perf) | Medium | Large repos, repeated runs |
| D — Ticket similarity | Low–Medium | Medium (UX) | Low | Deduplication, semantic search feature |
| E — Creator RAG | High | High | High | Very large repos, best generation quality |

**Recommended order**: B → A → D → C → E. B is a near-zero risk fix. A gives the highest quality improvement per effort unit. D adds user-facing value independently. C and E are worthwhile only once the simpler options prove the pattern works.
