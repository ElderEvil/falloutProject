"""API endpoints for wasteland exploration."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403, verify_exploration_access
from app.crud import exploration as crud_exploration
from app.db.session import get_async_session
from app.schemas.exploration import (
    ExplorationCompleteResponse,
    ExplorationProgress,
    ExplorationRead,
    ExplorationReadShort,
    ExplorationSendRequest,
)
from app.services.exploration_service import exploration_service
from app.utils.exceptions import ValidationException

router = APIRouter(prefix="/explorations", tags=["Exploration"])


@router.post("/send", response_model=ExplorationRead)
async def send_dweller_to_wasteland(
    request: ExplorationSendRequest,
    vault_id: Annotated[UUID4, Query()],
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExplorationRead:
    """Send a dweller to the wasteland for exploration."""
    await get_user_vault_or_403(vault_id, user, db_session)
    try:
        return await exploration_service.send_dweller(
            db_session,
            vault_id=vault_id,
            dweller_id=request.dweller_id,
            duration=request.duration,
            stimpaks=request.stimpaks,
            radaways=request.radaways,
        )
    except ValueError as e:
        raise ValidationException(str(e)) from e


@router.get("/vault/{vault_id}", response_model=list[ExplorationReadShort])
async def list_explorations_by_vault(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    active_only: bool = True,
) -> list[ExplorationReadShort]:
    """List all explorations for a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud_exploration.get_by_vault(
        db_session,
        vault_id=vault_id,
        active_only=active_only,
    )


@router.get("/{exploration_id}", response_model=ExplorationRead)
async def get_exploration(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExplorationRead:
    """Get detailed information about an exploration."""
    await verify_exploration_access(exploration_id, user, db_session)
    return await crud_exploration.get(db_session, exploration_id)


@router.get("/{exploration_id}/progress", response_model=ExplorationProgress)
async def get_exploration_progress(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExplorationProgress:
    """Get current progress of an exploration."""
    await verify_exploration_access(exploration_id, user, db_session)
    return await exploration_service.get_exploration_progress(db_session, exploration_id)


@router.post("/{exploration_id}/recall", response_model=ExplorationCompleteResponse)
async def recall_dweller(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExplorationCompleteResponse:
    """Recall a dweller early from exploration."""
    await verify_exploration_access(exploration_id, user, db_session)
    try:
        exploration, rewards = await exploration_service.recall_exploration_with_data(db_session, exploration_id)
        return ExplorationCompleteResponse(
            exploration=exploration,
            rewards_summary=rewards.model_dump(),
        )
    except ValueError as e:
        raise ValidationException(str(e)) from e


@router.post("/{exploration_id}/complete", response_model=ExplorationCompleteResponse)
async def complete_exploration(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExplorationCompleteResponse:
    """Complete an exploration and collect rewards."""
    await verify_exploration_access(exploration_id, user, db_session)
    try:
        exploration, rewards = await exploration_service.complete_exploration_with_data(db_session, exploration_id)
        return ExplorationCompleteResponse(
            exploration=exploration,
            rewards_summary=rewards.model_dump(),
        )
    except ValueError as e:
        raise ValidationException(str(e)) from e


@router.post("/{exploration_id}/generate_event", response_model=ExplorationRead)
async def generate_event(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> ExplorationRead:
    """Manually trigger event generation for an exploration (for testing/debugging)."""
    await verify_exploration_access(exploration_id, user, db_session)
    try:
        return await exploration_service.process_event_for_exploration(db_session, exploration_id)
    except ValueError as e:
        raise ValidationException(str(e)) from e
