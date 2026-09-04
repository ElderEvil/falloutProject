"""Service for room operations: build, destroy, upgrade, and queries."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.schemas.room import RoomBuild, RoomCreate, RoomRead
from app.services.user_service import user_service
from app.utils.exceptions import (
    InsufficientResourcesException,
    NoSpaceAvailableException,
    UniqueRoomViolationException,
    VaultOperationException,
)
from app.utils.static_data import game_data_store

logger = logging.getLogger(__name__)


class RoomService:
    """Service for room operations."""

    async def build_room(
        self,
        db_session: AsyncSession,
        room_request: RoomBuild,
    ) -> RoomRead:
        """Build a new room in a vault.

        Args:
            db_session: Database session
            room_request: Requested template and placement

        Returns:
            Created room

        Raises:
            InsufficientResourcesException: If vault lacks resources
            NoSpaceAvailableException: If no space for the room
            UniqueRoomViolationException: If unique room already exists
            VaultOperationException: On other build failures
        """
        try:
            room_template = game_data_store.get_room(room_request.room_name)
            if room_template is None or room_template.name.lower() == "vault door":
                raise VaultOperationException(detail=f"Room cannot be built: {room_request.room_name}")
            room_data = RoomCreate(
                **room_template.model_dump()
                | {
                    "vault_id": room_request.vault_id,
                    "size": room_template.size_min,
                    "coordinate_x": room_request.coordinate_x,
                    "coordinate_y": room_request.coordinate_y,
                }
            )
            room, created = await crud.room.build(db_session=db_session, obj_in=room_data, include_created=True)
        except (InsufficientResourcesException, NoSpaceAvailableException, UniqueRoomViolationException):
            raise
        except ValueError as e:
            raise VaultOperationException(detail=str(e)) from e
        else:
            if created:
                await user_service.record_vault_statistic(db_session, room.vault_id, "total_rooms_built")
            return room

    async def destroy_room(
        self,
        db_session: AsyncSession,
        room_id: UUID4,
    ) -> RoomRead:
        """Destroy a room and refund a portion of its cost.

        Args:
            db_session: Database session
            room_id: Room ID to destroy

        Returns:
            Destroyed room data

        Raises:
            ResourceNotFoundException: If room not found
            VaultOperationException: If room cannot be destroyed (vault door, elevator dependency)
        """
        try:
            return await crud.room.destroy(db_session=db_session, id=room_id)
        except ValueError as e:
            raise VaultOperationException(detail=str(e)) from e

    async def upgrade_room(
        self,
        db_session: AsyncSession,
        room_id: UUID4,
    ) -> RoomRead:
        """Upgrade a room to the next tier.

        Args:
            db_session: Database session
            room_id: Room ID to upgrade

        Returns:
            Upgraded room

        Raises:
            ResourceNotFoundException: If room not found
            InsufficientResourcesException: If vault lacks caps
            VaultOperationException: On other upgrade failures
        """
        try:
            return await crud.room.upgrade(db_session=db_session, room_id=room_id)
        except ValueError as e:
            raise VaultOperationException(detail=str(e)) from e

    async def get_buildable_rooms(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list:
        """Get list of rooms that can be built in a vault.

        Filters out vault doors and unique rooms already built.

        Args:
            db_session: Database session
            vault_id: Vault ID

        Returns:
            List of buildable room specs
        """
        from app.api.game_data_deps import get_static_game_data

        data_store = await get_static_game_data()
        existing_room_names = await crud.room.get_existing_room_names(db_session=db_session, vault_id=vault_id)
        return data_store.get_buildable_rooms(existing_room_names)


# Singleton instance
room_service = RoomService()
