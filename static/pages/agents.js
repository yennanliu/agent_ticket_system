/* pages/agents.js — agent catalog */

const AGENTS = [
  {
    name: "Creator",
    icon: "⬡",
    file: "app/agents/creator.py",
    mission: "Analyses a repository and generates 5–10 actionable draft tickets in one pass. Reads the full repo context, prompts the LLM, then saves each ticket and kicks off validation.",
    graph: ["fetch_context", "generate_tickets", "save_tickets"],
    trigger: "POST /api/agents/create-from-repo",
    tools: ["read_repo", "ChatOpenAI", "TicketStore"],
  },
  {
    name: "Enricher",
    icon: "◈",
    file: "app/agents/enricher.py",
    mission: "Adds acceptance criteria, related files, technical notes, suggested assignee, and change refs to a ticket. Accepts optional validation feedback for the heal loop.",
    graph: ["fetch_ticket", "fetch_context", "enrich", "find_refs", "save_ticket"],
    trigger: "POST /api/agents/enrich/:id",
    tools: ["read_repo", "find_refs", "ChatOpenAI", "TicketStore"],
  },
  {
    name: "Validator",
    icon: "✦",
    file: "app/agents/validator.py",
    mission: "Scores a ticket 0–1 across four quality dimensions — testable criteria, plausible files, actionable notes, change refs — and marks it passed if score ≥ 0.6.",
    graph: ["fetch_ticket", "validate", "save_ticket"],
    trigger: "POST /api/agents/validate/:id",
    tools: ["ChatOpenAI", "TicketStore"],
  },
  {
    name: "Healer",
    icon: "↺",
    file: "app/agents/healer.py",
    mission: "Re-enriches and re-validates a ticket in a feedback loop until score ≥ 0.75 or max 3 iterations. Passes validation notes as feedback to the Enricher each cycle.",
    graph: ["validate", "→ enrich (w/ feedback)", "→ validate", "loop ×3"],
    trigger: "POST /api/agents/heal/:id",
    tools: ["Enricher", "Validator"],
  },
  {
    name: "Kickstart",
    icon: "⚡",
    file: "app/agents/kickstart.py",
    mission: "Full pipeline for newly created tickets. Enriches if a repo is available, validates, then retries up to 3× until score ≥ 0.60. Called automatically after ticket creation.",
    graph: ["enrich?", "validate", "retry loop ×3", "∎"],
    trigger: "POST /api/agents/kickstart/:id",
    tools: ["Enricher", "Validator"],
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
    name: "find_refs",
    file: "app/search_tools.py",
    desc: "Builds change references for a ticket's related files. Constructs GitHub blob URLs for remote repos; falls back to DuckDuckGo search for local paths. Classifies each file as code, doc, or design.",
    used_by: ["Enricher"],
  },
  {
    name: "ChatOpenAI",
    file: "langchain-openai",
    desc: "LLM backbone for all generation, enrichment, and validation tasks. Model is set via OPENAI_MODEL env var (default: gpt-4o). Temperature is tuned per task: 0.3 for creation, 0.2 for enrichment, 0.1 for validation.",
    used_by: ["Creator", "Enricher", "Validator"],
  },
  {
    name: "TicketStore",
    file: "app/storage.py",
    desc: "In-memory dict with JSON persistence to data/tickets.json. Every mutation triggers a full write. Used as a singleton by the live app; tests inject an isolated instance via tmp_path.",
    used_by: ["Creator", "Enricher", "Validator", "Healer", "Kickstart"],
  },
  {
    name: "AgentLogger",
    file: "app/logger.py",
    desc: "Appends structured JSONL entries to data/agent_logs.jsonl on every agent run. Records: event, agent, ticket_id, duration_ms, status, and details. Never raises — logging must not crash agent execution.",
    used_by: ["Creator", "Enricher", "Validator", "Healer", "Kickstart"],
  },
];

function renderAgents() {
  document.getElementById('agent-grid').innerHTML = AGENTS.map(a => `
    <div class="agent-card">
      <div class="agent-head">
        <span class="agent-icon">${a.icon}</span>
        <span class="agent-name">${esc(a.name)}</span>
        <span class="agent-file">${esc(a.file)}</span>
      </div>
      <p class="agent-mission">${esc(a.mission)}</p>
      <div class="flow-wrap">
        ${a.graph.map((n, i) =>
          `<span class="flow-node">${esc(n)}</span>${i < a.graph.length - 1 ? '<span class="flow-arrow">→</span>' : ''}`
        ).join('')}
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
        <span class="tool-file">${esc(t.file)}</span>
      </div>
      <p class="tool-desc">${esc(t.desc)}</p>
      <div class="tool-used-by">
        <span class="meta-key">Used by</span>
        ${t.used_by.map(a => `<span class="used-by-tag">${esc(a)}</span>`).join('')}
      </div>
    </div>
  `).join('');
}

document.addEventListener('DOMContentLoaded', () => {
  renderAgents();
  renderTools();
});
