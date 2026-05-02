import pytest
from unittest.mock import patch
from app.storage import TicketStore
from app.models import Ticket
from app.agents.enricher import run_enricher


MOCK_ENRICHMENT = {
    "acceptance_criteria": ["User can filter by seniority", "Filter persists across sessions"],
    "related_files": ["skills/linkedin-job-auto-apply/autoApplyLinkedInJobs.js"],
    "technical_notes": "Use localStorage for persistence.",
    "suggested_assignee": "frontend-team",
}

MOCK_REFS = [{"file": "skills/linkedin-job-auto-apply/autoApplyLinkedInJobs.js",
              "ref_type": "code", "ref_url": "http://ex.com", "title": "autoApply"}]


def make_store(tmp_data_dir):
    return TicketStore(data_dir=str(tmp_data_dir))


def test_enricher_adds_enriched_fields(tmp_data_dir, sample_ticket, repo_context):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    with patch("app.agents.enricher.read_repo", return_value=repo_context), \
         patch("app.agents.enricher._llm_enrich_ticket", return_value=MOCK_ENRICHMENT), \
         patch("app.agents.enricher.find_refs", return_value=[]):
        enriched = run_enricher(sample_ticket.id, "../linkedin-skill", store)
    assert enriched.acceptance_criteria == MOCK_ENRICHMENT["acceptance_criteria"]
    assert enriched.technical_notes == MOCK_ENRICHMENT["technical_notes"]
    assert enriched.suggested_assignee == "frontend-team"


def test_enricher_persists_to_store(tmp_data_dir, sample_ticket, repo_context):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    with patch("app.agents.enricher.read_repo", return_value=repo_context), \
         patch("app.agents.enricher._llm_enrich_ticket", return_value=MOCK_ENRICHMENT), \
         patch("app.agents.enricher.find_refs", return_value=[]):
        run_enricher(sample_ticket.id, "../linkedin-skill", store)
    stored = store.get(sample_ticket.id)
    assert stored.technical_notes == MOCK_ENRICHMENT["technical_notes"]


def test_enricher_missing_ticket_raises(tmp_data_dir, repo_context):
    store = make_store(tmp_data_dir)
    with patch("app.agents.enricher.read_repo", return_value=repo_context), \
         patch("app.agents.enricher._llm_enrich_ticket", return_value=MOCK_ENRICHMENT), \
         patch("app.agents.enricher.find_refs", return_value=[]):
        with pytest.raises(ValueError, match="not found"):
            run_enricher("bad-id", "../linkedin-skill", store)


def test_enricher_calls_find_refs(tmp_data_dir, sample_ticket, repo_context):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    with patch("app.agents.enricher.read_repo", return_value=repo_context), \
         patch("app.agents.enricher._llm_enrich_ticket", return_value=MOCK_ENRICHMENT), \
         patch("app.agents.enricher.find_refs", return_value=[]) as mock_refs:
        run_enricher(sample_ticket.id, "../linkedin-skill", store)
    mock_refs.assert_called_once()


def test_enricher_stores_change_refs(tmp_data_dir, sample_ticket, repo_context):
    store = make_store(tmp_data_dir)
    store.create(sample_ticket)
    with patch("app.agents.enricher.read_repo", return_value=repo_context), \
         patch("app.agents.enricher._llm_enrich_ticket", return_value=MOCK_ENRICHMENT), \
         patch("app.agents.enricher.find_refs", return_value=MOCK_REFS):
        enriched = run_enricher(sample_ticket.id, "../linkedin-skill", store)
    assert enriched.suggested_change_refs == MOCK_REFS
