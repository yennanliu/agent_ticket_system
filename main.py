from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.storage import TicketStore, get_store
from app.logger import AgentLogger, get_logger
from app.api.tickets import make_router as make_tickets_router
from app.api.agents import make_router as make_agents_router
from app.api.logs import make_router as make_logs_router

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def create_app(store: TicketStore | None = None, logger: AgentLogger | None = None) -> FastAPI:
    app = FastAPI(title="Agent Ticket System")

    if store is None:
        store = get_store()
    if logger is None:
        logger = get_logger()

    app.include_router(make_tickets_router(store))
    app.include_router(make_agents_router(store, logger))
    app.include_router(make_logs_router(logger))

    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    templates = Jinja2Templates(directory=_TEMPLATES_DIR)

    @app.get("/")
    def landing(request: Request):
        return templates.TemplateResponse(request=request, name="landing.html", context={"active": "landing"})

    @app.get("/tickets")
    def index(request: Request):
        return templates.TemplateResponse(request=request, name="index.html", context={"active": "tickets"})

    @app.get("/tickets/{ticket_id}")
    def ticket_page(request: Request, ticket_id: str):
        return templates.TemplateResponse(request=request, name="ticket.html", context={"active": "tickets"})

    @app.get("/review")
    def review_page(request: Request):
        return templates.TemplateResponse(request=request, name="review.html", context={"active": "review"})

    @app.get("/logs")
    def logs_page(request: Request):
        return templates.TemplateResponse(request=request, name="logs.html", context={"active": "logs"})

    @app.get("/agents")
    def agents_page(request: Request):
        return templates.TemplateResponse(request=request, name="agents.html", context={"active": "agents"})

    @app.get("/agent-metrics")
    def agent_metrics_page(request: Request):
        return templates.TemplateResponse(request=request, name="agent_metrics.html", context={"active": "agent-metrics"})

    @app.get("/ticket-metrics")
    def ticket_metrics_page(request: Request):
        return templates.TemplateResponse(request=request, name="ticket_metrics.html", context={"active": "ticket-metrics"})

    return app


app = create_app()
