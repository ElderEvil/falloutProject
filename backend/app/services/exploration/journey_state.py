"""Journey-level state transitions shared by recall, retreat and dweller deletion."""

from datetime import datetime

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerStatusEnum
from app.crud import dweller as dweller_crud
from app.crud import expedition_run as crud_expedition_run
from app.crud.dweller import determine_status_for_room
from app.crud.room import room as room_crud
from app.crud.team import team_crud
from app.models.exploration import ExpeditionRun, ExpeditionRunStatus, Exploration
from app.schemas.dweller import DwellerUpdate


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


async def restore_dweller_status(db_session: AsyncSession, dweller_id: UUID4) -> None:
    """Restore one dweller's room-appropriate status after a journey; the caller commits."""
    dweller_obj = await dweller_crud.get(db_session, dweller_id)
    if dweller_obj.is_dead:
        return
    if dweller_obj.room_id:
        room_obj = await room_crud.get(db_session, dweller_obj.room_id)
        new_status = determine_status_for_room(room_obj.category, room_obj.name)
    else:
        new_status = DwellerStatusEnum.IDLE
    await dweller_crud.update(db_session, dweller_id, DwellerUpdate(status=new_status), commit=False)


async def settle_journey_dwellers(db_session: AsyncSession, exploration: Exploration) -> None:
    """Return every survivor to a room-appropriate status and drop the party roster.

    Shared by normal finalization and terminal closes (dweller deletion): departure
    marks every party member EXPLORING, so a terminal close that skipped this would
    leave survivors unavailable for new assignments. The caller commits.
    """
    if exploration.team_id is not None:
        for member in await team_crud.get_exploration_team_dwellers(db_session, exploration.id):
            if not member.is_dead:
                await restore_dweller_status(db_session, member.id)
        team = await team_crud.get_exploration_team(db_session, exploration.id)
        if team is not None:
            await db_session.delete(team)
        return
    await restore_dweller_status(db_session, exploration.dweller_id)
