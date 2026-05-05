from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.storage import TicketStore, get_store
from app.logger import AgentLogger, get_logger
from app.api.tickets import make_router as make_tickets_router
from app.api.agents import make_router as make_agents_router
from app.api.logs import make_router as make_logs_router


def create_app(store: TicketStore | None = None, logger: AgentLogger | None = None) -> FastAPI:
    app = FastAPI(title="Agent Ticket System")

    if store is None:
        store = get_store()
    if logger is None:
        logger = get_logger()

    app.include_router(make_tickets_router(store))
    app.include_router(make_agents_router(store, logger))
    app.include_router(make_logs_router(logger))

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def landing():
        return FileResponse(os.path.join(static_dir, "landing.html"))

    @app.get("/tickets")
    def index():
        return FileResponse(os.path.join(static_dir, "index.html"))

    @app.get("/tickets/{ticket_id}")
    def ticket_page(ticket_id: str):
        return FileResponse(os.path.join(static_dir, "ticket.html"))

    @app.get("/logs")
    def logs_page():
        return FileResponse(os.path.join(static_dir, "logs.html"))

    return app


app = create_app()
