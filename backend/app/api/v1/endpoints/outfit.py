from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.game_data_deps import get_static_game_data
from app.db.session import get_async_session
from app.schemas.junk import JunkRead
from app.schemas.outfit import OutfitCreate, OutfitRead, OutfitUpdate

router = APIRouter()


@router.post("/", response_model=OutfitRead)
async def create_outfit(outfit_data: OutfitCreate, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.outfit.create(db_session, outfit_data)


@router.get("/", response_model=list[OutfitRead])
async def read_outfit_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    skip: int = 0,
    limit: int = 100,
    vault_id: UUID4 | None = None,
):
    """Get outfits, optionally filtered by vault."""
    if vault_id:
        # Filter by vault: items in vault's storage OR equipped by vault's dwellers
        from sqlmodel import or_, select

        from app.models.dweller import Dweller
        from app.models.storage import Storage

        # Subqueries for vault's storage and dwellers
        storage_subquery = select(Storage.id).where(Storage.vault_id == vault_id).scalar_subquery()
        dweller_subquery = select(Dweller.id).where(Dweller.vault_id == vault_id).scalar_subquery()

        query = (
            select(crud.outfit.model)
            .where(
                or_(
                    crud.outfit.model.storage_id.in_(storage_subquery),
                    crud.outfit.model.dweller_id.in_(dweller_subquery),
                )
            )
            .offset(skip)
            .limit(limit)
        )
        result = await db_session.execute(query)
        return result.scalars().all()

    return await crud.outfit.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{outfit_id}", response_model=OutfitRead)
async def read_outfit(outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.outfit.get(db_session, outfit_id)


@router.put("/{outfit_id}", response_model=OutfitRead)
async def update_outfit(
    outfit_id: UUID4,
    outfit_data: OutfitUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await crud.outfit.update(db_session, outfit_id, outfit_data)


@router.delete("/{outfit_id}", status_code=204)
async def delete_outfit(outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.outfit.delete(db_session, outfit_id)


@router.post("/{dweller_id}/equip/{outfit_id}", response_model=OutfitRead)
async def equip_outfit(
    dweller_id: UUID4, outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]
):
    return await crud.outfit.equip(db_session=db_session, item_id=outfit_id, dweller_id=dweller_id)


@router.post("/{outfit_id}/unequip/", status_code=200)
async def unequip_outfit(outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.outfit.unequip(db_session=db_session, item_id=outfit_id)


@router.post("/{outfit_id}/scrap/", response_model=dict[str, list[JunkRead]] | None)
async def scrap_outfit(outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    junk_list = await crud.outfit.scrap(db_session=db_session, item_id=outfit_id)
    return {"junk": junk_list}


@router.post("/{outfit_id}/sell/", status_code=200)
async def sell_outfit(outfit_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.outfit.sell(db_session=db_session, item_id=outfit_id)


@router.get("/read_data/", response_model=list[OutfitCreate])
async def read_outfits_data(data_store=Depends(get_static_game_data)):
    return data_store.outfits
