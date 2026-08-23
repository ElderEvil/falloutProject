"""Arena endpoints — experimental battle playground."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.schemas.arena import (
    ArenaEventsCleared,
    ArenaFightersRequest,
    ArenaFightersResponse,
    ArenaFightStarted,
    ArenaState,
)
from app.services.arena_service import arena_service

router = APIRouter(prefix="/arena", tags=["Arena"])


@router.get("/vault/{vault_id}/state", response_model=ArenaState)
async def get_arena_state(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ArenaState:
    """Return arena rooms with their selected fighters, roster, match state, and journal."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await arena_service.get_arena_state(db_session, vault_id)


@router.post("/vault/{vault_id}/rooms/{room_id}/fighters", response_model=ArenaFightersResponse)
async def set_arena_fighters(
    vault_id: UUID4,
    room_id: UUID4,
    payload: ArenaFightersRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ArenaFightersResponse:
    """Pick which assigned dwellers fight. Changing the selection resets the match."""
    await get_user_vault_or_403(vault_id, user, db_session)
    room = await arena_service.set_fighters(db_session, room_id, payload.fighter_a_id, payload.fighter_b_id, vault_id)
    return ArenaFightersResponse(
        room_id=str(room.id),
        fighter_a_id=str(room.arena_fighter_a_id) if room.arena_fighter_a_id else None,
        fighter_b_id=str(room.arena_fighter_b_id) if room.arena_fighter_b_id else None,
    )


@router.delete("/vault/{vault_id}/rooms/{room_id}/events", response_model=ArenaEventsCleared)
async def clear_arena_events(
    vault_id: UUID4,
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ArenaEventsCleared:
    """Clear the battle journal for an arena room."""
    await get_user_vault_or_403(vault_id, user, db_session)
    cleared = await arena_service.clear_journal(db_session, room_id, vault_id)
    return ArenaEventsCleared(room_id=str(room_id), cleared=cleared)


@router.post("/vault/{vault_id}/rooms/{room_id}/start", response_model=ArenaFightStarted)
async def start_arena_fight(
    vault_id: UUID4,
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ArenaFightStarted:
    """Arm an arena match: both fighter slots set, not already done/started."""
    await get_user_vault_or_403(vault_id, user, db_session)
    room = await arena_service.start_fight(db_session, room_id, vault_id)
    # Wake the arena tick chain immediately so combat starts right after the
    # countdown instead of waiting for the periodiq watchdog (up to 2 min).
    from app.api.arena_tasks import arena_tick

    arena_tick.send()
    return ArenaFightStarted(room_id=str(room.id), started=True)
