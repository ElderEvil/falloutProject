import logging

from pydantic import UUID4
from sqlmodel import and_, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase, ModelType
from app.crud.vault import vault as vault_crud
from app.models.room import Room
from app.schemas.common import RoomActionEnum, RoomTypeEnum
from app.schemas.room import RoomCreate, RoomUpdate
from app.utils.exceptions import InsufficientResourcesException, NoSpaceAvailableException, UniqueRoomViolationException

logger = logging.getLogger(__name__)

DESTROY_ROOM_REWARD = 0.2


class CRUDRoom(CRUDBase[Room, RoomCreate, RoomUpdate]):
    @staticmethod
    async def get_multy_by_vault(*, db_session: AsyncSession, vault_id: UUID4, skip: int, limit: int):
        """Retrieve multiple rooms by vault ID."""
        response = await db_session.execute(select(Room).where(Room.vault_id == vault_id).offset(skip).limit(limit))
        return response.scalars().all()

    @staticmethod
    async def get_existing_room_names(*, db_session: AsyncSession, vault_id: UUID4) -> set[str]:
        """Get set of lowercase room names that exist in a vault."""
        response = await db_session.execute(select(Room.name).where(Room.vault_id == vault_id))
        return {name.lower() for name in response.scalars().all()}

    @staticmethod
    def evaluate_capacity_formula(formula: str, level: int, size: int) -> int:
        try:
            result = eval(formula, {"L": level, "S": size})
            return int(result)
        except (ValueError, SyntaxError) as e:
            logger.exception("Error evaluating capacity formula.", exc_info=e)
            return 0

    @staticmethod
    def evaluate_output_formula(formula: str, level: int, size: int) -> int:
        try:
            result = eval(formula, {"L": level, "S": size})
            return int(result)
        except (ValueError, SyntaxError) as e:
            logger.exception("Error evaluating output formula.", exc_info=e)
            return 0

    @staticmethod
    async def get_room_by_coordinates(
        *, db_session: AsyncSession, vault_id: int, x_coord: int, y_coord: int
    ) -> Room | None:
        """Retrieve a room by its coordinates in a vault."""
        response = await db_session.execute(
            select(Room).where(
                and_(Room.vault_id == vault_id, Room.coordinate_x == x_coord, Room.coordinate_y == y_coord)
            )
        )
        return response.scalars().first()

    @staticmethod
    async def get_room_build_price(*, db_session: AsyncSession, room_in: RoomCreate) -> int:
        """
        Calculate the price of building a room in a vault.
        It considers the base cost of the room type and applies an incremental cost
        based on the number of similar rooms already built in the vault.
        """
        response = await db_session.execute(
            select(Room).where(Room.vault_id == room_in.vault_id, Room.category == room_in.category)
        )
        rooms = response.scalars().all()

        if not room_in.incremental_cost:
            msg = "Incremental cost must be set for the room category."
            raise ValueError(msg)
        return room_in.base_cost + (len(rooms) * room_in.incremental_cost)

    @staticmethod
    async def check_is_unique_room(*, db_session: AsyncSession, obj_in: RoomCreate):
        """Raise an exception if a unique room of the same type already exists."""
        if obj_in.is_unique:
            existing_unique_room = await db_session.execute(
                select(Room).where(
                    and_(
                        Room.vault_id == obj_in.vault_id,
                        Room.name == obj_in.name,
                        or_(Room.incremental_cost == 0, Room.incremental_cost.is_(None)),
                    )
                )
            )
            if existing_unique_room.scalars().first():
                raise UniqueRoomViolationException(room_name=obj_in.name)

    async def expand_room(self, db_session: AsyncSession, existing_room: Room, additional_size: int) -> Room:
        """Expand the size of the existing room."""
        info = f"Expanding room {existing_room.name} (ID: {existing_room.id}) by {additional_size} units."
        logger.info(msg=info)
        if existing_room.size_min + additional_size > existing_room.size_max:
            raise InsufficientResourcesException(resource_name="room size", resource_amount=additional_size)
        existing_room.size_min += additional_size
        await self.update(
            db_session=db_session, obj_in=RoomUpdate(size_min=existing_room.size_min), id=existing_room.id
        )
        return existing_room

    @staticmethod
    def requires_recalculation(room_obj: RoomCreate | Room) -> bool:
        """Check if the room category needs to be recalculated."""
        return room_obj.category == RoomTypeEnum.CAPACITY or (
            room_obj.category == RoomTypeEnum.PRODUCTION and room_obj.name != "Radio studio"
        )

    async def build(self, *, db_session: AsyncSession, obj_in: RoomCreate) -> Room:  # noqa: C901, PLR0912
        """Implements the objectives to build a room checking for business logic constraints."""
        vault = await vault_crud.get(db_session, id=obj_in.vault_id)

        # Validate room size before proceeding
        if obj_in.size_min is None or obj_in.size_min < 1:
            msg = f"Invalid room size: {obj_in.size_min}. Size must be at least 1."
            raise ValueError(msg)

        if obj_in.size_max is None or obj_in.size_min > obj_in.size_max:
            msg = f"Invalid room size: {obj_in.size_min} exceeds maximum size {obj_in.size_max}."
            raise ValueError(msg)

        # Validate grid coordinates
        if obj_in.coordinate_x is None or obj_in.coordinate_y is None:
            msg = "Room coordinates must be specified."
            raise ValueError(msg)

        if obj_in.coordinate_x < 0 or obj_in.coordinate_x > 8:
            msg = f"Invalid X coordinate: {obj_in.coordinate_x}. Must be between 0 and 8."
            raise ValueError(msg)

        if obj_in.coordinate_y < 0 or obj_in.coordinate_y > 25:
            msg = f"Invalid Y coordinate: {obj_in.coordinate_y}. Must be between 0 and 25."
            raise ValueError(msg)

        # Prevent building multiple vault doors
        if obj_in.name.lower() == "vault door":
            existing_vault_door = await db_session.execute(
                select(Room).where(and_(Room.vault_id == vault.id, Room.name == "Vault Door"))
            )
            if existing_vault_door.scalars().first():
                msg = "Cannot build multiple vault doors. A vault door already exists."
                raise UniqueRoomViolationException(room_name="Vault Door")

        if not await vault_crud.is_enough_dwellers(
            db_session=db_session, vault_id=vault.id, population_required=obj_in.population_required
        ):
            raise InsufficientResourcesException(resource_name="dwellers", resource_amount=obj_in.population_required)

        existing_room = await self.get_room_by_coordinates(
            db_session=db_session, vault_id=vault.id, x_coord=obj_in.coordinate_x, y_coord=obj_in.coordinate_y
        )

        if existing_room:
            if existing_room.name == obj_in.name and existing_room.tier == obj_in.tier:
                return await self.expand_room(db_session, existing_room, obj_in.size_min)
            raise NoSpaceAvailableException(space_needed=obj_in.size_min)

        if obj_in.capacity_formula:
            obj_in.capacity = self.evaluate_capacity_formula(obj_in.capacity_formula, obj_in.tier, obj_in.size_min)

        if obj_in.output_formula:
            obj_in.output = self.evaluate_output_formula(obj_in.output_formula, obj_in.tier, obj_in.size_min)

        await self.check_is_unique_room(db_session=db_session, obj_in=obj_in)

        price = await self.get_room_build_price(db_session=db_session, room_in=obj_in)
        await vault_crud.withdraw_caps(db_session=db_session, vault_obj=vault, amount=price)

        obj_in_db = await self.create(db_session, obj_in=obj_in)

        if self.requires_recalculation(obj_in):
            await vault_crud.recalculate_vault_attributes(
                db_session=db_session, vault_obj=vault, room_obj=obj_in, action=RoomActionEnum.BUILD
            )

        return obj_in_db

    async def check_elevator_dependencies(self, db_session: AsyncSession, elevator_room: Room) -> None:
        """
        Check if removing an elevator would make any level inaccessible.
        An elevator is essential if removing it would leave a level with rooms but no elevator access.
        """
        if elevator_room.name.lower() != "elevator":
            return

        elevator_level = elevator_room.coordinate_y

        # Get all elevators in this vault
        elevators_result = await db_session.execute(
            select(Room).where(and_(Room.vault_id == elevator_room.vault_id, Room.name == "Elevator"))
        )
        all_elevators = elevators_result.scalars().all()

        # If this is the only elevator on this level, check if there are other rooms on this level
        elevators_on_level = [e for e in all_elevators if e.coordinate_y == elevator_level and e.id != elevator_room.id]

        if not elevators_on_level:
            # Check if there are other rooms (non-elevators) on this level
            rooms_on_level_result = await db_session.execute(
                select(Room).where(
                    and_(
                        Room.vault_id == elevator_room.vault_id,
                        Room.coordinate_y == elevator_level,
                        Room.name != "Elevator",
                        Room.id != elevator_room.id,
                    )
                )
            )
            other_rooms_on_level = rooms_on_level_result.scalars().all()

            if other_rooms_on_level:
                room_count = len(other_rooms_on_level)
                msg = (
                    f"Cannot destroy this elevator. It provides the only access to level {elevator_level} "
                    f"which contains {room_count} other room(s)."
                )
                raise ValueError(msg)

    async def destroy(self, db_session: AsyncSession, id: int | UUID4) -> ModelType:
        # Get room before deletion to check if it's a vault door
        room_to_delete = await self.get(db_session, id)

        # Prevent vault door removal
        if room_to_delete.name.lower() == "vault door":
            msg = "Cannot destroy the vault door. It is a critical structure and must remain in place."
            raise ValueError(msg)

        # Check elevator dependencies
        await self.check_elevator_dependencies(db_session, room_to_delete)

        db_obj = await super().delete(db_session, id=id)
        vault = await vault_crud.get(db_session, id=db_obj.vault_id)
        await vault_crud.deposit_caps(
            db_session=db_session, vault_obj=vault, amount=db_obj.base_cost * DESTROY_ROOM_REWARD
        )

        if self.requires_recalculation(db_obj):
            await vault_crud.recalculate_vault_attributes(
                db_session=db_session, vault_obj=vault, room_obj=db_obj, action=RoomActionEnum.DESTROY
            )

        return db_obj

    async def upgrade(self, *, db_session: AsyncSession, room_id: UUID4) -> Room:
        """Upgrade a room to the next tier."""
        room = await self.get(db_session, room_id)
        vault = await vault_crud.get(db_session, id=room.vault_id)

        # Determine max tier based on available upgrade costs
        max_tier = room.max_tier

        # Check if room can be upgraded
        if room.tier >= max_tier:
            msg = f"Room {room.name} is already at maximum tier {max_tier}"
            raise ValueError(msg)

        # Determine upgrade cost
        if room.tier == 1 and room.t2_upgrade_cost:
            upgrade_cost = room.t2_upgrade_cost
        elif room.tier == 2 and room.t3_upgrade_cost:
            upgrade_cost = room.t3_upgrade_cost
        else:
            msg = f"No upgrade cost defined for room {room.name} at tier {room.tier}"
            raise ValueError(msg)

        # Withdraw caps from vault
        await vault_crud.withdraw_caps(db_session=db_session, vault_obj=vault, amount=upgrade_cost)

        # Store old tier for recalculation
        old_tier = room.tier

        # Upgrade room tier
        room.tier += 1

        # Recalculate capacity and output proportionally based on tier increase
        # Capacity and output scale with tier level, so we multiply by the ratio
        new_capacity = None
        new_output = None

        if room.capacity is not None:
            # Recalculate based on tier scaling (capacity increases with tier)
            # Formula typically has (L+constant) factor, so we scale proportionally
            tier_ratio = (room.tier + 4) / (old_tier + 4)  # Using +4 from common formula pattern
            new_capacity = int(room.capacity * tier_ratio)

        if room.output is not None:
            # Recalculate based on tier scaling (output increases with tier)
            tier_ratio = (room.tier + 4) / (old_tier + 4)
            new_output = int(room.output * tier_ratio)

        # Update room in database
        await self.update(
            db_session=db_session,
            obj_in=RoomUpdate(tier=room.tier, capacity=new_capacity, output=new_output),
            id=room.id,
        )

        # Update local room object for recalculation
        room.capacity = new_capacity
        room.output = new_output

        # Recalculate vault attributes if needed
        if self.requires_recalculation(room):
            await vault_crud.recalculate_vault_attributes(
                db_session=db_session, vault_obj=vault, room_obj=room, action=RoomActionEnum.UPGRADE
            )

        await db_session.refresh(room)
        return room


room = CRUDRoom(Room)
