import pytest
from unittest.mock import patch
from app.storage import TicketStore
from app.models import Ticket
from app.agents.kickstart import run_kickstart, KICKSTART_THRESHOLD, KICKSTART_MAX_RETRIES

PASS_TICKET = Ticket(
    title="T", description="D", source_repo="../repo",
    validation_score=0.75, validation_passed=True, validation_notes="Good.",
)
FAIL_TICKET = Ticket(
    title="T", description="D", source_repo="../repo",
    validation_score=0.40, validation_passed=False, validation_notes="ACs too vague.",
)


def make_store(tmp_data_dir):
    return TicketStore(data_dir=str(tmp_data_dir))


def test_kickstart_enriches_then_validates(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={"acceptance_criteria": ["AC1"]})
    with patch("app.agents.kickstart.run_enricher", return_value=enriched) as mock_enrich, \
         patch("app.agents.kickstart.run_validator", return_value=PASS_TICKET):
        result = run_kickstart(sample_ticket.id, store)
    mock_enrich.assert_called_once()
    assert result.validation_score == 0.75


def test_kickstart_skips_enrich_without_source_repo(tmp_data_dir):
    store = make_store(tmp_data_dir)
    t = Ticket(title="No source", description="D", source_repo="")
    store.create(t)
    no_source_pass = t.model_copy(update={"validation_score": 0.75, "validation_passed": True})
    with patch("app.agents.kickstart.run_enricher") as mock_enrich, \
         patch("app.agents.kickstart.run_validator", return_value=no_source_pass):
        run_kickstart(t.id, store)
    mock_enrich.assert_not_called()


def test_kickstart_retries_when_score_below_threshold(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={"acceptance_criteria": ["AC1"]})
    with patch("app.agents.kickstart.run_enricher", return_value=enriched), \
         patch("app.agents.kickstart.run_validator", side_effect=[FAIL_TICKET, PASS_TICKET]):
        result = run_kickstart(sample_ticket.id, store)
    assert result.validation_score == 0.75
    assert store.get(sample_ticket.id).validation_iterations == 1


def test_kickstart_passes_validation_notes_as_feedback(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={"acceptance_criteria": ["AC1"]})
    with patch("app.agents.kickstart.run_enricher", return_value=enriched) as mock_enrich, \
         patch("app.agents.kickstart.run_validator", side_effect=[FAIL_TICKET, PASS_TICKET]):
        run_kickstart(sample_ticket.id, store)
    # Second enrich call (the retry) should receive the validation notes as feedback
    retry_call = mock_enrich.call_args_list[1]
    assert retry_call.kwargs.get("feedback") == FAIL_TICKET.validation_notes


def test_kickstart_caps_at_max_retries(tmp_data_dir, sample_ticket):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={"acceptance_criteria": ["AC"]})
    with patch("app.agents.kickstart.run_enricher", return_value=enriched) as mock_enrich, \
         patch("app.agents.kickstart.run_validator", return_value=FAIL_TICKET):
        run_kickstart(sample_ticket.id, store)
    # 1 initial enrich + KICKSTART_MAX_RETRIES re-enriches
    assert mock_enrich.call_count == 1 + KICKSTART_MAX_RETRIES
    assert store.get(sample_ticket.id).validation_iterations == KICKSTART_MAX_RETRIES


def test_kickstart_no_retry_when_no_source_repo(tmp_data_dir):
    store = make_store(tmp_data_dir)
    t = Ticket(title="No source", description="D", source_repo="")
    store.create(t)
    fail_no_source = t.model_copy(update={"validation_score": 0.3, "validation_passed": False})
    with patch("app.agents.kickstart.run_enricher") as mock_enrich, \
         patch("app.agents.kickstart.run_validator", return_value=fail_no_source):
        run_kickstart(t.id, store)
    # Enricher never called — no source, so no enrich on initial or retries
    mock_enrich.assert_not_called()


def test_kickstart_missing_ticket_raises(tmp_data_dir):
    store = make_store(tmp_data_dir)
    with pytest.raises(ValueError, match="not found"):
        run_kickstart("bad-id", store)


def test_kickstart_logs_success(tmp_data_dir, sample_ticket, logger):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    enriched = sample_ticket.model_copy(update={"acceptance_criteria": ["AC"]})
    with patch("app.agents.kickstart.run_enricher", return_value=enriched), \
         patch("app.agents.kickstart.run_validator", return_value=PASS_TICKET):
        run_kickstart(sample_ticket.id, store, logger=logger)
    entries = logger.read_all()
    assert any(e["event"] == "kickstart" for e in entries)
