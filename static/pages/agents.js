/* pages/agents.js — agent catalog with Mermaid flowcharts + code viewer */

mermaid.initialize({ startOnLoad: false, theme: 'dark', themeVariables: { fontSize: '12px' } });

const AGENTS = [
  {
    name: "Creator",
    icon: "⬡",
    file: "app/agents/creator.py",
    mission: "Analyses a repository and generates 5–10 actionable draft tickets in one pass. Reads the full repo context, prompts the LLM, then saves each ticket and kicks off validation.",
    graph: ["fetch_context", "generate_tickets", "save_tickets"],
    trigger: "POST /api/agents/create-from-repo",
    tools: ["read_repo", "ChatOpenAI", "TicketStore"],
    mermaid: `graph LR\n  A([fetch_context]) --> B([generate_tickets]) --> C([save_tickets])`,
  },
  {
    name: "Enricher",
    icon: "◈",
    file: "app/agents/enricher.py",
    mission: "Adds acceptance criteria, related files, technical notes, suggested assignee, and change refs to a ticket. With RAG enabled, retrieves semantically relevant code chunks; falls back to brute-force read_repo.",
    graph: ["fetch_ticket", "fetch_context", "enrich", "find_refs", "save_ticket"],
    trigger: "POST /api/agents/enrich/:id",
    tools: ["read_repo", "IndexService", "find_refs", "ChatOpenAI", "TicketStore"],
    mermaid: `graph LR\n  A([fetch_ticket]) --> B([fetch_context])\n  B -->|RAG ready| C([enrich])\n  B -->|fallback| C\n  C --> D([find_refs]) --> E([save_ticket])`,
  },
  {
    name: "Validator",
    icon: "✦",
    file: "app/agents/validator.py",
    mission: "Scores a ticket 0–1 across four quality dimensions — testable criteria, plausible files, actionable notes, change refs — and marks it passed if score ≥ 0.6.",
    graph: ["fetch_ticket", "validate", "save_ticket"],
    trigger: "POST /api/agents/validate/:id",
    tools: ["ChatOpenAI", "TicketStore"],
    mermaid: `graph LR\n  A([fetch_ticket]) --> B([validate]) --> C([save_ticket])`,
  },
  {
    name: "Healer",
    icon: "↺",
    file: "app/agents/healer.py",
    mission: "Re-enriches and re-validates a ticket in a feedback loop until score ≥ 0.75 or max 3 iterations. Passes validation notes as feedback to the Enricher each cycle.",
    graph: ["validate", "→ enrich (w/ feedback)", "→ validate", "loop ×3"],
    trigger: "POST /api/agents/heal/:id",
    tools: ["Enricher", "Validator"],
    mermaid: `graph TD\n  A([validate]) -->|score >= 0.75| Z([done])\n  A -->|score < 0.75| B([enrich w/ feedback])\n  B --> C([validate])\n  C -->|pass or 3x| Z\n  C -->|fail| B`,
  },
  {
    name: "Kickstart",
    icon: "⚡",
    file: "app/agents/kickstart.py",
    mission: "Full pipeline for newly created tickets. Enriches if a repo is available, validates, then retries up to 3× until score ≥ 0.60. Called automatically after ticket creation.",
    graph: ["enrich?", "validate", "retry loop ×3", "∎"],
    trigger: "POST /api/agents/kickstart/:id",
    tools: ["Enricher", "Validator"],
    mermaid: `graph TD\n  A([enrich?]) --> B([validate])\n  B -->|pass| Z([done])\n  B -->|fail| C([retry])\n  C --> B\n  C -->|3x| Z`,
  },
];

const TOOLS = [
  {
    name: "read_repo",
    file: "app/repo_tools.py",
    desc: "Auto-detects local path vs GitHub URL. Walks the file tree, reads source files up to 50 KB, and extracts the README for LLM context. Skips node_modules, .venv, dist, build, and similar noise directories.",
    used_by: ["Creator", "Enricher"],
  },
  {
    name: "IndexService",
    file: "app/indexer.py",
    desc: "Background RAG indexer. Embeds repo files in ~400-token chunks and caches by path + mtime fingerprint. Enricher calls retrieve() for top-k semantically relevant chunks; falls back to read_repo when index is not ready.",
    used_by: ["Enricher"],
  },
  {
    name: "find_refs",
    file: "app/search_tools.py",
    desc: "Resolves related_files to actual paths via exact match then Jaccard-similarity fallback over the local file tree. Constructs GitHub blob URLs for remote repos. Returns file snippets alongside each ref.",
    used_by: ["Enricher"],
  },
  {
    name: "ChatOpenAI",
    file: null,
    desc: "LLM backbone for all generation, enrichment, and validation tasks. Model is set via OPENAI_MODEL env var (default: gpt-4o). Temperature is tuned per task: 0.3 for creation, 0.2 for enrichment, 0.1 for validation.",
    used_by: ["Creator", "Enricher", "Validator"],
  },
  {
    name: "TicketStore",
    file: "app/storage.py",
    desc: "In-memory dict backed by SQLite. Every mutation writes through immediately. Used as a singleton by the live app; tests inject an isolated instance via tmp_path.",
    used_by: ["Creator", "Enricher", "Validator", "Healer", "Kickstart"],
  },
  {
    name: "AgentLogger",
    file: "app/logger.py",
    desc: "Appends structured JSONL entries to data/agent_logs.jsonl on every agent run. Records: event, agent, ticket_id, duration_ms, status, and details. Never raises — logging must not crash agent execution.",
    used_by: ["Creator", "Enricher", "Validator", "Healer", "Kickstart"],
  },
];

// ── Rendering ──────────────────────────────────────────────────────────────

function renderAgents() {
  document.getElementById('agent-grid').innerHTML = AGENTS.map((a, i) => `
    <div class="agent-card">
      <div class="agent-head">
        <span class="agent-icon">${a.icon}</span>
        <span class="agent-name">${esc(a.name)}</span>
        <button class="view-code-btn" data-file="${esc(a.file)}">View Code</button>
        <span class="agent-file">${esc(a.file)}</span>
      </div>
      <p class="agent-mission">${esc(a.mission)}</p>
      <div class="mermaid-wrap">
        <div class="mermaid" id="mermaid-${i}">${a.mermaid}</div>
      </div>
      <div class="meta-row">
        <span class="meta-key">Trigger</span>
        <span class="trigger-code">${esc(a.trigger)}</span>
      </div>
      <div class="meta-row">
        <span class="meta-key">Tools</span>
        ${a.tools.map(t => `<span class="tool-tag">${esc(t)}</span>`).join('')}
      </div>
    </div>
  `).join('');
}

function renderTools() {
  document.getElementById('tool-list').innerHTML = TOOLS.map(t => `
    <div class="tool-card">
      <div class="tool-head">
        <span class="tool-name">${esc(t.name)}</span>
        ${t.file ? `<button class="view-code-btn small" data-file="${esc(t.file)}">View Code</button>` : ''}
        <span class="tool-file">${esc(t.file || 'langchain-openai')}</span>
      </div>
      <p class="tool-desc">${esc(t.desc)}</p>
      <div class="tool-used-by">
        <span class="meta-key">Used by</span>
        ${t.used_by.map(a => `<span class="used-by-tag">${esc(a)}</span>`).join('')}
      </div>
    </div>
  `).join('');
}

// ── Code drawer ────────────────────────────────────────────────────────────

function openCodeDrawer(file) {
  const drawer = document.getElementById('code-drawer');
  const backdrop = document.getElementById('code-backdrop');
  document.getElementById('code-drawer-file').textContent = file;
  const pre = document.getElementById('code-drawer-content');
  pre.textContent = 'Loading…';
  drawer.classList.add('open');
  backdrop.classList.add('open');
  fetch(`/api/source?file=${encodeURIComponent(file)}`)
    .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
    .then(d => { pre.textContent = d.content; })
    .catch(e => { pre.textContent = `Error loading file: ${e}`; });
}

function closeCodeDrawer() {
  document.getElementById('code-drawer').classList.remove('open');
  document.getElementById('code-backdrop').classList.remove('open');
}

// ── Init ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  renderAgents();
  renderTools();

  await mermaid.run({ nodes: document.querySelectorAll('.mermaid') });

  document.addEventListener('click', e => {
    const btn = e.target.closest('.view-code-btn');
    if (btn) openCodeDrawer(btn.dataset.file);
  });
  document.getElementById('code-drawer-close').addEventListener('click', closeCodeDrawer);
  document.getElementById('code-backdrop').addEventListener('click', closeCodeDrawer);
});
