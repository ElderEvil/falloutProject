"""Failure-isolation policy for per-entity steps inside tick phases.

Tick sweeps must survive single bad entities: one corrupt exploration or
training session cannot abort the whole pass. This helper is the only
sanctioned shape for that — call it instead of nesting try/except blocks.
"""

import contextlib
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


async def refresh_after_recovery(db_session: "AsyncSession", entities: Iterable[object]) -> None:
    """Re-load instances expired by a rollback so the next step may touch them.

    ``recover_session`` expires every loaded ORM instance, so a sweep that keeps
    iterating its originally-loaded list would trip an implicit async refresh
    (``MissingGreenlet``) on the next attribute access. Call this with the
    remaining entities after a recovery; an entity whose row is gone stays
    expired and is skipped by the caller's own error handling.
    """
    for entity in entities:
        if not isinstance(entity, SQLModel):
            continue  # not a mapped instance (e.g. a test double)
        with contextlib.suppress(SQLAlchemyError):
            await db_session.refresh(entity)


async def recover_session(db_session: "AsyncSession") -> None:
    """Restore a session after a failed statement and drop deferred side effects.

    A failed statement aborts the transaction, so every later statement on the
    same session fails until it is rolled back — one bad entity would otherwise
    fail the rest of the sweep. Rolling back is not enough on its own:
    notifications and level-ups queued for delivery after the next commit
    describe work that no longer exists, so they are discarded with it.
    """
    from app.services.leveling_service import leveling_service
    from app.services.notification_service import notification_service

    notification_service.discard_deferred_notifications(db_session)
    leveling_service.discard_deferred_level_ups(db_session)
    await db_session.rollback()


async def guard_phase(
    label: str,
    fn: Callable[[], Awaitable[None]],
    *,
    catch: tuple[type[BaseException], ...],
    db_session: "AsyncSession | None" = None,
) -> str | None:
    """Run a per-entity tick step; return the error message, or None on success.

    Pass ``db_session`` so a database error recovers the session: without it the
    aborted transaction fails every later entity in the sweep.
    """
    try:
        await fn()
    except catch as e:
        logger.error(f"{label}: {e}", exc_info=True)
        if db_session is not None and isinstance(e, SQLAlchemyError):
            await recover_session(db_session)
        return str(e)
    else:
        return None
