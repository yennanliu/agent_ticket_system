import json
import os
import time
from typing import TypedDict, Optional

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from app.models import Ticket
from app.storage import TicketStore

# Maps parent type → (child type, count hint for prompt)
CHILD_MAP = {
    "epic":  ("story",   "3–5 user stories"),
    "story": ("task",    "2–4 actionable tasks"),
    "task":  ("subtask", "2–3 specific subtasks"),
}


class SplitterState(TypedDict):
    ticket_id: str
    ticket: Optional[dict]
    child_specs: list[dict]
    children: list[Ticket]


def _llm_split(ticket: dict) -> list[dict]:
    t_type = ticket.get("ticket_type", "task")
    child_type, count_hint = CHILD_MAP.get(t_type, ("subtask", "2–3 subtasks"))
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    llm = ChatOpenAI(model=model, temperature=0.3)

    prompt = f"""You are a senior tech lead and scrum master decomposing a {t_type} into {count_hint}.

Parent {t_type.capitalize()}:
- Title: {ticket['title']}
- Description: {ticket.get('description', '')}
- Business Requirement: {ticket.get('business_req', '')}
- Acceptance Criteria: {json.dumps(ticket.get('acceptance_criteria', []))}
- User Story: {ticket.get('user_story', '')}

Rules:
- Each {child_type} must be independently deliverable
- Together they must fully cover the parent's scope — no gaps
- Start each title with an action verb (Implement, Add, Fix, Create, etc.)
- Inherit priority from the parent

Return ONLY a JSON array. Each item must have exactly these keys:
- title (string, max 80 chars)
- description (string, 2–3 sentences)
- priority (string, use: "{ticket.get('priority', 'medium')}")
- importance (string: "low" | "medium" | "high" | "critical")
- labels (array of strings, refine from: {json.dumps(ticket.get('labels', []))})
- user_story (string, "As a <role>, I want <goal> so that <benefit>")
- business_req (string, specific to this {child_type})

Return only the JSON array."""

    response = llm.invoke(prompt)
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())


def _node_fetch(state: SplitterState, store: TicketStore) -> SplitterState:
    ticket = store.get(state["ticket_id"])
    if ticket is None:
        raise ValueError(f"Ticket {state['ticket_id']} not found")
    state["ticket"] = ticket.model_dump(mode="json")
    return state


def _node_split(state: SplitterState) -> SplitterState:
    state["child_specs"] = _llm_split(state["ticket"])
    return state


def _node_save(state: SplitterState, store: TicketStore) -> SplitterState:
    parent = state["ticket"]
    t_type = parent.get("ticket_type", "task")
    child_type = CHILD_MAP.get(t_type, ("subtask", ""))[0]
    children = []
    for spec in state["child_specs"]:
        child = Ticket(
            title=spec.get("title", "Untitled"),
            description=spec.get("description", ""),
            status="draft",
            priority=spec.get("priority", parent.get("priority", "medium")),
            importance=spec.get("importance", "medium"),
            labels=spec.get("labels", parent.get("labels", [])),
            source_repo=parent.get("source_repo", ""),
            business_req=spec.get("business_req", ""),
            stakeholder=parent.get("stakeholder", ""),
            user_story=spec.get("user_story", ""),
            ticket_type=child_type,
            parent_id=parent["id"],
        )
        store.create(child)
        children.append(child)
    state["children"] = children
    return state


def _build_graph(store: TicketStore):
    g = StateGraph(SplitterState)
    g.add_node("fetch_ticket", lambda s: _node_fetch(s, store))
    g.add_node("split", _node_split)
    g.add_node("save_children", lambda s: _node_save(s, store))
    g.set_entry_point("fetch_ticket")
    g.add_edge("fetch_ticket", "split")
    g.add_edge("split", "save_children")
    g.add_edge("save_children", END)
    return g.compile()


def run_splitter(ticket_id: str, store: TicketStore, logger=None) -> list[Ticket]:
    start = time.time()
    try:
        result = _build_graph(store).invoke({
            "ticket_id": ticket_id,
            "ticket": None,
            "child_specs": [],
            "children": [],
        })
        children = result["children"]
        if logger:
            logger.log("split", "splitter", ticket_id=ticket_id,
                       duration_ms=(time.time() - start) * 1000,
                       status="success", details=f"created {len(children)} children")
        return children
    except Exception as e:
        if logger:
            logger.log("split", "splitter", ticket_id=ticket_id,
                       duration_ms=(time.time() - start) * 1000,
                       status="error", details=str(e))
        raise
