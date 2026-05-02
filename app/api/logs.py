from fastapi import APIRouter
from app.logger import AgentLogger


def make_router(logger: AgentLogger) -> APIRouter:
    r = APIRouter(prefix="/api/logs", tags=["logs"])

    @r.get("", response_model=list[dict])
    def get_logs():
        return logger.read_all()

    @r.delete("", status_code=204)
    def clear_logs():
        logger.clear()

    return r
