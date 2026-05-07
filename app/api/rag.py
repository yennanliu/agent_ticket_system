from fastapi import APIRouter
from pydantic import BaseModel

from app.indexer import indexer


class IndexRequest(BaseModel):
    source: str


def make_router() -> APIRouter:
    r = APIRouter(prefix="/api/rag", tags=["rag"])

    @r.get("/status")
    def rag_status():
        return indexer.status()

    @r.post("/index")
    def trigger_index(body: IndexRequest):
        indexer.submit(body.source)
        return {"queued": body.source}

    return r
