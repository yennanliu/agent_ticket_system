from datetime import datetime, timezone
from typing import Optional
import uuid
from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Ticket(BaseModel):
    id: str = Field(default_factory=_uuid)
    title: str
    description: str
    status: str = "open"        # open | in_progress | done
    priority: str = "medium"    # low | medium | high
    labels: list[str] = Field(default_factory=list)
    source_repo: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    # Populated by enricher agent
    acceptance_criteria: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    technical_notes: str = ""
    suggested_assignee: str = ""


class CreateTicketRequest(BaseModel):
    title: str
    description: str = ""
    status: str = "open"
    priority: str = "medium"
    labels: list[str] = Field(default_factory=list)
    source_repo: str = ""


class UpdateTicketRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    labels: Optional[list[str]] = None
    source_repo: Optional[str] = None
    acceptance_criteria: Optional[list[str]] = None
    related_files: Optional[list[str]] = None
    technical_notes: Optional[str] = None
    suggested_assignee: Optional[str] = None


class RepoRequest(BaseModel):
    repo_path: Optional[str] = None
    repo_url: Optional[str] = None
