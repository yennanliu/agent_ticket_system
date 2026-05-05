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
    importance: str = "medium"  # low | medium | high | critical
    labels: list[str] = Field(default_factory=list)
    source_repo: str = ""
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    # Content fields
    business_req: str = ""
    stakeholder: str = ""
    user_story: str = ""
    # Populated by enricher agent
    acceptance_criteria: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    technical_notes: str = ""
    suggested_assignee: str = ""
    suggested_change_refs: list[dict] = Field(default_factory=list)
    # Populated by validator agent
    validation_score: Optional[float] = None
    validation_notes: str = ""
    validation_passed: Optional[bool] = None
    validation_iterations: int = 0   # heal loop cycle count


class CreateTicketRequest(BaseModel):
    title: str
    description: str = ""
    status: str = "open"
    priority: str = "medium"
    importance: str = "medium"
    labels: list[str] = Field(default_factory=list)
    source_repo: str = ""
    business_req: str = ""
    stakeholder: str = ""
    user_story: str = ""


class UpdateTicketRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    importance: Optional[str] = None
    labels: Optional[list[str]] = None
    source_repo: Optional[str] = None
    business_req: Optional[str] = None
    stakeholder: Optional[str] = None
    user_story: Optional[str] = None
    acceptance_criteria: Optional[list[str]] = None
    related_files: Optional[list[str]] = None
    technical_notes: Optional[str] = None
    suggested_assignee: Optional[str] = None
    suggested_change_refs: Optional[list[dict]] = None
    validation_score: Optional[float] = None
    validation_notes: Optional[str] = None
    validation_passed: Optional[bool] = None
    validation_iterations: Optional[int] = None


class RepoRequest(BaseModel):
    repo_path: Optional[str] = None
    repo_url: Optional[str] = None
