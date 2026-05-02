import pytest
from datetime import datetime, timezone

from app.models import Ticket
from app.storage import TicketStore
from app.logger import AgentLogger


@pytest.fixture
def sample_ticket():
    return Ticket(
        title="Fix login bug",
        description="Users cannot log in with Google SSO",
        status="open",
        priority="high",
        labels=["bug", "auth"],
        source_repo="../linkedin-skill",
    )


@pytest.fixture
def sample_ticket_dict():
    return {
        "title": "Fix login bug",
        "description": "Users cannot log in with Google SSO",
        "status": "open",
        "priority": "high",
        "labels": ["bug", "auth"],
        "source_repo": "../linkedin-skill",
    }


@pytest.fixture
def tmp_data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def repo_context():
    return {
        "name": "linkedin-skill",
        "file_tree": ["README.md", "skills/linkedin-job-auto-apply/autoApplyLinkedInJobs.js"],
        "readme": "# LinkedIn Skill\nAutomate LinkedIn interactions.",
        "file_contents": "// autoApplyLinkedInJobs.js\nconst jobs = [];\n",
    }


@pytest.fixture
def store(tmp_data_dir):
    return TicketStore(data_dir=str(tmp_data_dir))


@pytest.fixture
def logger(tmp_path):
    return AgentLogger(log_path=str(tmp_path / "test_logs.jsonl"))


@pytest.fixture
def app_with_store(store, logger):
    from main import create_app
    return create_app(store, logger=logger)
