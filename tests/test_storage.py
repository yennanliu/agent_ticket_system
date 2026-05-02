import json
import pytest
from app.models import Ticket
from app.storage import TicketStore


def make_store(tmp_data_dir):
    return TicketStore(data_dir=str(tmp_data_dir))


def test_empty_store_returns_empty_list(tmp_data_dir):
    store = make_store(tmp_data_dir)
    assert store.get_all() == []


def test_create_and_get(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    result = store.get(sample_ticket.id)
    assert result is not None
    assert result.title == "Fix login bug"


def test_get_missing_id_returns_none(tmp_data_dir):
    store = make_store(tmp_data_dir)
    assert store.get("nonexistent") is None


def test_get_all_returns_all(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    t2 = Ticket(title="Another", description="Desc")
    store.create(sample_ticket)
    store.create(t2)
    assert len(store.get_all()) == 2


def test_update_merges_fields(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    updated = store.update(sample_ticket.id, {"status": "done", "priority": "low"})
    assert updated.status == "done"
    assert updated.priority == "low"
    assert updated.title == "Fix login bug"  # unchanged


def test_update_missing_id_returns_none(tmp_data_dir):
    store = make_store(tmp_data_dir)
    assert store.update("bad-id", {"status": "done"}) is None


def test_delete_removes_ticket(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    assert store.delete(sample_ticket.id) is True
    assert store.get(sample_ticket.id) is None


def test_delete_missing_id_returns_false(tmp_data_dir):
    store = make_store(tmp_data_dir)
    assert store.delete("bad-id") is False


def test_persists_to_json_file(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    json_path = tmp_data_dir / "tickets.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert any(t["id"] == sample_ticket.id for t in data)


def test_reloads_from_json_on_init(tmp_data_dir, sample_ticket):
    store1 = make_store(tmp_data_dir)
    store1.create(sample_ticket)
    # New store instance reads from the same file
    store2 = make_store(tmp_data_dir)
    assert store2.get(sample_ticket.id) is not None
