"""Combat Zone endpoints — thin handlers over ``CombatZoneService``."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403
from app.db.session import get_async_session
from app.schemas.combat_zone import (
    CombatZoneEventRead,
    CombatZoneLobbyRead,
    CombatZoneMatchRead,
    CombatZonePartyRead,
    CombatZoneSendRequest,
    CombatZoneStanceRequest,
    CombatZoneVaultToggleRead,
    CombatZoneVaultToggleRequest,
)
from app.services.combat.combat_zone_service import combat_zone_service

router = APIRouter(prefix="/combat-zone", tags=["Combat Zone"])


@router.get("/lobby", response_model=CombatZoneLobbyRead)
async def get_lobby(
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZoneLobbyRead:
    """The shared board: queued parties and live matches across every vault."""
    _ = user
    return await combat_zone_service.get_lobby(db_session)


@router.get("/vault/{vault_id}/party", response_model=CombatZonePartyRead | None)
async def get_party(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZonePartyRead | None:
    """This vault's party, or null before its first send."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await combat_zone_service.get_party(db_session, vault_id)


@router.post("/vault/{vault_id}/party", response_model=CombatZonePartyRead)
async def send_party(
    vault_id: UUID4,
    payload: CombatZoneSendRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZonePartyRead:
    """Send one dweller to the Zone, escrowing the entry fee."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await combat_zone_service.send_party(db_session, vault_id, payload.dweller_id)


@router.delete("/vault/{vault_id}/party", response_model=CombatZonePartyRead)
async def recall_party(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZonePartyRead:
    """Recall the party. A queued fee is refunded; an in-match recall retreats."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await combat_zone_service.recall_party(db_session, vault_id)


@router.post("/vault/{vault_id}/stance", response_model=CombatZonePartyRead)
async def set_stance(
    vault_id: UUID4,
    payload: CombatZoneStanceRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZonePartyRead:
    """Set the party's stance; it applies from the next micro-round."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await combat_zone_service.set_stance(db_session, vault_id, payload.stance)


@router.post("/vault/{vault_id}/challenge/{target_party_id}", response_model=CombatZoneMatchRead)
async def challenge_party(
    vault_id: UUID4,
    target_party_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZoneMatchRead:
    """Challenge a queued party directly, ignoring the auto-pair power band."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await combat_zone_service.challenge(db_session, vault_id, target_party_id)


@router.post("/admin/vault/{vault_id}/enabled", response_model=CombatZoneVaultToggleRead)
async def set_vault_enabled(
    vault_id: UUID4,
    payload: CombatZoneVaultToggleRequest,
    _user: CurrentSuperuser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZoneVaultToggleRead:
    """Admin switch: enable or disable the Combat Zone for one vault."""
    enabled = await combat_zone_service.set_vault_enabled(db_session, vault_id, payload.enabled)
    return CombatZoneVaultToggleRead(vault_id=vault_id, enabled=enabled)


@router.get("/matches/{match_id}", response_model=CombatZoneMatchRead)
async def get_match(
    match_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> CombatZoneMatchRead:
    """Spectate a match: both parties, live HP, pot, and journal."""
    _ = user
    return await combat_zone_service.get_match(db_session, match_id)


@router.get("/matches/{match_id}/events", response_model=list[CombatZoneEventRead])
async def get_match_events(
    match_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    after_seq: int | None = None,
) -> list[CombatZoneEventRead]:
    """Poll the journal after the last round already seen."""
    _ = user
    return await combat_zone_service.get_events(db_session, match_id, after_seq)
