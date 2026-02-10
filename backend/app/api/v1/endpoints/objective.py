from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.db.session import get_async_session
from app.models.objective import Objective, ObjectiveBase
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.common import ObjectiveKindEnum
from app.schemas.objective import ObjectiveCreate, ObjectiveRead
from app.services.chat_service import chat_service

router = APIRouter()


@router.get("/generate", response_model=list[ObjectiveBase])
async def generate_objectives(
    objective_kind: ObjectiveKindEnum,
    objective_count: int = 3,
):
    """Generate game objectives using AI."""
    try:
        return await chat_service.generate_objectives(
            objective_kind=objective_kind,
            objective_count=objective_count,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Failed to generate objectives") from e


@router.post("/{vault_id}/", response_model=Objective)
async def create_objective(
    objective_data: ObjectiveCreate, vault_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    return await crud.objective_crud.create_for_vault(db_session, vault_id, objective_data)


@router.get("/{vault_id}/", response_model=list[ObjectiveRead])
async def read_objective_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    vault_id: UUID4,
    skip: int = 0,
    limit: int = 100,
):
    return await crud.objective_crud.get_multi_for_vault(db_session, vault_id, skip=skip, limit=limit)


@router.get("/{objective_id}", response_model=ObjectiveRead)
async def read_objective(objective_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.objective_crud.get(db_session, objective_id)


@router.post("/{vault_id}/{objective_id}/complete", response_model=Objective)
async def complete_objective(
    vault_id: UUID4, objective_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    """Mark an objective as completed for a vault."""
    return await crud.objective_crud.complete(db_session=db_session, objective_id=objective_id, vault_id=vault_id)


@router.post("/{vault_id}/{objective_id}/progress")
async def update_objective_progress(
    vault_id: UUID4,
    objective_id: UUID4,
    progress: int,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Update the progress of an objective for a vault."""
    return await crud.objective_crud.update_progress(
        db_session=db_session, objective_id=objective_id, vault_id=vault_id, progress=progress
    )


@router.post("/{vault_id}/assign-random")
async def assign_random_objectives(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    count: int = 5,
):
    """Assign random available objectives to a vault (for testing/debugging)."""
    # Get objectives not already assigned to this vault
    query = select(Objective.id).join(VaultObjectiveProgressLink).where(VaultObjectiveProgressLink.vault_id == vault_id)
    assigned = await db_session.execute(query)
    assigned_ids = set(assigned.scalars().all())

    # Get unassigned objectives
    all_objectives = await crud.objective_crud.get_multi(db_session, skip=0, limit=100)
    unassigned = [o for o in all_objectives if o.id not in assigned_ids]

    # Assign up to 'count' objectives
    assigned_count = 0
    for objective in unassigned[:count]:
        link = VaultObjectiveProgressLink(
            vault_id=vault_id,
            objective_id=objective.id,
            progress=0,
            total=objective.target_amount or 1,
            is_completed=False,
        )
        db_session.add(link)
        assigned_count += 1

    await db_session.commit()
    return {"assigned": assigned_count, "message": f"Assigned {assigned_count} objectives to vault"}
