"""
Integration tests — spin up the full FastAPI app (in-process) via httpx AsyncClient
and exercise the complete HTTP stack: routing, template rendering, API persistence,
and agent endpoints (LLM calls are mocked at the agent-function level).

These tests use a temporary data directory so the real data/tickets.json is untouched.
"""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.models import Ticket
from app.storage import TicketStore
from app.logger import AgentLogger
from main import create_app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def integration_store(tmp_path):
    return TicketStore(data_dir=str(tmp_path))


@pytest.fixture
def integration_logger(tmp_path):
    return AgentLogger(log_path=str(tmp_path / "test_agent_logs.jsonl"))


@pytest.fixture
async def iclient(integration_store, integration_logger):
    app = create_app(store=integration_store, logger=integration_logger)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, integration_store, integration_logger


# ── HTML page rendering ────────────────────────────────────────────────────────

async def test_landing_page_renders(iclient):
    c, *_ = iclient
    r = await c.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Agent Ticket System" in r.text
    assert "shared.css" in r.text
    assert "shared.js" in r.text


async def test_tickets_page_renders(iclient):
    c, *_ = iclient
    r = await c.get("/tickets")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "shared.css" in r.text
    assert "index.js" in r.text


async def test_review_page_renders(iclient):
    c, *_ = iclient
    r = await c.get("/review")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "review.js" in r.text


async def test_logs_page_renders(iclient):
    c, *_ = iclient
    r = await c.get("/logs")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "logs.js" in r.text


async def test_ticket_detail_page_renders(iclient):
    c, store, _ = iclient
    t = Ticket(title="Integration ticket", description="Test")
    store.create(t)
    r = await c.get(f"/tickets/{t.id}")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "ticket.js" in r.text


async def test_ticket_page_unknown_id_still_200(iclient):
    c, *_ = iclient
    r = await c.get("/tickets/unknown-id-xyz")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


async def test_nav_active_class_tickets(iclient):
    c, *_ = iclient
    r = await c.get("/tickets")
    assert 'class="nav-link active"' in r.text or "active" in r.text


async def test_nav_active_class_logs(iclient):
    c, *_ = iclient
    r = await c.get("/logs")
    assert "Agent Logs" in r.text


# ── Full ticket lifecycle via API ──────────────────────────────────────────────

async def test_full_create_read_update_delete(iclient):
    c, store, _ = iclient

    # Create
    r = await c.post("/api/tickets", json={
        "title": "Integration task",
        "description": "Full lifecycle test",
        "priority": "high",
        "importance": "critical",
        "labels": ["integration", "test"],
    })
    assert r.status_code == 201
    ticket_id = r.json()["id"]
    assert r.json()["title"] == "Integration task"
    assert r.json()["priority"] == "high"

    # Read via list
    r = await c.get("/api/tickets")
    assert r.status_code == 200
    ids = [t["id"] for t in r.json()]
    assert ticket_id in ids

    # Read individual
    r = await c.get(f"/api/tickets/{ticket_id}")
    assert r.status_code == 200
    assert r.json()["importance"] == "critical"

    # Update
    r = await c.put(f"/api/tickets/{ticket_id}", json={"status": "in_progress", "priority": "low"})
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"
    assert r.json()["priority"] == "low"

    # Persisted to store
    assert store.get(ticket_id).status == "in_progress"

    # Delete
    r = await c.delete(f"/api/tickets/{ticket_id}")
    assert r.status_code == 204

    # Gone
    r = await c.get(f"/api/tickets/{ticket_id}")
    assert r.status_code == 404

    # Removed from store
    assert store.get(ticket_id) is None


async def test_create_ticket_defaults(iclient):
    c, *_ = iclient
    r = await c.post("/api/tickets", json={"title": "Defaults check"})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "open"
    assert data["priority"] == "medium"
    assert data["importance"] == "medium"
    assert data["labels"] == []
    assert data["source_repo"] == ""


async def test_create_ticket_missing_title_returns_422(iclient):
    c, *_ = iclient
    r = await c.post("/api/tickets", json={"description": "No title"})
    assert r.status_code == 422


async def test_update_labels(iclient):
    c, *_ = iclient
    r = await c.post("/api/tickets", json={"title": "Label test"})
    tid = r.json()["id"]
    r = await c.put(f"/api/tickets/{tid}", json={"labels": ["a", "b", "c"]})
    assert r.json()["labels"] == ["a", "b", "c"]


# ── Approve / Reject workflow ──────────────────────────────────────────────────

async def test_approve_reject_workflow(iclient):
    c, store, _ = iclient

    # Create a draft
    t = Ticket(title="Draft ticket", description="Needs review", status="draft")
    store.create(t)

    # Approve → becomes open
    r = await c.post(f"/api/tickets/{t.id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "open"
    assert store.get(t.id).status == "open"

    # Cannot approve again (not draft)
    r = await c.post(f"/api/tickets/{t.id}/approve")
    assert r.status_code == 400

    # Create another draft and reject it
    t2 = Ticket(title="Reject me", description="Bad ticket", status="draft")
    store.create(t2)
    r = await c.post(f"/api/tickets/{t2.id}/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


# ── Batch create ───────────────────────────────────────────────────────────────

async def test_batch_create_produces_drafts_and_persists(iclient):
    c, store, _ = iclient
    r = await c.post("/api/agents/create-batch", json={
        "titles": ["Alpha", "Beta", "Gamma"],
        "repo_path": "/tmp/repo",
    })
    assert r.status_code == 201
    tickets = r.json()
    assert len(tickets) == 3
    for t in tickets:
        assert t["status"] == "draft"
        assert t["source_repo"] == "/tmp/repo"
        assert store.get(t["id"]) is not None


# ── Agent endpoints with mocked LLM ───────────────────────────────────────────

async def test_create_from_repo_integration(iclient):
    c, store, _ = iclient

    mock_tickets = [
        Ticket(title="Add auth", description="Implement OAuth", source_repo="/tmp/repo"),
        Ticket(title="Fix bug", description="Null pointer", source_repo="/tmp/repo"),
    ]

    with patch("app.agents.creator._llm_generate_tickets", return_value=[
        {"title": t.title, "description": t.description, "priority": "medium",
         "importance": "medium", "labels": [], "business_req": "", "stakeholder": "", "user_story": ""}
        for t in mock_tickets
    ]), patch("app.repo_tools.read_repo", return_value={
        "name": "test-repo", "readme": "", "file_tree": [], "file_contents": "",
    }), patch("app.agents.validator._llm_validate_ticket", return_value={
        "validation_score": 0.8, "validation_notes": "Good", "validation_passed": True,
    }):
        r = await c.post("/api/agents/create-from-repo", json={"repo_path": "/tmp/repo"})

    assert r.status_code == 200
    tickets = r.json()
    assert len(tickets) == 2
    titles = [t["title"] for t in tickets]
    assert "Add auth" in titles
    assert "Fix bug" in titles
    # All persisted to store
    for t in tickets:
        assert store.get(t["id"]) is not None


async def test_enrich_ticket_integration(iclient):
    c, store, _ = iclient

    t = Ticket(title="Add tests", description="Need coverage", source_repo="/tmp/repo")
    store.create(t)

    with patch("app.agents.enricher._llm_enrich_ticket", return_value={
        "acceptance_criteria": ["Tests pass", "Coverage > 80%"],
        "related_files": ["tests/test_api.py"],
        "technical_notes": "Use pytest fixtures",
        "suggested_assignee": "backend",
        "business_req": "Quality assurance",
        "stakeholder": "Engineering",
        "user_story": "As a dev, I want tests",
        "suggested_change_refs": [],
    }), patch("app.repo_tools.read_repo", return_value={
        "name": "test-repo", "readme": "", "file_tree": [], "file_contents": "",
    }), patch("app.search_tools.find_refs", return_value=[]):
        r = await c.post(f"/api/agents/enrich/{t.id}", json={"repo_path": "/tmp/repo"})

    assert r.status_code == 200
    data = r.json()
    assert data["acceptance_criteria"] == ["Tests pass", "Coverage > 80%"]
    assert data["technical_notes"] == "Use pytest fixtures"
    assert store.get(t.id).suggested_assignee == "backend"


async def test_validate_ticket_integration(iclient):
    c, store, _ = iclient

    t = Ticket(
        title="Validate me",
        description="Something",
        acceptance_criteria=["AC1", "AC2"],
        related_files=["app/main.py"],
        technical_notes="Use async",
    )
    store.create(t)

    with patch("app.agents.validator._llm_validate_ticket", return_value={
        "validation_score": 0.75,
        "validation_notes": "Solid ticket, minor gaps",
        "validation_passed": True,
    }):
        r = await c.post(f"/api/agents/validate/{t.id}")

    assert r.status_code == 200
    data = r.json()
    assert data["validation_score"] == 0.75
    assert data["validation_passed"] is True
    assert store.get(t.id).validation_passed is True


async def test_heal_ticket_integration(iclient):
    c, store, _ = iclient

    t = Ticket(
        title="Low score ticket", description="Sparse",
        source_repo="/tmp/repo",
        acceptance_criteria=["AC1"],
        technical_notes="notes",
        related_files=["f.py"],
    )
    store.create(t)

    # Validator first call: fail → healer triggers enrich → second call: pass
    validate_responses = [
        {"validation_score": 0.4, "validation_notes": "Too vague", "validation_passed": False},
        {"validation_score": 0.8, "validation_notes": "Improved", "validation_passed": True},
    ]
    enrich_response = {
        "acceptance_criteria": ["AC1", "AC2"],
        "related_files": ["app/main.py"],
        "technical_notes": "Better notes",
        "suggested_assignee": "backend",
        "business_req": "b", "stakeholder": "s", "user_story": "u",
        "suggested_change_refs": [],
    }

    with patch("app.agents.validator._llm_validate_ticket", side_effect=validate_responses), \
         patch("app.agents.enricher._llm_enrich_ticket", return_value=enrich_response), \
         patch("app.repo_tools.read_repo", return_value={
             "name": "r", "readme": "", "file_tree": [], "file_contents": "",
         }), \
         patch("app.search_tools.find_refs", return_value=[]):
        r = await c.post(f"/api/agents/heal/{t.id}")

    assert r.status_code == 200
    data = r.json()
    assert data["validation_passed"] is True
    assert data["validation_score"] == 0.8


# ── Log persistence ────────────────────────────────────────────────────────────

async def test_logs_written_on_agent_action(iclient):
    c, store, logger = iclient

    t = Ticket(title="Logged ticket", description="x", source_repo="/tmp/repo")
    store.create(t)

    with patch("app.agents.validator._llm_validate_ticket", return_value={
        "validation_score": 0.9, "validation_notes": "Great", "validation_passed": True,
    }):
        await c.post(f"/api/agents/validate/{t.id}")

    r = await c.get("/api/logs")
    assert r.status_code == 200
    logs = r.json()
    assert any(e["event"] == "validate" for e in logs)
    assert any(e["ticket_id"] == t.id for e in logs)


async def test_clear_logs_integration(iclient):
    c, store, logger = iclient

    logger.log("test_event", "test_agent", status="success")
    r = await c.get("/api/logs")
    assert len(r.json()) == 1

    r = await c.delete("/api/logs")
    assert r.status_code == 204

    r = await c.get("/api/logs")
    assert r.json() == []


# ── Static assets ──────────────────────────────────────────────────────────────

async def test_shared_css_served(iclient):
    c, *_ = iclient
    r = await c.get("/static/shared.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]
    assert "--accent" in r.text


async def test_shared_js_served(iclient):
    c, *_ = iclient
    r = await c.get("/static/shared.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]
    assert "apiFetch" in r.text
    assert "withLoading" in r.text


async def test_page_js_served(iclient):
    c, *_ = iclient
    for page in ["index", "ticket", "review", "logs", "landing"]:
        r = await c.get(f"/static/pages/{page}.js")
        assert r.status_code == 200, f"Missing {page}.js"


async def test_page_css_served(iclient):
    c, *_ = iclient
    for page in ["index", "ticket", "review", "logs", "landing"]:
        r = await c.get(f"/static/pages/{page}.css")
        assert r.status_code == 200, f"Missing {page}.css"
