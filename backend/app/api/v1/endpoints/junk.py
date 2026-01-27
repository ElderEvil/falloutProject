from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.game_data_deps import get_static_game_data
from app.db.session import get_async_session
from app.schemas.junk import JunkCreate, JunkRead, JunkUpdate

router = APIRouter()


@router.post("/", response_model=JunkRead)
async def create_junk(junk_data: JunkCreate, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.junk.create(db_session, junk_data)


@router.get("/", response_model=list[JunkRead])
async def read_junk_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)], skip: int = 0, limit: int = 100
):
    return await crud.junk.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{junk_id}", response_model=JunkRead)
async def read_junk(junk_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.junk.get(db_session, junk_id)


@router.put("/{junk_id}", response_model=JunkRead)
async def update_junk(
    junk_id: UUID4, junk_data: JunkUpdate, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    return await crud.junk.update(db_session, junk_id, junk_data)


@router.delete("/{junk_id}", status_code=204)
async def delete_junk(junk_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.junk.delete(db_session, junk_id)


@router.post("/{junk_id}/sell/", status_code=200)
async def sell_junk(junk_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.junk.sell(db_session=db_session, item_id=junk_id)


@router.get("/read_data/")
async def read_junk_data(data_store=Depends(get_static_game_data)):
    return data_store.junk_items
