"""API endpoints for the world map."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_user_vault_or_403
from app.db.session import get_async_session
from app.models.vault import Vault
from app.schemas.wasteland_location import VaultMapResponse, WastelandLocationWithDwellers
from app.services.map_service import map_service

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
    return await map_service.get_location_detail(db_session, vault, location_id)
