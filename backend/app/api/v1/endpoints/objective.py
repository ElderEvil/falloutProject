from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.db.session import get_async_session
from app.models.objective import Objective
from app.schemas.objective import ObjectiveCreate, ObjectiveRead

router = APIRouter()


@router.post("/{vault_id}/", response_model=Objective)
async def create_objective(
    objective_data: ObjectiveCreate, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    return await crud.objective_crud.create(db_session, objective_data)


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


@router.post("/{vault_id}/{objective_id}/complete", response_model=ObjectiveRead)
async def complete_objective(
    vault_id: UUID4, objective_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    return await crud.objective_crud.complete(db_session=db_session, quest_entity_id=objective_id, vault_id=vault_id)
