import os
import threading
import time
from unittest.mock import patch, MagicMock

from app.indexer import IndexService, _chunk_repo, _cosine, _fingerprint


# --- unit tests ---

def test_cosine_identical():
    v = [1.0, 0.0, 0.0]
    assert abs(_cosine(v, v) - 1.0) < 1e-9


def test_cosine_orthogonal():
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_zero_vector():
    assert _cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_fingerprint_changes_on_file_edit(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("v1")
    fp1 = _fingerprint(str(tmp_path))
    time.sleep(0.01)
    f.write_text("v2")
    os.utime(f, (time.time() + 1, time.time() + 1))  # force mtime bump
    fp2 = _fingerprint(str(tmp_path))
    assert fp1 != fp2


def test_chunk_repo_splits_large_file(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_CHUNK_SIZE", "1")  # 1 token → 4 chars per chunk
    # Re-evaluate the constant inside the module for this test
    import app.indexer as idx_mod
    original = idx_mod._CHUNK_CHARS
    idx_mod._CHUNK_CHARS = 4

    (tmp_path / "big.py").write_text("abcdefgh")  # 8 chars → 2 chunks of 4
    chunks = _chunk_repo(str(tmp_path))
    idx_mod._CHUNK_CHARS = original

    assert len(chunks) == 2
    assert "### big.py" in chunks[0]


def test_chunk_repo_skips_non_source(tmp_path):
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    chunks = _chunk_repo(str(tmp_path))
    assert chunks == []


def test_chunk_repo_skips_skip_dirs(tmp_path):
    node = tmp_path / "node_modules"
    node.mkdir()
    (node / "lib.js").write_text("module.exports = {}")
    chunks = _chunk_repo(str(tmp_path))
    assert chunks == []


# --- IndexService tests ---

def _fake_embed(texts):
    # Returns a unique embedding per text (simple hash-based stub)
    return [[float(hash(t) % 1000) / 1000, 0.5] for t in texts]


def test_get_returns_none_before_index(tmp_path):
    svc = IndexService()
    assert svc.get(str(tmp_path)) is None


def test_submit_and_get_after_build(tmp_path):
    (tmp_path / "main.py").write_text("def main(): pass")
    svc = IndexService()

    with patch("app.indexer._embed", side_effect=_fake_embed):
        svc.submit(str(tmp_path))
        # Wait for background thread to finish
        svc._executor.shutdown(wait=True)

    entry = svc.get(str(tmp_path))
    assert entry is not None
    assert len(entry.chunks) >= 1


def test_submit_skips_if_already_in_progress(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    svc = IndexService()
    svc._in_progress.add(os.path.abspath(str(tmp_path)))

    with patch("app.indexer._embed", side_effect=_fake_embed) as mock_embed:
        svc.submit(str(tmp_path))
        svc._executor.shutdown(wait=True)

    mock_embed.assert_not_called()


def test_submit_skips_if_fingerprint_matches(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    svc = IndexService()
    abs_src = os.path.abspath(str(tmp_path))
    svc._fingerprints[abs_src] = _fingerprint(abs_src)  # pretend already indexed

    with patch("app.indexer._embed", side_effect=_fake_embed) as mock_embed:
        svc.submit(str(tmp_path))
        svc._executor.shutdown(wait=True)

    mock_embed.assert_not_called()


def test_retrieve_returns_none_when_not_indexed(tmp_path):
    svc = IndexService()
    with patch("app.indexer._embed", side_effect=_fake_embed):
        result = svc.retrieve(str(tmp_path), "some query")
    assert result is None


def test_retrieve_returns_chunks_when_indexed(tmp_path):
    (tmp_path / "utils.py").write_text("def helper(): return 42")
    svc = IndexService()

    with patch("app.indexer._embed", side_effect=_fake_embed):
        svc.submit(str(tmp_path))
        svc._executor.shutdown(wait=True)
        result = svc.retrieve(str(tmp_path), "helper function", k=1)

    assert result is not None
    assert len(result) == 1
    assert "utils.py" in result[0]


def test_empty_repo_does_not_cache(tmp_path):
    svc = IndexService()
    with patch("app.indexer._embed", side_effect=_fake_embed):
        svc.submit(str(tmp_path))
        svc._executor.shutdown(wait=True)
    assert svc.get(str(tmp_path)) is None


# --- enricher integration ---

def test_enricher_uses_rag_when_enabled(tmp_data_dir, sample_ticket, repo_context):
    from app.storage import TicketStore
    from app.agents.enricher import run_enricher

    store = TicketStore(data_dir=str(tmp_data_dir))
    store.create(sample_ticket)

    mock_chunks = ["### app/main.py\ndef run(): pass"]
    mock_enrichment = {
        "acceptance_criteria": ["done"],
        "related_files": ["app/main.py"],
        "technical_notes": "use RAG",
        "suggested_assignee": "backend",
    }

    with patch.dict(os.environ, {"RAG_ENABLED": "true"}), \
         patch("app.agents.enricher.read_repo", return_value=repo_context) as mock_read, \
         patch("app.agents.enricher.indexer.retrieve", return_value=mock_chunks) as mock_retrieve, \
         patch("app.agents.enricher._llm_enrich_ticket", return_value=mock_enrichment), \
         patch("app.agents.enricher.find_refs", return_value=[]):
        run_enricher(sample_ticket.id, "../local-repo", store)

    mock_retrieve.assert_called_once()
    # file_contents should have been replaced with chunks
    call_args = mock_read.return_value
    assert call_args["file_contents"] == mock_chunks[0]


def test_enricher_falls_back_when_rag_not_ready(tmp_data_dir, sample_ticket, repo_context):
    from app.storage import TicketStore
    from app.agents.enricher import run_enricher

    store = TicketStore(data_dir=str(tmp_data_dir))
    store.create(sample_ticket)

    mock_enrichment = {
        "acceptance_criteria": ["done"],
        "related_files": [],
        "technical_notes": "fallback",
        "suggested_assignee": "",
    }

    with patch.dict(os.environ, {"RAG_ENABLED": "true"}), \
         patch("app.agents.enricher.read_repo", return_value=repo_context), \
         patch("app.agents.enricher.indexer.retrieve", return_value=None), \
         patch("app.agents.enricher.indexer.submit") as mock_submit, \
         patch("app.agents.enricher._llm_enrich_ticket", return_value=mock_enrichment), \
         patch("app.agents.enricher.find_refs", return_value=[]):
        run_enricher(sample_ticket.id, "../local-repo", store)

    # Should have triggered background indexing
    mock_submit.assert_called_once_with("../local-repo")


def test_enricher_skips_rag_for_github_source(tmp_data_dir, sample_ticket, repo_context):
    from app.storage import TicketStore
    from app.agents.enricher import run_enricher

    store = TicketStore(data_dir=str(tmp_data_dir))
    store.create(sample_ticket)

    mock_enrichment = {
        "acceptance_criteria": [],
        "related_files": [],
        "technical_notes": "",
        "suggested_assignee": "",
    }

    with patch.dict(os.environ, {"RAG_ENABLED": "true"}), \
         patch("app.agents.enricher.read_repo", return_value=repo_context), \
         patch("app.agents.enricher.indexer.retrieve") as mock_retrieve, \
         patch("app.agents.enricher._llm_enrich_ticket", return_value=mock_enrichment), \
         patch("app.agents.enricher.find_refs", return_value=[]):
        run_enricher(sample_ticket.id, "https://github.com/owner/repo", store)

    mock_retrieve.assert_not_called()
