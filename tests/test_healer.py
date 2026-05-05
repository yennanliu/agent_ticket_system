import pytest
from unittest.mock import patch, call
from app.storage import TicketStore
from app.models import Ticket
from app.agents.healer import run_healer, HEAL_THRESHOLD, HEAL_MAX_ITERATIONS


PASS_TICKET = Ticket(
    title="T", description="D", source_repo="../repo",
    validation_score=0.85, validation_passed=True, validation_notes="Looks good.",
)
FAIL_TICKET = Ticket(
    title="T", description="D", source_repo="../repo",
    validation_score=0.40, validation_passed=False, validation_notes="ACs are vague.",
)


def make_store(tmp_data_dir):
    return TicketStore(data_dir=str(tmp_data_dir))


def test_healer_stops_when_first_validate_passes(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    with patch("app.agents.healer.run_validator", return_value=PASS_TICKET), \
         patch("app.agents.healer.run_enricher") as mock_enrich:
        result = run_healer(sample_ticket.id, store)
    mock_enrich.assert_not_called()
    assert result.validation_score == 0.85


def test_healer_enriches_and_revalidates_on_low_score(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={"acceptance_criteria": ["AC1"]})
    with patch("app.agents.healer.run_validator", side_effect=[FAIL_TICKET, PASS_TICKET]), \
         patch("app.agents.healer.run_enricher", return_value=enriched):
        result = run_healer(sample_ticket.id, store)
    assert result.validation_score == 0.85
    stored = store.get(sample_ticket.id)
    assert stored.validation_iterations == 1


def test_healer_passes_feedback_to_enricher(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={"acceptance_criteria": ["AC1"]})
    with patch("app.agents.healer.run_validator", side_effect=[FAIL_TICKET, PASS_TICKET]), \
         patch("app.agents.healer.run_enricher", return_value=enriched) as mock_enrich:
        run_healer(sample_ticket.id, store)
    _, kwargs = mock_enrich.call_args
    assert kwargs.get("feedback") == FAIL_TICKET.validation_notes


def test_healer_caps_at_max_iterations(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={"acceptance_criteria": ["AC"]})
    with patch("app.agents.healer.run_validator", return_value=FAIL_TICKET), \
         patch("app.agents.healer.run_enricher", return_value=enriched) as mock_enrich:
        run_healer(sample_ticket.id, store)
    assert mock_enrich.call_count == HEAL_MAX_ITERATIONS
    assert store.get(sample_ticket.id).validation_iterations == HEAL_MAX_ITERATIONS


def test_healer_skips_enrich_when_no_source_repo(tmp_data_dir):
    store = make_store(tmp_data_dir)
    t = Ticket(title="No source", description="D", source_repo="")
    store.create(t)
    fail_no_source = t.model_copy(update={"validation_score": 0.3, "validation_passed": False, "validation_notes": "Bad"})
    with patch("app.agents.healer.run_validator", return_value=fail_no_source), \
         patch("app.agents.healer.run_enricher") as mock_enrich:
        result = run_healer(t.id, store)
    mock_enrich.assert_not_called()
    assert result.validation_score == 0.3


def test_healer_missing_ticket_raises(tmp_data_dir):
    store = make_store(tmp_data_dir)
    with pytest.raises(ValueError, match="not found"):
        run_healer("bad-id", store)


def test_healer_logs_success(tmp_data_dir, sample_ticket, logger):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    with patch("app.agents.healer.run_validator", return_value=PASS_TICKET), \
         patch("app.agents.healer.run_enricher"):
        run_healer(sample_ticket.id, store, logger=logger)
    entries = logger.read_all()
    assert any(e["event"] == "heal" for e in entries)
