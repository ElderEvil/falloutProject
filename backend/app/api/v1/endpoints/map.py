"""API endpoints for the world map."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_user_vault_or_403
from app.crud.wasteland_location import wasteland_location as wl_crud
from app.db.session import get_async_session
from app.models.vault import Vault
from app.models.wasteland_location import WastelandLocation
from app.schemas.wasteland_location import VaultMapResponse, WastelandLocationWithDwellers
from app.services.map_service import map_service
from app.utils.exceptions import ResourceNotFoundException

router = APIRouter(prefix="/map", tags=["Map"])


@router.get("/vault/{vault_id}", response_model=VaultMapResponse)
async def get_vault_map(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> VaultMapResponse:
    """Return the full world-map for a vault."""
    return await map_service.get_vault_map(db_session, vault)


@router.get("/vault/{vault_id}/locations/{location_id}", response_model=WastelandLocationWithDwellers)
async def get_location_detail(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    location_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WastelandLocationWithDwellers:
    """Return a single location with its linked dweller references."""
    location = await wl_crud.get_by_id(db_session, location_id)
    if location is None or location.vault_id != vault.id:
        raise ResourceNotFoundException(WastelandLocation, identifier=location_id)

    refs_map = await wl_crud.get_dweller_refs(db_session, [location.id])
    refs = refs_map.get(location.id, [])

    return WastelandLocationWithDwellers(
        id=location.id,
        name=location.name,
        normalized_name=location.normalized_name,
        type=location.type,
        coord_x=location.coord_x,
        coord_y=location.coord_y,
        description=location.description,
        vault_id=location.vault_id,
        exploration_id=location.exploration_id,
        created_at=location.created_at,
        dwellers=refs,
    )
