from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator
from typing import Optional

from app.models import Ticket
from app.storage import TicketStore
from app.agents.creator import run_creator
from app.agents.enricher import run_enricher
from app.agents.validator import run_validator


class RepoSource(BaseModel):
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


class EnrichBatchRequest(RepoSource):
    ticket_ids: Optional[list[str]] = None


class CreateBatchRequest(BaseModel):
    titles: list[str]
    repo_path: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_title(self):
        if not self.titles:
            raise ValueError("Provide at least one title")
        return self


def make_router(store: TicketStore, logger=None) -> APIRouter:
    r = APIRouter(prefix="/api/agents", tags=["agents"])

    @r.post("/create-from-repo", response_model=list[Ticket])
    def create_from_repo(body: RepoSource):
        return run_creator(body.source, store, logger=logger)

    @r.post("/create-batch", response_model=list[Ticket], status_code=201)
    def create_batch(body: CreateBatchRequest):
        tickets = []
        for title in body.titles:
            t = Ticket(title=title.strip(), description="",
                       source_repo=body.repo_path or "")
            store.create(t)
            tickets.append(t)
        if logger:
            logger.log("create_batch", "api", duration_ms=0,
                       details=f"created {len(tickets)} tickets manually")
        return tickets

    @r.post("/enrich/{ticket_id}", response_model=Ticket)
    def enrich_ticket(ticket_id: str, body: RepoSource):
        try:
            return run_enricher(ticket_id, body.source, store, logger=logger)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @r.post("/enrich-batch", response_model=list[Ticket])
    def enrich_batch(body: EnrichBatchRequest):
        ids = body.ticket_ids or [t.id for t in store.get_all()]
        results = []
        for ticket_id in ids:
            try:
                results.append(run_enricher(ticket_id, body.source, store, logger=logger))
            except ValueError:
                pass
        return results

    @r.post("/validate/{ticket_id}", response_model=Ticket)
    def validate_ticket(ticket_id: str):
        try:
            return run_validator(ticket_id, store, logger=logger)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return r
