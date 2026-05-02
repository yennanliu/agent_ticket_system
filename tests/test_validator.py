import pytest
from unittest.mock import patch
from app.storage import TicketStore
from app.agents.validator import run_validator


MOCK_PASS = {"validation_score": 0.75, "validation_notes": "Good ACs but notes are generic.", "validation_passed": True}
MOCK_FAIL = {"validation_score": 0.25, "validation_notes": "No ACs, no related files, vague notes.", "validation_passed": False}


def make_store(tmp_data_dir):
    return TicketStore(data_dir=str(tmp_data_dir))


def test_validator_sets_score_and_notes(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    with patch("app.agents.validator._llm_validate_ticket", return_value=MOCK_PASS):
        result = run_validator(sample_ticket.id, store)
    assert result.validation_score == 0.75
    assert result.validation_passed is True
    assert "generic" in result.validation_notes


def test_validator_fail_threshold(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    with patch("app.agents.validator._llm_validate_ticket", return_value=MOCK_FAIL):
        result = run_validator(sample_ticket.id, store)
    assert result.validation_passed is False
    assert result.validation_score == 0.25


def test_validator_persists_to_store(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    with patch("app.agents.validator._llm_validate_ticket", return_value=MOCK_PASS):
        run_validator(sample_ticket.id, store)
    stored = store.get(sample_ticket.id)
    assert stored.validation_score == 0.75
    assert stored.validation_notes == MOCK_PASS["validation_notes"]


def test_validator_missing_ticket_raises(tmp_data_dir):
    store = make_store(tmp_data_dir)
    with pytest.raises(ValueError, match="not found"):
        run_validator("bad-id", store)
