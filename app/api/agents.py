from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator
from typing import Optional

from app.models import Ticket, RepoRequest
from app.storage import TicketStore
from app.agents.creator import run_creator
from app.agents.enricher import run_enricher


class CreateFromRepoRequest(BaseModel):
    repo_path: Optional[str] = None
    repo_url: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_source(self):
        if not self.repo_path and not self.repo_url:
            raise ValueError("Provide either repo_path or repo_url")
        return self

    @property
    def source(self) -> str:
        return self.repo_url if self.repo_url else self.repo_path


class EnrichRequest(BaseModel):
    repo_path: Optional[str] = None
    repo_url: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_source(self):
        if not self.repo_path and not self.repo_url:
            raise ValueError("Provide either repo_path or repo_url")
        return self

    @property
    def source(self) -> str:
        return self.repo_url if self.repo_url else self.repo_path


def make_router(store: TicketStore) -> APIRouter:
    r = APIRouter(prefix="/api/agents", tags=["agents"])

    @r.post("/create-from-repo", response_model=list[Ticket])
    def create_from_repo(body: CreateFromRepoRequest):
        tickets = run_creator(body.source, store)
        return tickets

    @r.post("/enrich/{ticket_id}", response_model=Ticket)
    def enrich_ticket(ticket_id: str, body: EnrichRequest):
        try:
            ticket = run_enricher(ticket_id, body.source, store)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return ticket

    return r
