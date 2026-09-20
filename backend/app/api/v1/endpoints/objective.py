"""Objective endpoints."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_current_active_user, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.objective import Objective
from app.models.vault import Vault
from app.schemas.objective import ObjectiveCreate, ObjectiveRead
from app.schemas.responses import AssignedResponse
from app.services.progression.objectives.assignment import ObjectiveAssignmentService
from app.services.reward_service import reward_service

router = APIRouter(prefix="/objectives", tags=["Objective"], dependencies=[Depends(get_current_active_user)])


@router.post("/{vault_id}/", response_model=Objective)
async def create_objective(
    objective_data: ObjectiveCreate,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Objective:
    """Create an objective for a vault (administrators only).

    Returns:
        The created objective.
    """
    return await crud.objective_crud.create_for_vault(db_session, vault_id, objective_data)


@router.get("/{vault_id}/", response_model=list[ObjectiveRead])
async def read_objective_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    vault_id: UUID4,
    user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[ObjectiveRead]:
    """Retrieve objectives for a vault.

    Returns:
        List of objectives for the vault.

    Raises:
        AccessDeniedException: If the user doesn't own the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.objective_crud.get_multi_for_vault(db_session, vault_id, skip=skip, limit=limit)


@router.get("/{objective_id}", response_model=ObjectiveRead)
async def read_objective(
    objective_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _user: CurrentActiveUser,
) -> Objective:
    """Retrieve an objective template by ID.

    Objectives are global templates; a vault links to them with its own progress,
    so any authenticated caller may read one (vault-scoped lists stay owner-only).

    Returns:
        The requested objective.
    """
    return await crud.objective_crud.get(db_session, objective_id)


@router.post("/{vault_id}/{objective_id}/complete", response_model=Objective)
async def complete_objective(
    vault_id: UUID4,
    objective_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Objective:
    """Manually complete an objective for a vault (administrators only).

    Returns:
        The completed objective.
    """
    return await reward_service.settle_objective_completion(db_session, objective_id, vault_id)


@router.post("/{vault_id}/{objective_id}/progress")
async def update_objective_progress(
    vault_id: UUID4,
    objective_id: UUID4,
    progress: int,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
):
    """Update the progress of an objective for a vault (administrators only).

    Returns:
        The updated objective.
    """
    return await reward_service.settle_objective_progress(db_session, objective_id, vault_id, progress)


@router.post("/{vault_id}/assign-random")
async def assign_random_objectives(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
    count: int = 5,
):
    """Assign random available objectives to a vault (administrators only).

    Returns:
        Response with count of assigned objectives.

    Raises:
        HTTPException: 404 if vault not found.
    """
    # Validate vault exists first to avoid orphan links
    vault = await db_session.get(Vault, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail=f"Vault {vault_id} not found")

    service = ObjectiveAssignmentService(db_session)
    assigned = await service.assign_random_objectives(vault_id, count)
    return AssignedResponse(assigned=len(assigned), message=f"Assigned {len(assigned)} objectives to vault")
