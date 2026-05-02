import json
import os
from datetime import datetime, timezone
from typing import Optional

from app.models import Ticket

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


class TicketStore:
    def __init__(self, data_dir: str = _DEFAULT_DATA_DIR):
        self._path = os.path.join(data_dir, "tickets.json")
        os.makedirs(data_dir, exist_ok=True)
        self._tickets: dict[str, Ticket] = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            with open(self._path) as f:
                data = json.load(f)
            self._tickets = {t["id"]: Ticket(**t) for t in data}

    def _save(self):
        with open(self._path, "w") as f:
            json.dump([t.model_dump(mode="json") for t in self._tickets.values()], f, indent=2)

    def get_all(self) -> list[Ticket]:
        return list(self._tickets.values())

    def get(self, ticket_id: str) -> Optional[Ticket]:
        return self._tickets.get(ticket_id)

    def create(self, ticket: Ticket) -> Ticket:
        self._tickets[ticket.id] = ticket
        self._save()
        return ticket

    def update(self, ticket_id: str, fields: dict) -> Optional[Ticket]:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            return None
        updated = ticket.model_copy(
            update={**fields, "updated_at": datetime.now(timezone.utc)}
        )
        self._tickets[ticket_id] = updated
        self._save()
        return updated

    def delete(self, ticket_id: str) -> bool:
        if ticket_id not in self._tickets:
            return False
        del self._tickets[ticket_id]
        self._save()
        return True


# Singleton used by the FastAPI app
_store: Optional[TicketStore] = None


def get_store() -> TicketStore:
    global _store
    if _store is None:
        _store = TicketStore()
    return _store
