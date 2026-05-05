import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.models import Ticket


@pytest.fixture
async def client(app_with_store):
    async with AsyncClient(transport=ASGITransport(app=app_with_store), base_url="http://test") as c:
        yield c


# ── Tickets CRUD ─────────────────────────────────────────────────────────────

async def test_list_tickets_empty(client):
    r = await client.get("/api/tickets")
    assert r.status_code == 200
    assert r.json() == []


async def test_create_ticket(client):
    payload = {"title": "New task", "description": "Do something", "priority": "low"}
    r = await client.post("/api/tickets", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "New task"
    assert data["id"]


async def test_create_ticket_without_description(client):
    r = await client.post("/api/tickets", json={"title": "No desc ticket"})
    assert r.status_code == 201
    assert r.json()["description"] == ""


async def test_get_ticket(client, store, sample_ticket):
    store.create(sample_ticket)
    r = await client.get(f"/api/tickets/{sample_ticket.id}")
    assert r.status_code == 200
    assert r.json()["title"] == sample_ticket.title


async def test_get_ticket_not_found(client):
    r = await client.get("/api/tickets/nonexistent")
    assert r.status_code == 404


async def test_update_ticket(client, store, sample_ticket):
    store.create(sample_ticket)
    r = await client.put(f"/api/tickets/{sample_ticket.id}", json={"status": "done"})
    assert r.status_code == 200
    assert r.json()["status"] == "done"


async def test_update_ticket_not_found(client):
    r = await client.put("/api/tickets/bad-id", json={"status": "done"})
    assert r.status_code == 404


async def test_delete_ticket(client, store, sample_ticket):
    store.create(sample_ticket)
    r = await client.delete(f"/api/tickets/{sample_ticket.id}")
    assert r.status_code == 204
    r2 = await client.get(f"/api/tickets/{sample_ticket.id}")
    assert r2.status_code == 404


async def test_delete_ticket_not_found(client):
    r = await client.delete("/api/tickets/bad-id")
    assert r.status_code == 404


async def test_list_tickets_after_create(client):
    await client.post("/api/tickets", json={"title": "T1", "description": "D1"})
    await client.post("/api/tickets", json={"title": "T2", "description": "D2"})
    r = await client.get("/api/tickets")
    assert len(r.json()) == 2


# ── HTML pages ────────────────────────────────────────────────────────────────

async def test_index_page(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


async def test_ticket_detail_page(client, store, sample_ticket):
    store.create(sample_ticket)
    r = await client.get(f"/tickets/{sample_ticket.id}")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


async def test_ticket_page_nonexistent_id_still_returns_html(client):
    r = await client.get("/tickets/nonexistent-id")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


async def test_logs_page(client):
    r = await client.get("/logs")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


# ── Agent endpoints ───────────────────────────────────────────────────────────

async def test_create_from_repo(client, repo_context):
    mock_tickets = [
        Ticket(title="Task A", description="Desc A", source_repo="../linkedin-skill"),
        Ticket(title="Task B", description="Desc B", source_repo="../linkedin-skill"),
    ]
    with patch("app.api.agents.run_creator", return_value=mock_tickets):
        r = await client.post("/api/agents/create-from-repo", json={"repo_path": "../linkedin-skill"})
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert r.json()[0]["title"] == "Task A"


async def test_create_from_repo_missing_source(client):
    r = await client.post("/api/agents/create-from-repo", json={})
    assert r.status_code == 422


async def test_enrich_ticket(client, store, sample_ticket):
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={
        "acceptance_criteria": ["AC1"],
        "technical_notes": "Some notes",
    })
    with patch("app.api.agents.run_enricher", return_value=enriched):
        r = await client.post(
            f"/api/agents/enrich/{sample_ticket.id}",
            json={"repo_path": "../linkedin-skill"},
        )
    assert r.status_code == 200
    assert r.json()["acceptance_criteria"] == ["AC1"]


async def test_enrich_ticket_not_found(client):
    with patch("app.api.agents.run_enricher", side_effect=ValueError("not found")):
        r = await client.post("/api/agents/enrich/bad-id", json={"repo_path": "../linkedin-skill"})
    assert r.status_code == 404


# ── Batch enrich ──────────────────────────────────────────────────────────────

async def test_enrich_batch_all(client, store, sample_ticket):
    store.create(sample_ticket)
    t2 = Ticket(title="T2", description="D2")
    store.create(t2)
    enriched_1 = sample_ticket.model_copy(update={"acceptance_criteria": ["AC1"]})
    enriched_2 = t2.model_copy(update={"acceptance_criteria": ["AC2"]})
    with patch("app.api.agents.run_enricher", side_effect=[enriched_1, enriched_2]):
        r = await client.post("/api/agents/enrich-batch", json={"repo_path": "../linkedin-skill"})
    assert r.status_code == 200
    assert len(r.json()) == 2


async def test_enrich_batch_selected_ids(client, store, sample_ticket):
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={"acceptance_criteria": ["AC1"]})
    with patch("app.api.agents.run_enricher", return_value=enriched):
        r = await client.post("/api/agents/enrich-batch", json={
            "repo_path": "../linkedin-skill",
            "ticket_ids": [sample_ticket.id],
        })
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_enrich_batch_no_source_returns_empty(client):
    # No source + empty store → no tickets to enrich → 200 []
    r = await client.post("/api/agents/enrich-batch", json={})
    assert r.status_code == 200
    assert r.json() == []


async def test_enrich_batch_skips_missing_tickets(client):
    with patch("app.api.agents.run_enricher", side_effect=ValueError("not found")):
        r = await client.post("/api/agents/enrich-batch", json={
            "repo_path": "../linkedin-skill",
            "ticket_ids": ["bad-id"],
        })
    assert r.status_code == 200
    assert r.json() == []


# ── Batch create ──────────────────────────────────────────────────────────────

async def test_create_batch(client):
    r = await client.post("/api/agents/create-batch", json={
        "titles": ["Fix bug A", "Add feature B", "Write tests C"],
    })
    assert r.status_code == 201
    assert len(r.json()) == 3
    assert r.json()[0]["title"] == "Fix bug A"


async def test_create_batch_with_repo(client):
    r = await client.post("/api/agents/create-batch", json={
        "titles": ["Task 1"],
        "repo_path": "../my-project",
    })
    assert r.status_code == 201
    assert r.json()[0]["source_repo"] == "../my-project"


async def test_create_batch_empty_titles_fails(client):
    r = await client.post("/api/agents/create-batch", json={"titles": []})
    assert r.status_code == 422


# ── Validate ─────────────────────────────────────────────────────────────────

async def test_validate_ticket(client, store, sample_ticket):
    store.create(sample_ticket)
    validated = sample_ticket.model_copy(update={
        "validation_score": 0.8,
        "validation_notes": "Good ticket",
        "validation_passed": True,
    })
    with patch("app.api.agents.run_validator", return_value=validated):
        r = await client.post(f"/api/agents/validate/{sample_ticket.id}")
    assert r.status_code == 200
    assert r.json()["validation_score"] == 0.8
    assert r.json()["validation_passed"] is True


async def test_validate_ticket_not_found(client):
    with patch("app.api.agents.run_validator", side_effect=ValueError("not found")):
        r = await client.post("/api/agents/validate/bad-id")
    assert r.status_code == 404


# ── Heal ─────────────────────────────────────────────────────────────────────

async def test_kickstart_ticket(client, store, sample_ticket):
    store.create(sample_ticket)
    processed = sample_ticket.model_copy(update={
        "acceptance_criteria": ["AC1"],
        "validation_score": 0.8, "validation_passed": True,
    })
    with patch("app.api.agents.run_kickstart", return_value=processed):
        r = await client.post(f"/api/agents/kickstart/{sample_ticket.id}")
    assert r.status_code == 200
    assert r.json()["validation_score"] == 0.8
    assert r.json()["acceptance_criteria"] == ["AC1"]


async def test_kickstart_ticket_not_found(client):
    with patch("app.api.agents.run_kickstart", side_effect=ValueError("not found")):
        r = await client.post("/api/agents/kickstart/bad-id")
    assert r.status_code == 404


# ── Heal ─────────────────────────────────────────────────────────────────────

async def test_heal_ticket(client, store, sample_ticket):
    store.create(sample_ticket)
    healed = sample_ticket.model_copy(update={"validation_score": 0.9, "validation_passed": True, "validation_iterations": 1})
    with patch("app.api.agents.run_healer", return_value=healed):
        r = await client.post(f"/api/agents/heal/{sample_ticket.id}")
    assert r.status_code == 200
    assert r.json()["validation_score"] == 0.9
    assert r.json()["validation_iterations"] == 1


async def test_heal_ticket_not_found(client):
    with patch("app.api.agents.run_healer", side_effect=ValueError("not found")):
        r = await client.post("/api/agents/heal/bad-id")
    assert r.status_code == 404


# ── Approve / Reject ──────────────────────────────────────────────────────────

async def test_approve_draft_ticket(client, store):
    t = Ticket(title="Draft T", description="D", status="draft")
    store.create(t)
    r = await client.post(f"/api/tickets/{t.id}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "open"


async def test_approve_non_draft_returns_400(client, store, sample_ticket):
    store.create(sample_ticket)  # status="open"
    r = await client.post(f"/api/tickets/{sample_ticket.id}/approve")
    assert r.status_code == 400


async def test_approve_missing_ticket_returns_404(client):
    r = await client.post("/api/tickets/bad-id/approve")
    assert r.status_code == 404


async def test_reject_draft_ticket(client, store):
    t = Ticket(title="Draft T", description="D", status="draft")
    store.create(t)
    r = await client.post(f"/api/tickets/{t.id}/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


async def test_reject_non_draft_returns_400(client, store, sample_ticket):
    store.create(sample_ticket)
    r = await client.post(f"/api/tickets/{sample_ticket.id}/reject")
    assert r.status_code == 400


async def test_reject_missing_ticket_returns_404(client):
    r = await client.post("/api/tickets/bad-id/reject")
    assert r.status_code == 404


# ── Draft status on AI creation ───────────────────────────────────────────────

async def test_create_batch_produces_drafts(client):
    r = await client.post("/api/agents/create-batch", json={"titles": ["Task A", "Task B"]})
    assert r.status_code == 201
    for ticket in r.json():
        assert ticket["status"] == "draft"


async def test_review_page(client):
    r = await client.get("/review")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


# ── Logs endpoint ─────────────────────────────────────────────────────────────

async def test_get_logs_empty(client):
    r = await client.get("/api/logs")
    assert r.status_code == 200
    assert r.json() == []


async def test_get_logs_returns_entries(client, logger):
    logger.log("enrich", "enricher", ticket_id="abc", status="success")
    r = await client.get("/api/logs")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["event"] == "enrich"


async def test_clear_logs(client, logger):
    logger.log("enrich", "enricher")
    r = await client.delete("/api/logs")
    assert r.status_code == 204
    r2 = await client.get("/api/logs")
    assert r2.json() == []
