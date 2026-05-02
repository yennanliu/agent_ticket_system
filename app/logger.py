import json
import os
from datetime import datetime, timezone
from typing import Optional

_DEFAULT_LOG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "agent_logs.jsonl"
)


class AgentLogger:
    def __init__(self, log_path: str = _DEFAULT_LOG_PATH):
        self._path = log_path
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        except Exception:
            pass

    def log(
        self,
        event: str,
        agent: str,
        ticket_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        status: str = "success",
        details: str = "",
    ) -> None:
        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "ticket_id": ticket_id or "",
                "agent": agent,
                "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
                "status": status,
                "details": details,
            }
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # logging must never crash agent execution

    def read_all(self) -> list[dict]:
        try:
            if not os.path.exists(self._path):
                return []
            entries = []
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            return entries
        except Exception:
            return []

    def clear(self) -> None:
        try:
            if os.path.exists(self._path):
                open(self._path, "w").close()
        except Exception:
            pass


_logger: Optional["AgentLogger"] = None


def get_logger() -> "AgentLogger":
    global _logger
    if _logger is None:
        _logger = AgentLogger()
    return _logger
