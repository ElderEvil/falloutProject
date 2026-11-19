"""Hazard team roster endpoints."""

from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentActiveUser, DBSession, get_user_vault_or_403
from app.core.enums import HazardTeam
from app.schemas.contamination_team import ContaminationTeamRead, HazardTeamPlaceUpdate
from app.services.hazard_team_service import hazard_team_service

router = APIRouter(prefix="/contamination-team", tags=["Contamination Team"])


@router.get("/vault/{vault_id}/roster", response_model=ContaminationTeamRead)
async def get_hazard_team_roster(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> ContaminationTeamRead:
    """Return each hazard team's roster: who holds a place, and who waits on the bench."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await hazard_team_service.get_roster(db_session, vault_id)


@router.put("/vault/{vault_id}/{team}/{dweller_id}", response_model=ContaminationTeamRead)
async def set_hazard_team_place(
    vault_id: UUID,
    team: HazardTeam,
    dweller_id: UUID,
    payload: HazardTeamPlaceUpdate,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> ContaminationTeamRead:
    """Move a team member between Active and Reserve, returning the updated roster."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await hazard_team_service.set_place(db_session, vault_id, team, dweller_id, active=payload.active)
