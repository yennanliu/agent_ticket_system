import json
import os
from typing import TypedDict, Optional

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from app.models import Ticket
from app.repo_tools import read_repo
from app.storage import TicketStore


class EnricherState(TypedDict):
    ticket_id: str
    source: str
    ticket: Optional[dict]
    repo_context: dict
    enriched_fields: dict


def _llm_enrich_ticket(ticket: dict, repo_context: dict) -> dict:
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    llm = ChatOpenAI(model=model, temperature=0.2)
    prompt = f"""You are a senior software engineer. Enrich the following task ticket with deeper technical context from the repository.

Ticket:
- Title: {ticket['title']}
- Description: {ticket['description']}
- Priority: {ticket['priority']}

Repository: {repo_context['name']}
README:
{repo_context['readme'][:2000]}

File tree:
{chr(10).join(repo_context['file_tree'][:40])}

File contents (excerpt):
{repo_context['file_contents'][:4000]}

Return ONLY a JSON object with these keys:
- acceptance_criteria (array of strings — specific, testable conditions for "done")
- related_files (array of file paths from the repo relevant to this ticket)
- technical_notes (string — implementation hints, edge cases, or gotchas)
- suggested_assignee (string — role or team best suited, e.g. "frontend", "devops", "")

Example:
{{"acceptance_criteria": ["..."], "related_files": ["..."], "technical_notes": "...", "suggested_assignee": "..."}}"""

    response = llm.invoke(prompt)
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


def _node_fetch_ticket(state: EnricherState, store: TicketStore) -> EnricherState:
    ticket = store.get(state["ticket_id"])
    if ticket is None:
        raise ValueError(f"Ticket {state['ticket_id']} not found")
    state["ticket"] = ticket.model_dump(mode="json")
    return state


def _node_fetch_context(state: EnricherState) -> EnricherState:
    state["repo_context"] = read_repo(state["source"])
    return state


def _node_enrich(state: EnricherState) -> EnricherState:
    state["enriched_fields"] = _llm_enrich_ticket(state["ticket"], state["repo_context"])
    return state


def _node_save(state: EnricherState, store: TicketStore) -> EnricherState:
    store.update(state["ticket_id"], state["enriched_fields"])
    return state


def _build_graph(store: TicketStore) -> StateGraph:
    graph = StateGraph(EnricherState)
    graph.add_node("fetch_ticket", lambda s: _node_fetch_ticket(s, store))
    graph.add_node("fetch_context", _node_fetch_context)
    graph.add_node("enrich", _node_enrich)
    graph.add_node("save_ticket", lambda s: _node_save(s, store))
    graph.set_entry_point("fetch_ticket")
    graph.add_edge("fetch_ticket", "fetch_context")
    graph.add_edge("fetch_context", "enrich")
    graph.add_edge("enrich", "save_ticket")
    graph.add_edge("save_ticket", END)
    return graph.compile()


def run_enricher(ticket_id: str, source: str, store: TicketStore) -> Ticket:
    app = _build_graph(store)
    app.invoke({
        "ticket_id": ticket_id,
        "source": source,
        "ticket": None,
        "repo_context": {},
        "enriched_fields": {},
    })
    return store.get(ticket_id)
