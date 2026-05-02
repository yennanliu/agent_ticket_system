import pytest
import tempfile
import os
from datetime import datetime, timezone

from app.models import Ticket


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
    """Provides a temporary directory for JSON persistence tests."""
    return tmp_path


@pytest.fixture
def repo_context():
    return {
        "name": "linkedin-skill",
        "file_tree": ["README.md", "skills/linkedin-job-auto-apply/autoApplyLinkedInJobs.js"],
        "readme": "# LinkedIn Skill\nAutomate LinkedIn interactions.",
        "file_contents": "// autoApplyLinkedInJobs.js\nconst jobs = [];\n",
    }
