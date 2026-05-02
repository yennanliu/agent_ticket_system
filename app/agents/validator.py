import json
import os
import time
from typing import TypedDict, Optional

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from app.models import Ticket
from app.storage import TicketStore


class ValidatorState(TypedDict):
    ticket_id: str
    ticket: Optional[dict]
    validation_result: dict


def _llm_validate_ticket(ticket: dict) -> dict:
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    llm = ChatOpenAI(model=model, temperature=0.1)

    ac = ticket.get("acceptance_criteria", [])
    files = ticket.get("related_files", [])
    notes = ticket.get("technical_notes", "")
    refs = ticket.get("suggested_change_refs", [])

    prompt = f"""You are a senior engineering lead reviewing a ticket for enrichment quality.

Ticket:
- Title: {ticket['title']}
- Description: {ticket.get('description', '')}
- Acceptance Criteria: {json.dumps(ac)}
- Related Files: {json.dumps(files)}
- Technical Notes: {notes}
- Change Refs: {len(refs)} ref(s) provided

Grade this ticket on 4 criteria worth 0.25 each:
1. Acceptance criteria are specific and testable (not vague like "it works" or "it is done")
2. Related files are plausible given the ticket title and description
3. Technical notes are specific and actionable (not generic platitudes)
4. At least one change reference exists

Return ONLY a JSON object:
{{"score": <float 0.0-1.0>, "notes": "<one concise sentence summarising strengths or gaps>"}}"""

    response = llm.invoke(prompt)
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    result = json.loads(content.strip())
    score = min(1.0, max(0.0, float(result.get("score", 0.0))))
    return {
        "validation_score": score,
        "validation_notes": str(result.get("notes", "")),
        "validation_passed": score >= 0.6,
    }


def _node_fetch_ticket(state: ValidatorState, store: TicketStore) -> ValidatorState:
    ticket = store.get(state["ticket_id"])
    if ticket is None:
        raise ValueError(f"Ticket {state['ticket_id']} not found")
    state["ticket"] = ticket.model_dump(mode="json")
    return state


def _node_validate(state: ValidatorState) -> ValidatorState:
    state["validation_result"] = _llm_validate_ticket(state["ticket"])
    return state


def _node_save(state: ValidatorState, store: TicketStore) -> ValidatorState:
    store.update(state["ticket_id"], state["validation_result"])
    return state


def _build_graph(store: TicketStore) -> StateGraph:
    graph = StateGraph(ValidatorState)
    graph.add_node("fetch_ticket", lambda s: _node_fetch_ticket(s, store))
    graph.add_node("validate", _node_validate)
    graph.add_node("save_ticket", lambda s: _node_save(s, store))
    graph.set_entry_point("fetch_ticket")
    graph.add_edge("fetch_ticket", "validate")
    graph.add_edge("validate", "save_ticket")
    graph.add_edge("save_ticket", END)
    return graph.compile()


def run_validator(ticket_id: str, store: TicketStore, logger=None) -> Ticket:
    start = time.time()
    try:
        app = _build_graph(store)
        app.invoke({"ticket_id": ticket_id, "ticket": None, "validation_result": {}})
        ticket = store.get(ticket_id)
        if logger:
            score = ticket.validation_score if ticket else None
            logger.log("validate", "validator", ticket_id=ticket_id,
                       duration_ms=(time.time() - start) * 1000,
                       status="success", details=f"score={score}")
        return ticket
    except Exception as e:
        if logger:
            logger.log("validate", "validator", ticket_id=ticket_id,
                       duration_ms=(time.time() - start) * 1000,
                       status="error", details=str(e))
        raise
