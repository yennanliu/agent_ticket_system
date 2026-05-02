import pytest
from datetime import datetime
from app.models import Ticket


def test_ticket_defaults():
    t = Ticket(title="T", description="D")
    assert t.status == "open"
    assert t.priority == "medium"
    assert t.labels == []
    assert t.source_repo == ""
    assert t.acceptance_criteria == []
    assert t.related_files == []
    assert t.technical_notes == ""
    assert t.suggested_assignee == ""


def test_ticket_id_is_generated():
    t = Ticket(title="T", description="D")
    assert t.id
    assert len(t.id) == 36  # UUID4 format


def test_two_tickets_have_different_ids():
    t1 = Ticket(title="T", description="D")
    t2 = Ticket(title="T", description="D")
    assert t1.id != t2.id


def test_ticket_timestamps_are_set():
    t = Ticket(title="T", description="D")
    assert isinstance(t.created_at, datetime)
    assert isinstance(t.updated_at, datetime)


def test_ticket_full_fields(sample_ticket):
    assert sample_ticket.title == "Fix login bug"
    assert sample_ticket.status == "open"
    assert sample_ticket.priority == "high"
    assert "bug" in sample_ticket.labels


def test_ticket_serializes_to_dict(sample_ticket):
    d = sample_ticket.model_dump()
    assert d["title"] == "Fix login bug"
    assert "id" in d
    assert "created_at" in d
