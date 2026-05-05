import json
import os
import time
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from app.models import Ticket
from app.repo_tools import read_repo
from app.storage import TicketStore
from app.agents.validator import run_validator


class CreatorState(TypedDict):
    source: str
    repo_context: dict
    ticket_drafts: list[dict]
    created_tickets: list[Ticket]


def _llm_generate_tickets(repo_context: dict) -> list[dict]:
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    llm = ChatOpenAI(model=model, temperature=0.3)
    prompt = f"""You are a software project manager. Analyze the repository below and generate 5-10 actionable development task tickets.

Project: {repo_context['name']}
README:
{repo_context['readme'][:3000]}

File tree:
{chr(10).join(repo_context['file_tree'][:50])}

File contents (excerpt):
{repo_context['file_contents'][:5000]}

Return ONLY a JSON array of tickets. Each ticket must have these keys:
- title (string, max 80 chars)
- description (string, 1-3 sentences)
- priority ("low", "medium", or "high")
- importance ("low", "medium", "high", or "critical")
- labels (array of short strings like ["bug", "feature", "ci", "docs"])
- business_req (string — the business need or goal this ticket addresses)
- stakeholder (string — who requested or benefits from this, e.g. "Product", "Engineering", "Customer")
- user_story (string — "As a <role>, I want <goal> so that <benefit>")

Example format:
[{{"title": "...", "description": "...", "priority": "medium", "importance": "medium", "labels": ["feature"], "business_req": "...", "stakeholder": "Product", "user_story": "As a user, I want ..."}}]"""

    response = llm.invoke(prompt)
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


def _node_fetch_context(state: CreatorState) -> CreatorState:
    state["repo_context"] = read_repo(state["source"])
    return state


def _node_generate(state: CreatorState) -> CreatorState:
    state["ticket_drafts"] = _llm_generate_tickets(state["repo_context"])
    return state


def _node_save(state: CreatorState, store: TicketStore) -> CreatorState:
    tickets = []
    for draft in state["ticket_drafts"]:
        ticket = Ticket(
            title=draft.get("title", "Untitled"),
            description=draft.get("description", ""),
            status="draft",
            priority=draft.get("priority", "medium"),
            importance=draft.get("importance", "medium"),
            labels=draft.get("labels", []),
            source_repo=state["source"],
            business_req=draft.get("business_req", ""),
            stakeholder=draft.get("stakeholder", ""),
            user_story=draft.get("user_story", ""),
        )
        store.create(ticket)
        tickets.append(ticket)
    state["created_tickets"] = tickets
    return state


def _build_graph(store: TicketStore) -> StateGraph:
    graph = StateGraph(CreatorState)
    graph.add_node("fetch_context", _node_fetch_context)
    graph.add_node("generate_tickets", _node_generate)
    graph.add_node("save_tickets", lambda s: _node_save(s, store))
    graph.set_entry_point("fetch_context")
    graph.add_edge("fetch_context", "generate_tickets")
    graph.add_edge("generate_tickets", "save_tickets")
    graph.add_edge("save_tickets", END)
    return graph.compile()


def run_creator(source: str, store: TicketStore, logger=None) -> list[Ticket]:
    start = time.time()
    try:
        app = _build_graph(store)
        result = app.invoke({"source": source, "repo_context": {}, "ticket_drafts": [], "created_tickets": []})
        tickets = result["created_tickets"]

        validated = []
        for ticket in tickets:
            try:
                validated.append(run_validator(ticket.id, store))
            except Exception:
                validated.append(store.get(ticket.id) or ticket)

        if logger:
            logger.log("create", "creator", duration_ms=(time.time() - start) * 1000,
                       status="success", details=f"created {len(validated)} tickets from {source}")
        return validated
    except Exception as e:
        if logger:
            logger.log("create", "creator", duration_ms=(time.time() - start) * 1000,
                       status="error", details=str(e))
        raise
