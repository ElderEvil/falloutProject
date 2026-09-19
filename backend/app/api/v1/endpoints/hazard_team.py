"""Contamination team roster endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.schemas.contamination_team import ContaminationTeamRead
from app.services.hazard_team_service import hazard_team_service

router = APIRouter(prefix="/contamination-team", tags=["Contamination Team"])


@router.get("/vault/{vault_id}/roster", response_model=ContaminationTeamRead)
async def get_contamination_team_roster(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ContaminationTeamRead:
    """Return each hazard team's roster: who holds a place, and who waits on the bench."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await hazard_team_service.get_roster(db_session, vault_id)
