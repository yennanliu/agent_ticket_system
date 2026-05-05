import os
import time

from app.models import Ticket
from app.storage import TicketStore
from app.agents.validator import run_validator
from app.agents.enricher import run_enricher

HEAL_THRESHOLD = float(os.getenv("HEAL_THRESHOLD", "0.75"))
HEAL_MAX_ITERATIONS = int(os.getenv("HEAL_MAX_ITERATIONS", "3"))


def run_healer(ticket_id: str, store: TicketStore, logger=None) -> Ticket:
    ticket = store.get(ticket_id)
    if ticket is None:
        raise ValueError(f"Ticket {ticket_id} not found")

    start = time.time()
    iterations = 0

    try:
        ticket = run_validator(ticket_id, store, logger=logger)

        while iterations < HEAL_MAX_ITERATIONS:
            if (ticket.validation_score or 0.0) >= HEAL_THRESHOLD:
                break

            source = ticket.source_repo
            if not source:
                break  # cannot re-enrich without a repo

            feedback = ticket.validation_notes
            ticket = run_enricher(ticket_id, source, store, feedback=feedback, logger=logger)
            ticket = run_validator(ticket_id, store, logger=logger)

            iterations += 1
            store.update(ticket_id, {"validation_iterations": iterations})
            # keep using ticket returned by run_validator (has up-to-date score);
            # just reflect the new iterations count on it
            ticket = ticket.model_copy(update={"validation_iterations": iterations})

        if logger:
            logger.log(
                "heal", "healer", ticket_id=ticket_id,
                duration_ms=(time.time() - start) * 1000,
                status="success",
                details=f"score={ticket.validation_score}, iters={iterations}",
            )
        return ticket

    except Exception as e:
        if logger:
            logger.log(
                "heal", "healer", ticket_id=ticket_id,
                duration_ms=(time.time() - start) * 1000,
                status="error", details=str(e),
            )
        raise
