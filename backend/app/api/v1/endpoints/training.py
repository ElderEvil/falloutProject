"""Training endpoints."""

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentActiveUser, DBSession, get_user_vault_or_403
from app.models.training import Training
from app.schemas.training import TrainingGoalUpdate, TrainingProgress, TrainingRead
from app.services.dweller_service import dweller_service
from app.services.training_service import training_service

router = APIRouter(prefix="/training", tags=["Training"])


@router.post("/start", response_model=TrainingRead, status_code=201)
async def start_training(
    dweller_id: Annotated[UUID, Query()],
    room_id: Annotated[UUID, Query()],
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Training:
    """Start training a dweller in a training room.

    Returns:
        Created training session.

    Raises:
        HTTPException: 404 if dweller or room not found.
        HTTPException: 400 if training cannot be started.
        HTTPException: 409 if dweller already training.
    """
    dweller = await dweller_service.get_dweller(db_session, dweller_id)
    await get_user_vault_or_403(dweller.vault_id, user, db_session)

    return await training_service.start_training(db_session, dweller_id, room_id)


@router.get("/dweller/{dweller_id}", response_model=TrainingRead | None)
async def get_dweller_training(
    dweller_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Training | None:
    """Get current active training for a dweller.

    Returns:
        Active training session or None.
    """
    training = await training_service.get_active_training_for_dweller(db_session, dweller_id)

    if training:
        await get_user_vault_or_403(training.vault_id, user, db_session)

    return training


@router.get("/vault/{vault_id}", response_model=list[TrainingRead])
async def list_vault_training(
    vault_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Sequence[Training]:
    """List all active training sessions in a vault.

    Returns:
        List of active training sessions.
    """
    await get_user_vault_or_403(vault_id, user, db_session)

    return await training_service.list_active_trainings_for_vault(db_session, vault_id)


@router.get("/{training_id}", response_model=TrainingProgress)
async def get_training(
    training_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> TrainingProgress:
    """Get training details with current progress.

    Returns:
        Training session with progress information.

    Raises:
        HTTPException: 404 if training session not found.
    """
    training = await training_service.get_training(db_session, training_id)

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
    training_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Training:
    """Complete an active training session and increase the dweller's SPECIAL stat.

    Returns:
        Completed training session.

    Raises:
        HTTPException: 404 if training not found.
        HTTPException: 400 if training not active or already completed.
    """
    training = await training_service.get_training(db_session, training_id)

    # Verify training belongs to user's vault
    await get_user_vault_or_403(training.vault_id, user, db_session)

    return await training_service.complete_training(db_session, training_id)


@router.post("/{training_id}/cancel", response_model=TrainingRead)
async def cancel_training(
    training_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Training:
    """Cancel an active training session.

    Returns:
        Cancelled training session.

    Raises:
        HTTPException: 404 if training not found.
        HTTPException: 400 if training not active.
    """
    training = await training_service.get_training(db_session, training_id)

    # Verify training belongs to user's vault
    await get_user_vault_or_403(training.vault_id, user, db_session)

    return await training_service.cancel_training(db_session, training_id)


@router.get("/room/{room_id}", response_model=list[TrainingRead])
async def list_room_training(
    room_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Sequence[Training]:
    """List all active training sessions in a room.

    Returns:
        List of active training sessions in the room.
    """
    trainings = await training_service.list_active_trainings_for_room(db_session, room_id)

    if trainings:
        # Verify room belongs to user's vault (check via first training's vault)
        await get_user_vault_or_403(trainings[0].vault_id, user, db_session)

    return trainings


@router.patch("/{training_id}/goal", response_model=TrainingRead)
async def set_training_goal(
    training_id: UUID,
    goal: TrainingGoalUpdate,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> Training:
    """Set a dweller's goal for the current training chain."""
    training = await training_service.get_training(db_session, training_id)
    await get_user_vault_or_403(training.vault_id, user, db_session)
    return await training_service.set_training_goal(db_session, training_id, goal.goal_stat_value)
