"""API endpoints for the world map."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.vault import Vault
from app.schemas.wasteland_location import VaultMapResponse, WastelandLocationWithDwellers
from app.schemas.world_snapshot import WorldSnapshotRead
from app.services.map_service import map_service
from app.services.world_snapshot_service import world_snapshot_service

router = APIRouter(prefix="/map", tags=["Map"])


@router.get("/world", response_model=WorldSnapshotRead)
async def get_world_snapshot(
    _user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WorldSnapshotRead:
    """Return the shared backend-generated base world (authenticated, public snapshot).

    Terrain, land-safe slots and background roads — never ownership, discoveries,
    or expedition state. Existing snapshots are only read, never regenerated.
    """
    return await world_snapshot_service.read(db_session)


@router.get("/vault/{vault_id}", response_model=VaultMapResponse)
async def get_vault_map(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    unlocked_only: Annotated[bool, Query()] = False,
) -> VaultMapResponse:
    """Return the full world-map for a vault.

    Pass *unlocked_only=True* to hide non-VAULT locations that have no unlocked
    dweller links.  The default (False) returns every location regardless of
    unlock state so the frontend can style locked markers.
    """
    return await map_service.get_vault_map(db_session, vault, unlocked_only=unlocked_only)


@router.get("/vault/{vault_id}/locations/{location_id}", response_model=WastelandLocationWithDwellers)
async def get_location_detail(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    location_id: UUID,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> WastelandLocationWithDwellers:
    """Return a single location with its linked dweller references."""
    return await map_service.get_location_detail(db_session, vault, location_id)
