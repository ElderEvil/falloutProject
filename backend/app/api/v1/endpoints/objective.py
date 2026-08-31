"""Objective endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentSuperuser
from app.db.session import get_async_session
from app.models.objective import Objective
from app.models.vault import Vault
from app.schemas.objective import ObjectiveCreate, ObjectiveRead
from app.schemas.responses import AssignedResponse
from app.services.objective_assignment_service import ObjectiveAssignmentService

router = APIRouter(prefix="/objectives", tags=["Objective"])


@router.post("/{vault_id}/", response_model=Objective)
async def create_objective(
    objective_data: ObjectiveCreate, vault_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]
) -> Objective:
    """Create an objective for a vault.

    Returns:
        The created objective.
    """
    return await crud.objective_crud.create_for_vault(db_session, vault_id, objective_data)


@router.get("/{vault_id}/", response_model=list[ObjectiveRead])
async def read_objective_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    vault_id: UUID4,
    skip: int = 0,
    limit: int = 100,
) -> list[ObjectiveRead]:
    """Retrieve objectives for a vault.

    Returns:
        List of objectives for the vault.
    """
    return await crud.objective_crud.get_multi_for_vault(db_session, vault_id, skip=skip, limit=limit)


@router.get("/{objective_id}", response_model=ObjectiveRead)
async def read_objective(
    objective_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]
) -> ObjectiveRead:
    """Retrieve an objective by ID.

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
    return await crud.objective_crud.complete(db_session=db_session, objective_id=objective_id, vault_id=vault_id)


@router.post("/{vault_id}/{objective_id}/progress")
async def update_objective_progress(
    vault_id: UUID4,
    objective_id: UUID4,
    progress: int,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Update the progress of an objective for a vault.

    Returns:
        The updated objective.
    """
    return await crud.objective_crud.update_progress(
        db_session=db_session, objective_id=objective_id, vault_id=vault_id, progress=progress
    )


@router.post("/{vault_id}/assign-random")
async def assign_random_objectives(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    count: int = 5,
):
    """Assign random available objectives to a vault (for testing/debugging).

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
