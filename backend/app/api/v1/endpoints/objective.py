from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.db.session import get_async_session
from app.models.quest import QuestObjective
from app.schemas.quest import QuestObjectiveCreate

router = APIRouter()


@router.post("/{vault_id}/", response_model=QuestObjective)
async def create_objective(objective_data: QuestObjectiveCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.objective_crud.create(db_session, objective_data)


@router.get("/{vault_id}/", response_model=list[QuestObjective])
async def read_objective_list(skip: int = 0, limit: int = 100, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.objective_crud.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{vault_id}/{objective_id}", response_model=QuestObjective)
async def read_objective(objective_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.objective_crud.get(db_session, objective_id)


@router.post("/{vault_id}/{objective_id}/complete", response_model=QuestObjective)
async def complete_objective(
    vault_id: UUID4, objective_id: UUID4, db_session: AsyncSession = Depends(get_async_session)
):
    return await crud.objective_crud.complete(db_session=db_session, quest_entity_id=objective_id, vault_id=vault_id)
