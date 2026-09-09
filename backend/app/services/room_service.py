"""Service for room operations: build, destroy, upgrade, and queries."""

import logging
from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RoomActionEnum
from app.core.game_config import game_config
from app.core.grid_config import GRID_X_MAX, GRID_X_MIN, GRID_Y_MAX, GRID_Y_MIN
from app.schemas.room import RoomBuild, RoomCreate, RoomRead, RoomUpdate
from app.services.event_bus import GameEvent, event_bus
from app.services.user_service import user_service
from app.services.vault_service import vault_service
from app.utils import room_rules
from app.utils.exceptions import (
    InsufficientResourcesException,
    NoSpaceAvailableException,
    UniqueRoomViolationException,
    VaultOperationException,
)
from app.utils.room_assets import get_room_image_url
from app.utils.static_data import game_data_store

if TYPE_CHECKING:
    from app.models.room import Room

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
            room, created = await self._build(db_session=db_session, obj_in=room_data)
        except (InsufficientResourcesException, NoSpaceAvailableException, UniqueRoomViolationException):
            raise
        except ValueError as e:
            raise VaultOperationException(detail=str(e)) from e
        else:
            if created:
                await user_service.record_vault_statistic(db_session, room.vault_id, "total_rooms_built")
            return room

    async def _build(self, *, db_session: AsyncSession, obj_in: RoomCreate) -> tuple[RoomRead, bool]:
        """Build a room from a full create payload, expanding when the same room exists."""
        vault = await crud.vault.get(db_session, id=obj_in.vault_id)

        if obj_in.size_min is None or obj_in.size_min < 1:
            msg = f"Invalid room size: {obj_in.size_min}. Size must be at least 1."
            raise ValueError(msg)

        if obj_in.size_max is None or obj_in.size_min > obj_in.size_max:
            msg = f"Invalid room size: {obj_in.size_min} exceeds maximum size {obj_in.size_max}."
            raise ValueError(msg)

        if obj_in.coordinate_x is None or obj_in.coordinate_y is None:
            msg = "Room coordinates must be specified."
            raise ValueError(msg)

        if obj_in.coordinate_x < GRID_X_MIN or obj_in.coordinate_x > GRID_X_MAX:
            msg = f"Invalid X coordinate: {obj_in.coordinate_x}. Must be between {GRID_X_MIN} and {GRID_X_MAX}."
            raise ValueError(msg)

        max_x = obj_in.coordinate_x + obj_in.size_min - 1
        if max_x > GRID_X_MAX:
            msg = f"Room exceeds grid width: max X {max_x} > {GRID_X_MAX}"
            raise ValueError(msg)

        if obj_in.coordinate_y < GRID_Y_MIN or obj_in.coordinate_y > GRID_Y_MAX:
            msg = f"Invalid Y coordinate: {obj_in.coordinate_y}. Must be between {GRID_Y_MIN} and {GRID_Y_MAX}."
            raise ValueError(msg)

        await room_rules.validate_build_placement(
            db_session,
            vault.id,
            obj_in.name,
            obj_in.coordinate_x,
            obj_in.coordinate_y,
        )

        if obj_in.name.lower() == "vault door":
            existing_names = await crud.room.get_existing_room_names(db_session=db_session, vault_id=vault.id)
            if "vault door" in existing_names:
                raise UniqueRoomViolationException(room_name="Vault Door")

        if not await vault_service.is_enough_dwellers(
            db_session=db_session, vault_id=vault.id, population_required=obj_in.population_required
        ):
            raise InsufficientResourcesException(resource_name="dwellers", resource_amount=obj_in.population_required)

        existing_room = await crud.room.get_room_by_coordinates(
            db_session=db_session, vault_id=vault.id, x_coord=obj_in.coordinate_x, y_coord=obj_in.coordinate_y
        )

        if existing_room:
            if existing_room.name == obj_in.name and existing_room.tier == obj_in.tier:
                room = await crud.room.expand_room(db_session, existing_room, obj_in.size_min)
                return room, False
            raise NoSpaceAvailableException(space_needed=obj_in.size_min)

        room_template = game_data_store.get_room(obj_in.name)
        if room_template:
            obj_in.capacity_formula = room_template.capacity_formula
            obj_in.output_formula = room_template.output_formula

        if obj_in.capacity_formula:
            room_size = obj_in.size if obj_in.size is not None else obj_in.size_min
            obj_in.capacity = crud.room.evaluate_capacity_formula(obj_in.capacity_formula, obj_in.tier, room_size)

        if obj_in.output_formula:
            room_size = obj_in.size if obj_in.size is not None else obj_in.size_min
            obj_in.output = crud.room.evaluate_output_formula(obj_in.output_formula, obj_in.tier, room_size)

        await crud.room.check_is_unique_room(db_session=db_session, obj_in=obj_in)

        price = await crud.room.get_room_build_price(db_session=db_session, room_in=obj_in)
        await vault_service.withdraw_caps(db_session=db_session, vault_obj=vault, amount=price)

        room_size = obj_in.size if obj_in.size is not None else obj_in.size_min
        obj_in.image_url = get_room_image_url(obj_in.name, tier=obj_in.tier, size=room_size)

        obj_in_db: Room = await crud.room.create(db_session, obj_in=obj_in)
        await db_session.refresh(obj_in_db)

        if crud.room.requires_recalculation(obj_in_db):
            await vault_service.recalculate_vault_attributes(
                db_session=db_session, vault_obj=vault, room_obj=obj_in_db, action=RoomActionEnum.BUILD
            )

        await event_bus.emit(
            GameEvent.ROOM_BUILT,
            vault.id,
            {"room_type": obj_in_db.name, "tier": obj_in_db.tier, "room_id": str(obj_in_db.id)},
        )

        return obj_in_db, True

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
            return await self._destroy(db_session, room_id)
        except ValueError as e:
            raise VaultOperationException(detail=str(e)) from e

    async def _destroy(self, db_session: AsyncSession, room_id: UUID4) -> RoomRead:
        room = await crud.room.get(db_session, room_id)
        vault = await crud.vault.get(db_session, id=room.vault_id)

        if room.name.lower() == "vault door":
            msg = "Cannot destroy the vault door. It is a critical structure and must remain in place."
            raise ValueError(msg)

        await room_rules.validate_elevator_destroy(db_session, room)

        db_obj = await crud.room.delete(db_session, id=room_id)

        refundable_total = db_obj.base_cost + (db_obj.incremental_cost or 0)

        if db_obj.tier >= 2 and db_obj.t2_upgrade_cost:
            refundable_total += db_obj.t2_upgrade_cost
        if db_obj.tier >= 3 and db_obj.t3_upgrade_cost:
            refundable_total += db_obj.t3_upgrade_cost

        refund = int(refundable_total * game_config.resource.destroy_room_refund_rate)

        await vault_service.deposit_caps(db_session=db_session, vault_obj=vault, amount=refund, track_earnings=False)

        if crud.room.requires_recalculation(db_obj):
            await vault_service.recalculate_vault_attributes(
                db_session=db_session, vault_obj=vault, room_obj=db_obj, action=RoomActionEnum.DESTROY
            )

        return db_obj

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
            return await self._upgrade(db_session, room_id)
        except ValueError as e:
            raise VaultOperationException(detail=str(e)) from e

    async def _upgrade(self, db_session: AsyncSession, room_id: UUID4) -> RoomRead:
        room = await crud.room.get(db_session, room_id)
        vault = await crud.vault.get(db_session, id=room.vault_id)

        max_tier = room.max_tier

        if room.tier >= max_tier:
            msg = f"Room {room.name} is already at maximum tier {max_tier}"
            raise ValueError(msg)

        if room.tier == 1 and room.t2_upgrade_cost:
            upgrade_cost = room.t2_upgrade_cost
        elif room.tier == 2 and room.t3_upgrade_cost:
            upgrade_cost = room.t3_upgrade_cost
        else:
            msg = f"No upgrade cost defined for room {room.name} at tier {room.tier}"
            raise ValueError(msg)

        await vault_service.withdraw_caps(db_session=db_session, vault_obj=vault, amount=upgrade_cost)

        old_tier = room.tier
        room.tier += 1

        new_capacity = None
        new_output = None

        if room.capacity is not None:
            tier_ratio = (room.tier + 4) / (old_tier + 4)
            new_capacity = int(room.capacity * tier_ratio)

        if room.output is not None:
            tier_ratio = (room.tier + 4) / (old_tier + 4)
            new_output = int(room.output * tier_ratio)

        room_size = room.size if room.size is not None else room.size_min
        new_image_url = get_room_image_url(room.name, tier=room.tier, size=room_size)

        await crud.room.update(
            db_session=db_session,
            obj_in=RoomUpdate(tier=room.tier, capacity=new_capacity, output=new_output, image_url=new_image_url),
            id=room.id,
        )

        room.capacity = new_capacity
        room.output = new_output

        if crud.room.requires_recalculation(room):
            await vault_service.recalculate_vault_attributes(
                db_session=db_session, vault_obj=vault, room_obj=room, action=RoomActionEnum.UPGRADE
            )

        await event_bus.emit(
            GameEvent.ROOM_UPGRADED,
            vault.id,
            {"room_type": room.name, "from_tier": old_tier, "to_tier": room.tier, "room_id": str(room.id)},
        )

        await db_session.refresh(room)
        return room

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
