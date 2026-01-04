"""API endpoints for wasteland exploration."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
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
from app.services.wasteland_service import wasteland_service

router = APIRouter()


@router.post("/send", response_model=ExplorationRead)
async def send_dweller_to_wasteland(
    request: ExplorationSendRequest,
    vault_id: Annotated[UUID4, Query()],
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Send a dweller to the wasteland for exploration."""
    await get_user_vault_or_403(vault_id, user, db_session)
    # Check if dweller is already on an active exploration
    existing_exploration = await crud_exploration.get_by_dweller(
        db_session,
        dweller_id=request.dweller_id,
    )

    if existing_exploration:
        raise HTTPException(
            status_code=400,
            detail="Dweller is already on an exploration",
        )

    # Create new exploration with dweller's current stats
    return await crud_exploration.create_with_dweller_stats(
        db_session,
        vault_id=vault_id,
        dweller_id=request.dweller_id,
        duration=request.duration,
    )


@router.get("/vault/{vault_id}", response_model=list[ExplorationReadShort])
async def list_explorations_by_vault(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    active_only: bool = True,  # noqa: FBT001, FBT002
):
    """List all explorations for a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)
    if active_only:
        explorations = await crud_exploration.get_active_by_vault(
            db_session,
            vault_id=vault_id,
        )
    else:
        # Get all explorations for vault (we can add this method if needed)
        explorations = await crud_exploration.get_active_by_vault(
            db_session,
            vault_id=vault_id,
        )

    return explorations


@router.get("/{exploration_id}", response_model=ExplorationRead)
async def get_exploration(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get detailed information about an exploration."""
    await verify_exploration_access(exploration_id, user, db_session)
    return await crud_exploration.get(db_session, exploration_id)


@router.get("/{exploration_id}/progress", response_model=ExplorationProgress)
async def get_exploration_progress(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get current progress of an exploration."""
    await verify_exploration_access(exploration_id, user, db_session)
    exploration = await crud_exploration.get(db_session, exploration_id)

    return ExplorationProgress(
        id=exploration.id,
        status=exploration.status,
        progress_percentage=exploration.progress_percentage(),
        time_remaining_seconds=exploration.time_remaining_seconds(),
        elapsed_time_seconds=exploration.elapsed_time_seconds(),
        events=exploration.events,
        loot_collected=exploration.loot_collected,
    )


@router.post("/{exploration_id}/recall", response_model=ExplorationCompleteResponse)
async def recall_dweller(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Recall a dweller early from exploration."""
    await verify_exploration_access(exploration_id, user, db_session)
    try:
        rewards = await wasteland_service.recall_exploration(db_session, exploration_id)
        exploration = await crud_exploration.get(db_session, exploration_id)

        return ExplorationCompleteResponse(
            exploration=exploration,
            rewards_summary=rewards,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904


@router.post("/{exploration_id}/complete", response_model=ExplorationCompleteResponse)
async def complete_exploration(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Complete an exploration and collect rewards."""
    await verify_exploration_access(exploration_id, user, db_session)
    try:
        rewards = await wasteland_service.complete_exploration(db_session, exploration_id)
        exploration = await crud_exploration.get(db_session, exploration_id)

        return ExplorationCompleteResponse(
            exploration=exploration,
            rewards_summary=rewards,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904


@router.post("/{exploration_id}/generate_event", response_model=ExplorationRead)
async def generate_event(
    exploration_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Manually trigger event generation for an exploration (for testing/debugging)."""
    await verify_exploration_access(exploration_id, user, db_session)
    exploration = await crud_exploration.get(db_session, exploration_id)

    if not exploration.is_active():
        raise HTTPException(status_code=400, detail="Exploration is not active")

    return await wasteland_service.process_event(db_session, exploration)
