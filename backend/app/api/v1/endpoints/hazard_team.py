"""Hazard team roster endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.core.enums import HazardTeam
from app.db.session import get_async_session
from app.schemas.contamination_team import ContaminationTeamRead, HazardTeamPlaceUpdate
from app.services.hazard_team_service import hazard_team_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException

router = APIRouter(prefix="/contamination-team", tags=["Contamination Team"])


@router.get("/vault/{vault_id}/roster", response_model=ContaminationTeamRead)
async def get_hazard_team_roster(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ContaminationTeamRead:
    """Return each hazard team's roster: who holds a place, and who waits on the bench."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await hazard_team_service.get_roster(db_session, vault_id)


@router.put("/vault/{vault_id}/{team}/{dweller_id}", response_model=ContaminationTeamRead)
async def set_hazard_team_place(
    vault_id: UUID4,
    team: HazardTeam,
    dweller_id: UUID4,
    payload: HazardTeamPlaceUpdate,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ContaminationTeamRead:
    """Move a team member between Active and Reserve, returning the updated roster."""
    await get_user_vault_or_403(vault_id, user, db_session)
    try:
        return await hazard_team_service.set_place(db_session, vault_id, team, dweller_id, active=payload.active)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ResourceConflictException as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
