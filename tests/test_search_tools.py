import os
import pytest
from app.search_tools import (
    classify_file,
    find_refs,
    _github_blob_url,
    _path_similarity,
    _local_ref,
)


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


def test_find_refs_empty_list():
    refs = find_refs([], source="https://github.com/owner/repo", repo_name="repo")
    assert refs == []


# --- local repo tests ---

def test_path_similarity_exact():
    assert _path_similarity("app/main.py", "app/main.py") == 1.0


def test_path_similarity_partial():
    score = _path_similarity("app/main.py", "app/utils.py")
    assert 0.0 < score < 1.0


def test_path_similarity_disjoint():
    assert _path_similarity("foo/bar.py", "baz/qux.js") == 0.0


def test_local_ref_exact_match(tmp_path):
    (tmp_path / "app").mkdir()
    target = tmp_path / "app" / "main.py"
    target.write_text("print('hello')")

    ref = _local_ref("app/main.py", str(tmp_path), "code")
    assert ref is not None
    assert ref["file"] == "app/main.py"
    assert ref["ref_url"] == f"file://{target}"
    assert "print" in ref["snippet"]
    assert ref["ref_type"] == "code"


def test_local_ref_fuzzy_match(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# main")

    # Query references a path that doesn't exist exactly
    ref = _local_ref("app/main.py", str(tmp_path), "code")
    assert ref is not None
    assert ref["file"] == os.path.join("src", "main.py")


def test_local_ref_no_match_returns_none(tmp_path):
    (tmp_path / "unrelated.rb").write_text("# rb")
    ref = _local_ref("completely_different_xyz.py", str(tmp_path), "code")
    # Jaccard is 0 → returns None
    assert ref is None


def test_find_refs_local_resolves_real_file(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("def run(): pass")

    refs = find_refs(["app/main.py"], source=str(tmp_path), repo_name="local-repo")
    assert len(refs) == 1
    assert refs[0]["ref_url"].startswith("file://")
    assert refs[0]["title"] == "app/main.py"
    assert "def run" in refs[0]["snippet"]


def test_find_refs_local_no_match_skips(tmp_path):
    (tmp_path / "unrelated.rb").write_text("# rb")
    refs = find_refs(["xyz_nonexistent.py"], source=str(tmp_path), repo_name="local-repo")
    assert refs == []


def test_find_refs_local_exception_does_not_crash(tmp_path):
    # Pass a non-existent source dir — _walk_file_tree returns [] → _local_ref returns None
    refs = find_refs(["app/main.py"], source=str(tmp_path / "ghost"), repo_name="repo")
    assert refs == []
