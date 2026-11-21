"""World event lifecycle tick.

A separate module because importing app.api.tasks from an endpoint is circular
(tasks -> crud.pregnancy -> app.api.deps).
"""

import logging

import dramatiq
import periodiq

import app.core.dramatiq  # ruff: ignore[unused-import] — broker must be set before the actor registers
from app.core import db_locks
from app.core.async_runtime import run_async
from app.db.session import task_session

logger = logging.getLogger(__name__)


async def _advance_world_event() -> str | None:
    """Advance the active event one lifecycle step under the cross-worker tick lock."""
    from app.services.world_event_service import world_event_service

    async with task_session() as session, db_locks.hold_advisory_lock(session, "world-event-tick") as acquired:
        if not acquired:
            # Another worker is mid-advance; the next cron tick retries.
            return "locked"
        return await world_event_service.advance(session)


@dramatiq.actor(actor_name="advance_world_event", max_retries=3, min_backoff=60000)
def advance_world_event():
    """Advance the active world event's lifecycle; return what changed."""
    try:
        result = run_async(_advance_world_event())
    except Exception:
        logger.exception("World event advance failed")
        raise
    else:
        logger.info(f"World event advance completed: {result}")
        return result


advance_world_event.options["periodic"] = periodiq.cron("*/5 * * * *")
