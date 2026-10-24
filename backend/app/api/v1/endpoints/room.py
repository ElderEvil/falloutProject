"""Room endpoints."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import (
    CurrentActiveUser,
    CurrentSuperuser,
    PaginationParams,
    get_user_vault_or_403,
    verify_room_access,
)
from app.db.session import get_async_session
from app.models.room import Room
from app.schemas.barbershop import BarbershopChangeRequest, BarbershopChangeResponse, BarbershopStatus
from app.schemas.grid import GridConfig, grid_config
from app.schemas.room import RoomBuild, RoomCreateWithoutVaultID, RoomMerge, RoomRead, RoomStyleUpdate
from app.schemas.room_rush import RoomRushQuote, RoomRushResult
from app.services.barbershop_service import barbershop_service
from app.services.room_remodel_service import remodel_room
from app.services.room_rush_service import room_rush_service
from app.services.room_service import room_service
from app.utils.exceptions import ValidationException

router = APIRouter(prefix="/rooms", tags=["Room"])


@router.get("/grid-config/", response_model=GridConfig)
async def read_grid_config(_: CurrentActiveUser) -> GridConfig:
    """Grid geometry for the vault view; the backend owns the unit layout."""
    return grid_config()


@router.get("/", response_model=list[RoomRead])
async def read_room_list(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
    pagination: PaginationParams,
) -> Sequence[Room]:
    """Retrieve a paginated list of rooms.

    Returns:
        List of rooms.
    """
    return await crud.room.get_multi(db_session, skip=pagination.skip, limit=pagination.limit)


@router.get("/vault/{vault_id}/", response_model=list[RoomRead])
async def read_rooms_by_vault(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    vault_id: UUID4,
    user: CurrentActiveUser,
    pagination: PaginationParams,
) -> Sequence[Room]:
    """Retrieve rooms for a specific vault.

    Returns:
        List of rooms in the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.room.get_multy_by_vault(
        db_session=db_session, skip=pagination.skip, limit=pagination.limit, vault_id=vault_id
    )


@router.get("/{room_id}", response_model=RoomRead)
async def read_room(
    room_id: UUID4, user: CurrentActiveUser, db_session: Annotated[AsyncSession, Depends(get_async_session)]
) -> Room:
    """Retrieve a room by ID.

    Returns:
        The requested room.
    """
    await verify_room_access(room_id, user, db_session)
    return await crud.room.get(db_session, room_id)


@router.get("/{room_id}/rush", response_model=RoomRushQuote)
async def read_room_rush_quote(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> RoomRushQuote:
    """Return the server-computed risk and payout for a room rush."""
    await verify_room_access(room_id, user, db_session)
    room = await crud.room.get(db_session, room_id)
    vault = await crud.vault.get_or_none(db_session, room.vault_id)
    if vault is None:
        raise ValidationException("Vault not found.")
    return await room_rush_service.quote(db_session, room, vault)


@router.post("/{room_id}/rush", response_model=RoomRushResult)
async def rush_room(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> RoomRushResult:
    """Execute one server-resolved Room Rush."""
    await verify_room_access(room_id, user, db_session)
    room = await crud.room.get(db_session, room_id)
    vault = await crud.vault.get_or_none(db_session, room.vault_id)
    if vault is None:
        raise ValidationException("Vault not found.")
    return await room_rush_service.rush(db_session, room, vault)


@router.get("/{room_id}/barbershop", response_model=BarbershopStatus)
async def read_barbershop_status(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> BarbershopStatus:
    """Return the Barbershop's availability, fee, and preset swatches."""
    await verify_room_access(room_id, user, db_session)
    room = await crud.room.get(db_session, room_id)
    return await barbershop_service.get_status_for_room(db_session, room)


@router.post("/{room_id}/barbershop/dwellers/{dweller_id}", response_model=BarbershopChangeResponse)
async def change_dweller_appearance(
    room_id: UUID4,
    dweller_id: UUID4,
    request: BarbershopChangeRequest,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> BarbershopChangeResponse:
    """Change a human adult's skin tone and hair color for the Barbershop fee."""
    await verify_room_access(room_id, user, db_session)
    room = await crud.room.get(db_session, room_id)
    return await barbershop_service.change_appearance(
        db_session,
        room=room,
        dweller_id=dweller_id,
        request=request,
    )


@router.get("/buildable/{vault_id}/", response_model=list[RoomCreateWithoutVaultID])
async def get_buildable_rooms(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[RoomCreateWithoutVaultID]:
    """Get list of rooms that can be built in a vault.

    Filters out:
    - Vault door (never buildable by user)
    - Unique rooms that are already built in this vault

    Returns:
        List of buildable room definitions.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await room_service.get_buildable_rooms(db_session, vault_id)


@router.post("/build/", response_model=RoomRead)
async def build_room(
    room_request: RoomBuild,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Room:
    """Build a new room in a vault.

    Returns:
        The built room.
    """
    await get_user_vault_or_403(room_request.vault_id, user, db_session)
    return await room_service.build_room(db_session, room_request)


@router.delete("/destroy/{room_id}", status_code=204)
async def destroy_room(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> None:
    """Destroy a room in a vault."""
    await verify_room_access(room_id, user, db_session)
    await room_service.destroy_room(db_session, room_id)


@router.post("/upgrade/{room_id}", response_model=RoomRead)
async def upgrade_room(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Room:
    """Upgrade a room to the next level.

    Returns:
        The upgraded room.
    """
    await verify_room_access(room_id, user, db_session)
    return await room_service.upgrade_room(db_session, room_id)


@router.post("/style/{room_id}", response_model=RoomRead)
async def apply_room_style(
    room_id: UUID4,
    request: RoomStyleUpdate,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Room:
    """Apply a cosmetic room style (for example, the Party theme)."""
    await verify_room_access(room_id, user, db_session)
    return await room_service.apply_room_style(db_session, room_id, request.style)


@router.post("/split/{room_id}", response_model=list[RoomRead])
async def split_room(
    room_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[Room]:
    """Split a merged room into its base segments without charging caps."""
    await verify_room_access(room_id, user, db_session)
    return await remodel_room(db_session, room_id)


@router.post("/merge/{room_id}", response_model=RoomRead)
async def merge_rooms(
    room_id: UUID4,
    request: RoomMerge,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Room:
    """Merge two explicitly chosen adjacent rooms."""
    await verify_room_access(room_id, user, db_session)
    await verify_room_access(request.other_room_id, user, db_session)
    return (await remodel_room(db_session, room_id, request.other_room_id))[0]
