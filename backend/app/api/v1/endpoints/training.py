"""Training endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.crud import training as crud_training
from app.db.session import get_async_session
from app.schemas.training import TrainingProgress, TrainingRead
from app.services.training_service import training_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, VaultOperationException

router = APIRouter(prefix="/training", tags=["Training"])


@router.post("/start", response_model=TrainingRead, status_code=201)
async def start_training(
    dweller_id: Annotated[UUID4, Query()],
    room_id: Annotated[UUID4, Query()],
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TrainingRead:
    """Start training a dweller in a training room.

    Returns:
        Created training session.

    Raises:
        HTTPException: 404 if dweller or room not found.
        HTTPException: 400 if training cannot be started.
        HTTPException: 409 if dweller already training.
    """
    from app.crud.dweller import dweller as dweller_crud

    dweller = await dweller_crud.get(db_session, dweller_id)
    await get_user_vault_or_403(dweller.vault_id, user, db_session)

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
) -> TrainingRead | None:
    """Get current active training for a dweller.

    Returns:
        Active training session or None.
    """
    training = await crud_training.training.get_active_by_dweller(db_session, dweller_id)

    if training:
        await get_user_vault_or_403(training.vault_id, user, db_session)

    return training


@router.get("/vault/{vault_id}", response_model=list[TrainingRead])
async def list_vault_training(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[TrainingRead]:
    """List all active training sessions in a vault.

    Returns:
        List of active training sessions.
    """
    await get_user_vault_or_403(vault_id, user, db_session)

    return await crud_training.training.get_active_by_vault(db_session, vault_id)


@router.get("/{training_id}", response_model=TrainingProgress)
async def get_training(
    training_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TrainingProgress:
    """Get training details with current progress.

    Returns:
        Training session with progress information.

    Raises:
        HTTPException: 404 if training session not found.
    """
    training = await crud_training.training.get(db_session, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training session not found")

    # Verify training belongs to user's vault
    await get_user_vault_or_403(training.vault_id, user, db_session)

    # Update progress before returning
    training = await training_service.update_training_progress(db_session, training)

    return TrainingProgress(
        **training.model_dump(),
        progress_percentage=training.progress_percentage(),
        time_remaining_seconds=training.time_remaining_seconds(),
        is_ready_to_complete=training.is_ready_to_complete(),
    )


@router.post("/{training_id}/complete", response_model=TrainingRead)
async def complete_training(
    training_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TrainingRead:
    """Complete an active training session and increase the dweller's SPECIAL stat.

    Returns:
        Completed training session.

    Raises:
        HTTPException: 404 if training not found.
        HTTPException: 400 if training not active or already completed.
    """
    training = await crud_training.training.get(db_session, training_id)
    if not training:
        raise HTTPException(status_code=404, detail="Training session not found")

    # Verify training belongs to user's vault
    await get_user_vault_or_403(training.vault_id, user, db_session)

    try:
        return await training_service.complete_training(db_session, training_id)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except VaultOperationException as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{training_id}/cancel", response_model=TrainingRead)
async def cancel_training(
    training_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> TrainingRead:
    """Cancel an active training session.

    Returns:
        Cancelled training session.

    Raises:
        HTTPException: 404 if training not found.
        HTTPException: 400 if training not active.
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
) -> list[TrainingRead]:
    """List all active training sessions in a room.

    Returns:
        List of active training sessions in the room.
    """
    trainings = await crud_training.training.get_active_by_room(db_session, room_id)

    if trainings:
        # Verify room belongs to user's vault (check via first training's vault)
        await get_user_vault_or_403(trainings[0].vault_id, user, db_session)

    return trainings
