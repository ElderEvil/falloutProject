from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser
from app.db.session import get_async_session
from app.schemas.quest import (
    QuestCreate,
    QuestRead,
    QuestUpdate,
)

router = APIRouter()


@router.post("/{vault_id}/", response_model=QuestRead)
async def create_quest(
    quest_data: QuestCreate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
):
    return await crud.quest_crud.create(db_session, quest_data)


@router.get("/{vault_id}/", response_model=list[QuestRead])
async def read_quest_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,  # noqa: ARG001
    skip: int = 0,
    limit: int = 100,
):
    return await crud.quest_crud.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{vault_id}/{quest_id}", response_model=QuestRead)
async def read_quest(
    quest_id: UUID4,
    user: CurrentActiveUser,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await crud.quest_crud.get_for_vault(db_session=db_session, quest_id=quest_id, vault_id=vault_id, user=user)


@router.put("/{vault_id}/{quest_id}", response_model=QuestRead)
async def update_quest(
    quest_id: UUID4,
    quest_data: QuestUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await crud.quest_crud.update(db_session, quest_id, quest_data)


@router.delete("/{vault_id}/{quest_id}", status_code=204)
async def delete_quest(quest_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.quest_crud.delete(db_session, quest_id)
