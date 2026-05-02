import pytest
from unittest.mock import patch, MagicMock
from app.storage import TicketStore
from app.agents.creator import run_creator


MOCK_DRAFTS = [
    {"title": "Add job filter", "description": "Filter by seniority", "priority": "high", "labels": ["feature"]},
    {"title": "Fix retry logic", "description": "Retry on 429", "priority": "medium", "labels": ["bug"]},
]


def make_store(tmp_data_dir):
    return TicketStore(data_dir=str(tmp_data_dir))


def test_creator_returns_ticket_list(tmp_data_dir, repo_context):
    store = make_store(tmp_data_dir)
    with patch("app.agents.creator.read_repo", return_value=repo_context), \
         patch("app.agents.creator._llm_generate_tickets", return_value=MOCK_DRAFTS):
        tickets = run_creator("../linkedin-skill", store)
    assert len(tickets) == 2
    assert tickets[0].title == "Add job filter"
    assert tickets[1].priority == "medium"


def test_creator_saves_to_store(tmp_data_dir, repo_context):
    store = make_store(tmp_data_dir)
    with patch("app.agents.creator.read_repo", return_value=repo_context), \
         patch("app.agents.creator._llm_generate_tickets", return_value=MOCK_DRAFTS):
        tickets = run_creator("../linkedin-skill", store)
    for t in tickets:
        assert store.get(t.id) is not None


def test_creator_sets_source_repo(tmp_data_dir, repo_context):
    store = make_store(tmp_data_dir)
    with patch("app.agents.creator.read_repo", return_value=repo_context), \
         patch("app.agents.creator._llm_generate_tickets", return_value=MOCK_DRAFTS):
        tickets = run_creator("../linkedin-skill", store)
    assert all(t.source_repo == "../linkedin-skill" for t in tickets)


def test_creator_tickets_have_valid_ids(tmp_data_dir, repo_context):
    store = make_store(tmp_data_dir)
    with patch("app.agents.creator.read_repo", return_value=repo_context), \
         patch("app.agents.creator._llm_generate_tickets", return_value=MOCK_DRAFTS):
        tickets = run_creator("../linkedin-skill", store)
    for t in tickets:
        assert len(t.id) == 36
