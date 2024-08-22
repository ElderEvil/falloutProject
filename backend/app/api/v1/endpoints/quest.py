from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.db.session import get_async_session
from app.schemas.quest import (
    QuestChainReadWithQuests,
    QuestCreate,
    QuestRead,
    QuestReadWithObjectives,
    QuestUpdate,
)

router = APIRouter()


@router.post("/", response_model=QuestRead)
async def create_quest(quest_data: QuestCreate, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.quest_crud.create(db_session, quest_data)


@router.get("/", response_model=list[QuestRead])
async def read_quest_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
):
    return await crud.quest_crud.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{quest_id}", response_model=QuestReadWithObjectives)
async def read_quest(quest_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.quest_crud.get(db_session, quest_id)


@router.put("/{quest_id}", response_model=QuestRead)
async def update_quest(
    quest_id: UUID4,
    quest_data: QuestUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await crud.quest_crud.update(db_session, quest_id, quest_data)


@router.delete("/{quest_id}", status_code=204)
async def delete_quest(quest_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.quest_crud.delete(db_session, quest_id)


@router.get("/{vault_id}/chains", response_model=list[QuestChainReadWithQuests])
async def read_quest_chain_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    vault_id: UUID4,
    skip: int = 0,
    limit: int = 100,
):
    return await crud.quest_chain_crud.get_multi_for_vault(
        skip=skip, limit=limit, db_session=db_session, vault_id=vault_id
    )
