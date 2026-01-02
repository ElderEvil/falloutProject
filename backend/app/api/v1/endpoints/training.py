"""API endpoints for dweller training."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.crud import training as crud_training
from app.crud.dweller import dweller as dweller_crud
from app.crud.room import room as room_crud
from app.db.session import get_async_session
from app.schemas.training import TrainingProgress, TrainingRead
from app.services.training_service import training_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, VaultOperationException

router = APIRouter()


@router.post("/start", response_model=TrainingRead, status_code=201)
async def start_training(
    dweller_id: Annotated[UUID4, Query()],
    room_id: Annotated[UUID4, Query()],
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Start training a dweller in a training room.

    Args:
        dweller_id: Dweller to train
        room_id: Training room ID
        user: Current authenticated user
        db_session: Database session

    Returns:
        Created training session

    Raises:
        404: Dweller or room not found
        400: Training cannot be started (invalid room, stat maxed, etc.)
        409: Dweller already training
    """
    # Verify dweller belongs to user's vault
    dweller = await dweller_crud.get(db_session, dweller_id)
    if not dweller:
        raise HTTPException(status_code=404, detail="Dweller not found")

    await get_user_vault_or_403(dweller.vault_id, user, db_session)

    # Verify room belongs to user's vault
    room = await room_crud.get(db_session, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.vault_id != dweller.vault_id:
        raise HTTPException(status_code=403, detail="Room does not belong to your vault")

    try:
        return await training_service.start_training(db_session, dweller_id, room_id)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ResourceConflictException as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except VaultOperationException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/dweller/{dweller_id}", response_model=TrainingRead | None)
async def get_dweller_training(
    dweller_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Get current active training for a dweller.

    Args:
        dweller_id: Dweller ID
        user: Current authenticated user
        db_session: Database session

    Returns:
        Active training session or None
    """
    # Verify dweller belongs to user's vault
    dweller = await dweller_crud.get(db_session, dweller_id)
    if not dweller:
        raise HTTPException(status_code=404, detail="Dweller not found")

    await get_user_vault_or_403(dweller.vault_id, user, db_session)

    return await crud_training.training.get_active_by_dweller(db_session, dweller_id)


@router.get("/vault/{vault_id}", response_model=list[TrainingRead])
async def list_vault_training(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    List all active training sessions in a vault.

    Args:
        vault_id: Vault ID
        user: Current authenticated user
        db_session: Database session

    Returns:
        List of active training sessions
    """
    await get_user_vault_or_403(vault_id, user, db_session)

    return await crud_training.training.get_active_by_vault(db_session, vault_id)


@router.get("/{training_id}", response_model=TrainingProgress)
async def get_training(
    training_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Get training details with current progress.

    Args:
        training_id: Training session ID
        user: Current authenticated user
        db_session: Database session

    Returns:
        Training session with progress information
    """
    training = await crud_training.training.get(db_session, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training session not found")

    # Verify training belongs to user's vault
    await get_user_vault_or_403(training.vault_id, user, db_session)

    # Update progress before returning
    training = await training_service.update_training_progress(db_session, training)

    # Convert to TrainingProgress response
    return TrainingProgress(
        **training.model_dump(),
        progress_percentage=training.progress_percentage(),
        time_remaining_seconds=training.time_remaining_seconds(),
        is_ready_to_complete=training.is_ready_to_complete(),
    )


@router.post("/{training_id}/cancel", response_model=TrainingRead)
async def cancel_training(
    training_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Cancel an active training session.

    Args:
        training_id: Training session ID
        user: Current authenticated user
        db_session: Database session

    Returns:
        Cancelled training session

    Raises:
        404: Training not found
        400: Training not active
    """
    training = await crud_training.training.get(db_session, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training session not found")

    # Verify training belongs to user's vault
    await get_user_vault_or_403(training.vault_id, user, db_session)

    try:
        return await training_service.cancel_training(db_session, training_id)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except VaultOperationException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/room/{room_id}", response_model=list[TrainingRead])
async def list_room_training(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    List all active training sessions in a room.

    Args:
        room_id: Room ID
        user: Current authenticated user
        db_session: Database session

    Returns:
        List of active training sessions in the room
    """
    # Verify room belongs to user's vault
    room = await room_crud.get(db_session, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    await get_user_vault_or_403(room.vault_id, user, db_session)

    return await crud_training.training.get_active_by_room(db_session, room_id)
