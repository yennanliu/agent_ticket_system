import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.models import Ticket
from app.storage import TicketStore


@pytest.fixture
def store(tmp_data_dir):
    return TicketStore(data_dir=str(tmp_data_dir))


@pytest.fixture
def app_with_store(store):
    from main import create_app
    return create_app(store)


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


# ── Agent endpoints ───────────────────────────────────────────────────────────

async def test_create_from_repo(client, store, repo_context):
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


async def test_enrich_ticket(client, store, sample_ticket, repo_context):
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
