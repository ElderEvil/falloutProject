"""World event endpoints — the vault-scoped view of the server-wide co-op event."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentActiveUser, DBSession, get_user_vault_or_403
from app.schemas.world_event import WorldEventClaimRead, WorldEventRead
from app.services.world_event_service import world_event_service

router = APIRouter(prefix="/vaults/{vault_id}/world-event", tags=["World Event"])


@router.get("", response_model=WorldEventRead)
async def get_world_event(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> WorldEventRead:
    """Return global progress plus this vault's contribution and claim eligibility."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await world_event_service.get_state(db_session, vault_id)


@router.post("/claim", response_model=WorldEventClaimRead)
async def claim_world_event(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> WorldEventClaimRead:
    """Pay the completed event's reward list to a qualifying vault exactly once."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await world_event_service.claim(db_session, vault_id)
