from unittest.mock import patch
from app.search_tools import classify_file, find_refs, _github_blob_url


def test_classify_code_files():
    assert classify_file("app/main.py") == "code"
    assert classify_file("src/index.js") == "code"
    assert classify_file("pkg/handler.go") == "code"


def test_classify_doc_files():
    assert classify_file("README.md") == "doc"
    assert classify_file("docs/guide.rst") == "doc"


def test_classify_design_by_path():
    assert classify_file("design/wireframe.png") == "design"
    assert classify_file("arch/diagram.pdf") == "design"


def test_classify_unknown_falls_back_to_doc():
    assert classify_file("somefile.xyz") == "doc"


def test_github_blob_url_constructs_correctly():
    url = _github_blob_url("https://github.com/owner/myrepo", "app/main.py")
    assert url == "https://github.com/owner/myrepo/blob/main/app/main.py"


def test_github_blob_url_strips_git_suffix():
    url = _github_blob_url("https://github.com/owner/myrepo.git", "app/main.py")
    assert url == "https://github.com/owner/myrepo/blob/main/app/main.py"


def test_github_blob_url_returns_none_for_local():
    assert _github_blob_url("../local-repo", "app/main.py") is None


def test_find_refs_github_constructs_urls():
    refs = find_refs(
        related_files=["app/main.py", "README.md"],
        source="https://github.com/owner/myrepo",
        repo_name="myrepo",
    )
    assert len(refs) == 2
    assert refs[0]["ref_url"] == "https://github.com/owner/myrepo/blob/main/app/main.py"
    assert refs[0]["ref_type"] == "code"
    assert refs[1]["ref_type"] == "doc"


def test_find_refs_local_uses_ddg():
    mock_results = [{"title": "Some Docs", "href": "https://example.com", "body": "..."}]
    with patch("app.search_tools._ddg_search", return_value=mock_results):
        refs = find_refs(["app/main.py"], source="../local-repo", repo_name="local-repo")
    assert len(refs) == 1
    assert refs[0]["ref_url"] == "https://example.com"
    assert refs[0]["title"] == "Some Docs"


def test_find_refs_ddg_no_results_returns_empty():
    with patch("app.search_tools._ddg_search", return_value=[]):
        refs = find_refs(["app/main.py"], source="../local-repo", repo_name="local-repo")
    assert refs == []


def test_find_refs_exception_does_not_crash():
    with patch("app.search_tools._ddg_search", side_effect=RuntimeError("network error")):
        refs = find_refs(["app/main.py"], source="../local-repo", repo_name="local-repo")
    assert refs == []


def test_find_refs_empty_list():
    refs = find_refs([], source="https://github.com/owner/repo", repo_name="repo")
    assert refs == []
