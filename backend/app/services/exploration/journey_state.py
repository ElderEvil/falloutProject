"""Journey-level state transitions shared by recall, retreat and dweller deletion."""

from datetime import datetime

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import expedition_run as crud_expedition_run
from app.models.exploration import ExpeditionRun, ExpeditionRunStatus


async def close_open_site_run(
    db_session: AsyncSession,
    exploration_id: UUID4,
    *,
    now: datetime | None = None,
) -> ExpeditionRun | None:
    """Force-retreat the open site run so no run outlives its journey; the caller commits."""
    run = await crud_expedition_run.get_open_for_exploration_for_update(db_session, exploration_id)
    if run is None:
        return None
    run.status = ExpeditionRunStatus.RETREATED
    run.finished_at = now or datetime.utcnow()
    db_session.add(run)
    await db_session.flush()
    return run
