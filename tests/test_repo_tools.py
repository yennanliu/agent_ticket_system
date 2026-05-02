import os
import pytest
from unittest.mock import MagicMock, patch
from app.repo_tools import read_repo, _read_local, _read_github


# ── Local path tests ──────────────────────────────────────────────────────────

def test_read_local_returns_repo_context(tmp_path):
    (tmp_path / "README.md").write_text("# My Project\nDoes stuff.")
    (tmp_path / "main.py").write_text("print('hello')")
    ctx = _read_local(str(tmp_path))
    assert ctx["name"] == tmp_path.name
    assert "README.md" in ctx["file_tree"]
    assert "# My Project" in ctx["readme"]
    assert ctx["file_contents"]


def test_read_local_skips_excluded_dirs(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lodash.js").write_text("module.exports={}")
    (tmp_path / "README.md").write_text("# hi")
    ctx = _read_local(str(tmp_path))
    assert not any("node_modules" in f for f in ctx["file_tree"])


def test_read_local_caps_content_size(tmp_path):
    (tmp_path / "README.md").write_text("x" * 60_000)
    ctx = _read_local(str(tmp_path))
    assert len(ctx["file_contents"].encode()) <= 52_000  # ~50KB cap


def test_read_repo_detects_local_path(tmp_path):
    (tmp_path / "README.md").write_text("# Test")
    ctx = read_repo(str(tmp_path))
    assert ctx["name"] == tmp_path.name


def test_read_repo_detects_github_url():
    mock_ctx = {"name": "myrepo", "file_tree": [], "readme": "", "file_contents": ""}
    with patch("app.repo_tools._read_github", return_value=mock_ctx) as mock:
        ctx = read_repo("https://github.com/owner/myrepo")
        mock.assert_called_once_with("https://github.com/owner/myrepo")
        assert ctx["name"] == "myrepo"


# ── GitHub URL tests (mocked) ────────────────────────────────────────────────

def test_read_github_returns_repo_context():
    mock_repo = MagicMock()
    mock_repo.name = "linkedin-skill"
    mock_repo.description = "LinkedIn automation"

    mock_readme = MagicMock()
    mock_readme.decoded_content = b"# LinkedIn Skill\nAutomate LinkedIn."
    mock_repo.get_readme.return_value = mock_readme

    mock_file = MagicMock()
    mock_file.type = "file"
    mock_file.name = "README.md"
    mock_file.path = "README.md"
    mock_repo.get_contents.return_value = [mock_file]

    mock_issue = MagicMock()
    mock_issue.title = "Bug: login fails"
    mock_issue.number = 1
    mock_repo.get_issues.return_value = [mock_issue]

    with patch("app.repo_tools.Github") as MockGithub:
        MockGithub.return_value.get_repo.return_value = mock_repo
        ctx = _read_github("https://github.com/owner/linkedin-skill")

    assert ctx["name"] == "linkedin-skill"
    assert "LinkedIn Skill" in ctx["readme"]
    assert "README.md" in ctx["file_tree"]
