from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.api.deps import get_static_game_data
from app.db.session import get_async_session
from app.schemas.junk import JunkRead
from app.schemas.outfit import OutfitCreate, OutfitRead, OutfitUpdate

router = APIRouter()


@router.post("/", response_model=OutfitRead)
async def create_outfit(outfit_data: OutfitCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.create(db_session, outfit_data)


@router.get("/", response_model=list[OutfitRead])
async def read_outfit_list(skip: int = 0, limit: int = 100, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{outfit_id}", response_model=OutfitRead)
async def read_outfit(outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.get(db_session, outfit_id)


@router.put("/{outfit_id}", response_model=OutfitRead)
async def update_outfit(
    outfit_id: UUID4,
    outfit_data: OutfitUpdate,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await crud.outfit.update(db_session, outfit_id, outfit_data)


@router.delete("/{outfit_id}", status_code=204)
async def delete_outfit(outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.delete(db_session, outfit_id)


@router.post("/{outfit_id}/equip/", response_model=OutfitRead)
async def equip_outfit(outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.equip(db_session, outfit_id)


@router.post("/{outfit_id}/unequip/", status_code=200)
async def unequip_outfit(outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.unequip(db_session, outfit_id)


@router.post("/{outfit_id}/scrap/", response_model=list[JunkRead] | None)
async def scrap_outfit(outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.scrap(db_session, outfit_id)


@router.post("/{outfit_id}/sell/", status_code=204)
async def sell_outfit(outfit_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.outfit.sell(db_session, outfit_id)


@router.get("/read_data/", response_model=list[OutfitCreate])
async def read_outfits_data(data_store=Depends(get_static_game_data)):
    return data_store.outfits
