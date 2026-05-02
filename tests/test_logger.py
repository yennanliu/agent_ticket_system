import json
import os
import pytest
from app.logger import AgentLogger


def test_log_creates_file(tmp_path):
    log_path = str(tmp_path / "test.jsonl")
    logger = AgentLogger(log_path=log_path)
    logger.log("enrich", "enricher", ticket_id="abc-123", status="success")
    assert os.path.exists(log_path)


def test_log_writes_valid_jsonl(tmp_path):
    log_path = str(tmp_path / "test.jsonl")
    logger = AgentLogger(log_path=log_path)
    logger.log("enrich", "enricher", ticket_id="abc-123", duration_ms=1234.5, status="success", details="done")
    with open(log_path) as f:
        entry = json.loads(f.read().strip())
    assert entry["event"] == "enrich"
    assert entry["agent"] == "enricher"
    assert entry["ticket_id"] == "abc-123"
    assert entry["duration_ms"] == 1234.5
    assert entry["status"] == "success"
    assert entry["details"] == "done"
    assert "timestamp" in entry


def test_log_appends_multiple_entries(tmp_path):
    log_path = str(tmp_path / "test.jsonl")
    logger = AgentLogger(log_path=log_path)
    logger.log("enrich", "enricher", ticket_id="t1")
    logger.log("create", "creator", ticket_id="t2")
    entries = logger.read_all()
    assert len(entries) == 2
    assert entries[0]["event"] == "enrich"
    assert entries[1]["event"] == "create"


def test_read_all_returns_empty_if_no_file(tmp_path):
    log_path = str(tmp_path / "nonexistent.jsonl")
    logger = AgentLogger(log_path=log_path)
    assert logger.read_all() == []


def test_log_does_not_raise_on_bad_path():
    logger = AgentLogger(log_path="/nonexistent_dir_xyz/logs.jsonl")
    logger.log("enrich", "enricher")  # must not raise


def test_read_all_skips_corrupt_lines(tmp_path):
    log_path = str(tmp_path / "test.jsonl")
    with open(log_path, "w") as f:
        f.write('{"valid": true}\n')
        f.write('not valid json\n')
        f.write('{"also_valid": true}\n')
    logger = AgentLogger(log_path=log_path)
    entries = logger.read_all()
    assert len(entries) == 2


def test_clear_empties_log(tmp_path):
    log_path = str(tmp_path / "test.jsonl")
    logger = AgentLogger(log_path=log_path)
    logger.log("enrich", "enricher")
    logger.log("create", "creator")
    logger.clear()
    assert logger.read_all() == []
