import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from app.models import Ticket

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_JSON_LIST_FIELDS = {"labels", "acceptance_criteria", "related_files", "suggested_change_refs"}
_DATETIME_FIELDS = {"created_at", "updated_at"}

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium',
    importance TEXT NOT NULL DEFAULT 'medium',
    labels TEXT NOT NULL DEFAULT '[]',
    source_repo TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    business_req TEXT NOT NULL DEFAULT '',
    stakeholder TEXT NOT NULL DEFAULT '',
    user_story TEXT NOT NULL DEFAULT '',
    acceptance_criteria TEXT NOT NULL DEFAULT '[]',
    related_files TEXT NOT NULL DEFAULT '[]',
    technical_notes TEXT NOT NULL DEFAULT '',
    suggested_assignee TEXT NOT NULL DEFAULT '',
    suggested_change_refs TEXT NOT NULL DEFAULT '[]',
    ticket_type TEXT NOT NULL DEFAULT 'task',
    parent_id TEXT,
    validation_score REAL,
    validation_notes TEXT NOT NULL DEFAULT '',
    validation_passed INTEGER,
    validation_iterations INTEGER NOT NULL DEFAULT 0
)
"""


def _row_to_ticket(row: sqlite3.Row) -> Ticket:
    data = dict(row)
    for field in _JSON_LIST_FIELDS:
        if field in data and data[field] is not None:
            data[field] = json.loads(data[field])
    if data.get("validation_passed") is not None:
        data["validation_passed"] = bool(data["validation_passed"])
    return Ticket(**data)


def _ticket_to_row(ticket: Ticket) -> dict:
    d = ticket.model_dump(mode="json")
    for field in _JSON_LIST_FIELDS:
        d[field] = json.dumps(d[field])
    for field in _DATETIME_FIELDS:
        if isinstance(d[field], datetime):
            d[field] = d[field].isoformat()
    if d.get("validation_passed") is not None:
        d["validation_passed"] = int(d["validation_passed"])
    return d


class TicketStore:
    def __init__(self, data_dir: str = _DEFAULT_DATA_DIR):
        os.makedirs(data_dir, exist_ok=True)
        self._db_path = os.path.join(data_dir, "tickets.db")
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE)
        self._conn.commit()

    def get_all(self) -> list[Ticket]:
        rows = self._conn.execute("SELECT * FROM tickets").fetchall()
        return [_row_to_ticket(r) for r in rows]

    def get(self, ticket_id: str) -> Optional[Ticket]:
        row = self._conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
        return _row_to_ticket(row) if row else None

    def create(self, ticket: Ticket) -> Ticket:
        d = _ticket_to_row(ticket)
        cols = ", ".join(d.keys())
        placeholders = ", ".join("?" * len(d))
        self._conn.execute(
            f"INSERT INTO tickets ({cols}) VALUES ({placeholders})", list(d.values())
        )
        self._conn.commit()
        return ticket

    def update(self, ticket_id: str, fields: dict) -> Optional[Ticket]:
        ticket = self.get(ticket_id)
        if ticket is None:
            return None
        updated = ticket.model_copy(
            update={**fields, "updated_at": datetime.now(timezone.utc)}
        )
        d = _ticket_to_row(updated)
        set_clause = ", ".join(f"{k} = ?" for k in d if k != "id")
        values = [v for k, v in d.items() if k != "id"] + [ticket_id]
        self._conn.execute(f"UPDATE tickets SET {set_clause} WHERE id = ?", values)
        self._conn.commit()
        return updated

    def delete(self, ticket_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        self._conn.commit()
        return cur.rowcount > 0


# Singleton used by the FastAPI app
_store: Optional[TicketStore] = None


def get_store() -> TicketStore:
    global _store
    if _store is None:
        _store = TicketStore()
    return _store
