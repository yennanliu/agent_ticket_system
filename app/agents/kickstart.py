import os
import time

from app.models import Ticket
from app.storage import TicketStore
from app.agents.enricher import run_enricher
from app.agents.validator import run_validator
from app.agents.splitter import run_splitter

KICKSTART_THRESHOLD = float(os.getenv("KICKSTART_THRESHOLD", "0.60"))
KICKSTART_MAX_RETRIES = int(os.getenv("KICKSTART_MAX_RETRIES", "3"))
_SPLIT_TYPES = {"epic", "story"}


def run_kickstart(ticket_id: str, store: TicketStore, logger=None) -> Ticket:
    """Enrich → validate → re-enrich/validate loop for newly created tickets.

    Skips enrichment if ticket has no source_repo.
    Retries up to KICKSTART_MAX_RETRIES times when score < KICKSTART_THRESHOLD.
    """
    ticket = store.get(ticket_id)
    if ticket is None:
        raise ValueError(f"Ticket {ticket_id} not found")

    start = time.time()
    source = ticket.source_repo
    retries = 0

    try:
        if source:
            ticket = run_enricher(ticket_id, source, store, logger=logger)

        ticket = run_validator(ticket_id, store, logger=logger)

        while retries < KICKSTART_MAX_RETRIES and source and (ticket.validation_score or 0.0) < KICKSTART_THRESHOLD:
            feedback = ticket.validation_notes
            ticket = run_enricher(ticket_id, source, store, feedback=feedback, logger=logger)
            ticket = run_validator(ticket_id, store, logger=logger)
            retries += 1
            store.update(ticket_id, {"validation_iterations": retries})
            ticket = ticket.model_copy(update={"validation_iterations": retries})

        if ticket.ticket_type in _SPLIT_TYPES:
            try:
                run_splitter(ticket_id, store, logger=logger)
            except Exception:
                pass  # split failure must not fail kickstart

        if logger:
            logger.log(
                "kickstart", "kickstart", ticket_id=ticket_id,
                duration_ms=(time.time() - start) * 1000,
                status="success",
                details=f"score={ticket.validation_score}, retries={retries}, type={ticket.ticket_type}",
            )
        return ticket

    except Exception as e:
        if logger:
            logger.log(
                "kickstart", "kickstart", ticket_id=ticket_id,
                duration_ms=(time.time() - start) * 1000,
                status="error", details=str(e),
            )
        raise
