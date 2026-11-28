"""Combat Zone endpoints — thin handlers over ``CombatZoneService``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.core.game_config import game_config
from app.db.session import get_async_session
from app.schemas.combat_zone import (
    CombatZoneEventRead,
    CombatZoneHistoryEntry,
    CombatZoneLobbyRead,
    CombatZoneMatchRead,
    CombatZonePartyRead,
    CombatZoneSendRequest,
    CombatZoneStanceRequest,
)
from app.services.combat.combat_zone_service import combat_zone_service
from app.utils.exceptions import NotFoundException

router = APIRouter(prefix="/combat-zone", tags=["Combat Zone"])


async def require_combat_zone_commands(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Player writes 404 while the global switch is off."""
    if not game_config.combat_zone.enabled:
        raise NotFoundException("The Combat Zone is offline.")
    await get_user_vault_or_403(vault_id, user, db_session)


@router.get("/lobby", response_model=CombatZoneLobbyRead)
async def get_lobby(
    _user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZoneLobbyRead:
    """The shared board: queued parties and live matches across every vault."""
    return await combat_zone_service.get_lobby(db_session)


@router.get(
    "/vault/{vault_id}/party",
    response_model=CombatZonePartyRead | None,
)
async def get_party(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZonePartyRead | None:
    """This vault's party, or null before its first send."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await combat_zone_service.get_party(db_session, vault_id)


@router.post(
    "/vault/{vault_id}/party",
    response_model=CombatZonePartyRead,
    dependencies=[Depends(require_combat_zone_commands)],
)
async def send_party(
    vault_id: UUID,
    payload: CombatZoneSendRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZonePartyRead:
    """Send one dweller to the Zone, escrowing the entry fee."""
    _ = user
    return await combat_zone_service.send_party(db_session, vault_id, payload.dweller_id)


@router.delete(
    "/vault/{vault_id}/party",
    response_model=CombatZonePartyRead,
    dependencies=[Depends(require_combat_zone_commands)],
)
async def recall_party(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZonePartyRead:
    """Recall the party. A queued fee is refunded; an in-match recall retreats."""
    _ = user
    return await combat_zone_service.recall_party(db_session, vault_id)


@router.post(
    "/vault/{vault_id}/stance",
    response_model=CombatZonePartyRead,
    dependencies=[Depends(require_combat_zone_commands)],
)
async def set_stance(
    vault_id: UUID,
    payload: CombatZoneStanceRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZonePartyRead:
    """Set the party's stance; it applies from the next micro-round."""
    _ = user
    return await combat_zone_service.set_stance(db_session, vault_id, payload.stance)


@router.post(
    "/vault/{vault_id}/challenge/{target_party_id}",
    response_model=CombatZoneMatchRead,
    dependencies=[Depends(require_combat_zone_commands)],
)
async def challenge_party(
    vault_id: UUID,
    target_party_id: UUID,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZoneMatchRead:
    """Challenge a queued party directly, ignoring the auto-pair power band."""
    _ = user
    return await combat_zone_service.challenge(db_session, vault_id, target_party_id)


@router.get(
    "/matches",
    response_model=list[CombatZoneHistoryEntry],
)
async def list_match_history(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    limit: int = 20,
) -> list[CombatZoneHistoryEntry]:
    """Bounded recent finished bouts for one vault."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await combat_zone_service.history(db_session, vault_id, limit=limit)


@router.get(
    "/matches/{match_id}",
    response_model=CombatZoneMatchRead,
)
async def get_match(
    match_id: UUID,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZoneMatchRead:
    """Spectate a live match or replay a finished one as a participant."""
    return await combat_zone_service.get_match(db_session, match_id, user.id)


@router.get(
    "/matches/{match_id}/events",
    response_model=list[CombatZoneEventRead],
)
async def get_match_events(
    match_id: UUID,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    after_sequence: int | None = None,
) -> list[CombatZoneEventRead]:
    """Poll the journal after the last sequence already seen."""
    return await combat_zone_service.get_events(db_session, match_id, after_sequence, user.id)
