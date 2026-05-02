from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.storage import TicketStore, get_store
from app.api.tickets import make_router as make_tickets_router
from app.api.agents import make_router as make_agents_router


def create_app(store: TicketStore | None = None) -> FastAPI:
    app = FastAPI(title="Agent Ticket System")

    if store is None:
        store = get_store()

    app.include_router(make_tickets_router(store))
    app.include_router(make_agents_router(store))

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(static_dir, "index.html"))

    return app


app = create_app()
