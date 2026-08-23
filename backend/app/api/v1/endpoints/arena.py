"""Arena endpoints — experimental battle playground."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4, BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.core.game_config import game_config
from app.db.session import get_async_session
from app.models.arena_match_event import ArenaMatchEvent
from app.services.arena_service import arena_service

router = APIRouter(prefix="/arena", tags=["Arena"])


class ArenaFightersRequest(BaseModel):
    """Fighter slot selection payload."""

    fighter_a_id: UUID4 | None = None
    fighter_b_id: UUID4 | None = None


@router.get("/vault/{vault_id}/state")
async def get_arena_state(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """Return arena rooms with their selected fighters, roster, match state, and journal."""
    await get_user_vault_or_403(vault_id, user, db_session)

    from datetime import datetime

    from app.models.dweller import Dweller
    from app.models.room import Room
    from app.schemas.common import AgeGroupEnum

    rooms_result = await db_session.execute(select(Room).where(Room.vault_id == vault_id, Room.category == "arena"))
    rooms = list(rooms_result.scalars().all())

    countdown = game_config.game_loop.arena_countdown_seconds
    state = []
    for room in rooms:
        fighters = await arena_service.get_fighters(db_session, room)

        roster_result = await db_session.execute(
            select(Dweller)
            .where(
                Dweller.room_id == room.id,
                Dweller.health > 0,
                Dweller.is_adult,
                Dweller.age_group == AgeGroupEnum.ADULT,
            )
            .order_by(Dweller.created_at)
        )
        roster = list(roster_result.scalars().all())

        match_done = room.arena_last_fight_at is not None
        started = room.arena_fight_started_at is not None
        countdown_remaining = 0
        if started and not match_done:
            elapsed = (datetime.utcnow() - room.arena_fight_started_at).total_seconds()
            countdown_remaining = max(0, int(countdown - elapsed))

        events_result = await db_session.execute(
            select(ArenaMatchEvent)
            .where(ArenaMatchEvent.room_id == room.id)
            .order_by(ArenaMatchEvent.created_at.desc())
            .limit(40)
        )
        events = [
            {
                "id": str(e.id),
                "round_seq": e.round_seq,
                "kind": e.kind,
                "message": e.message,
            }
            for e in reversed(events_result.scalars().all())
        ]

        state.append(
            {
                "room_id": str(room.id),
                "room_name": room.name,
                "tier": room.tier,
                "fighter_a_id": str(room.arena_fighter_a_id) if room.arena_fighter_a_id else None,
                "fighter_b_id": str(room.arena_fighter_b_id) if room.arena_fighter_b_id else None,
                "fighters": [
                    {
                        "id": str(f.id),
                        "name": f"{f.first_name} {f.last_name}",
                        "level": f.level,
                        "health": f.health,
                        "max_health": f.max_health,
                        "strength": f.strength,
                        "endurance": f.endurance,
                        "agility": f.agility,
                    }
                    for f in fighters
                ],
                "roster": [
                    {
                        "id": str(d.id),
                        "name": f"{d.first_name} {d.last_name}",
                        "level": d.level,
                        "health": d.health,
                        "max_health": d.max_health,
                    }
                    for d in roster
                ],
                "fight_ready": len(roster) >= 2,
                "match_done": match_done,
                "fight_started": started,
                "countdown_remaining": countdown_remaining,
                "can_start": len(fighters) == 2 and not started and not match_done,
                "events": events,
            }
        )

    return {"rooms": state}


@router.post("/vault/{vault_id}/rooms/{room_id}/fighters")
async def set_arena_fighters(
    vault_id: UUID4,
    room_id: UUID4,
    payload: ArenaFightersRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """Pick which assigned dwellers fight. Changing the selection resets the match."""
    await get_user_vault_or_403(vault_id, user, db_session)
    room = await arena_service.set_fighters(db_session, room_id, payload.fighter_a_id, payload.fighter_b_id)
    return {
        "room_id": str(room.id),
        "fighter_a_id": str(room.arena_fighter_a_id) if room.arena_fighter_a_id else None,
        "fighter_b_id": str(room.arena_fighter_b_id) if room.arena_fighter_b_id else None,
    }


@router.delete("/vault/{vault_id}/rooms/{room_id}/events")
async def clear_arena_events(
    vault_id: UUID4,
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """Clear the battle journal for an arena room."""
    await get_user_vault_or_403(vault_id, user, db_session)
    cleared = await arena_service.clear_journal(db_session, room_id)
    return {"room_id": str(room_id), "cleared": cleared}


@router.post("/vault/{vault_id}/rooms/{room_id}/start")
async def start_arena_fight(
    vault_id: UUID4,
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """Arm an arena match: both fighter slots set, not already done/started."""
    await get_user_vault_or_403(vault_id, user, db_session)
    room = await arena_service.start_fight(db_session, room_id)
    # Wake the arena tick chain immediately so combat starts right after the
    # countdown instead of waiting for the periodiq watchdog (up to 2 min).
    from app.api.arena_tasks import arena_tick

    arena_tick.send()
    return {"room_id": str(room.id), "started": True}
