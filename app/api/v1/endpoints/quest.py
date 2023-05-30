from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.base import get_async_session
from app.schemas.quest import QuestCreate, QuestRead, QuestReadWithSteps, QuestUpdate

router = APIRouter()


@router.post("/quests", response_model=QuestRead)
async def create_quest(quest_data: QuestCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.quest.create(db_session, quest_data)


@router.get("/", response_model=list[QuestRead])
async def read_quest_list(skip: int = 0, limit: int = 100, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.quest.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{quest_id}", response_model=QuestReadWithSteps)
async def read_quest(quest_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.quest.get(db_session, quest_id)


@router.put("/{quest_id}", response_model=QuestRead)
async def update_quest(
    quest_id: UUID4,
    quest_data: QuestUpdate,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await crud.quest.update(db_session, quest_id, quest_data)


@router.delete("/{quest_id}", status_code=204)
async def delete_quest(quest_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.quest.delete(db_session, quest_id)
