from fastapi import APIRouter, HTTPException, status, Depends
from app.models import Ticket, CreateTicketRequest, UpdateTicketRequest
from app.storage import TicketStore

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _get_store_dep(store: TicketStore):
    """Returns a FastAPI dependency that injects the given store."""
    def dep():
        return store
    return dep


def make_router(store: TicketStore) -> APIRouter:
    r = APIRouter(prefix="/api/tickets", tags=["tickets"])

    @r.get("", response_model=list[Ticket])
    def list_tickets():
        return store.get_all()

    @r.get("/{ticket_id}", response_model=Ticket)
    def get_ticket(ticket_id: str):
        ticket = store.get(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket

    @r.post("", response_model=Ticket, status_code=status.HTTP_201_CREATED)
    def create_ticket(body: CreateTicketRequest):
        ticket = Ticket(**body.model_dump())
        return store.create(ticket)

    @r.put("/{ticket_id}", response_model=Ticket)
    def update_ticket(ticket_id: str, body: UpdateTicketRequest):
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        updated = store.update(ticket_id, fields)
        if not updated:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return updated

    @r.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_ticket(ticket_id: str):
        if not store.delete(ticket_id):
            raise HTTPException(status_code=404, detail="Ticket not found")

    return r
