import logging

from sqlmodel import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.crud.vault import vault as vault_crud
from app.models.room import Room
from app.schemas.common import RoomType
from app.schemas.room import RoomCreate, RoomUpdate
from app.utils.exceptions import InsufficientResourcesException, NoSpaceAvailableException, UniqueRoomViolationException

logger = logging.getLogger(__name__)


class CRUDRoom(CRUDBase[Room, RoomCreate, RoomUpdate]):
    @staticmethod
    def evaluate_capacity_formula(formula: str, level: int, size: int) -> int:
        try:
            return eval(formula, {"L": level, "S": size})  # noqa: S307
        except (ValueError, SyntaxError) as e:
            logger.exception("Error evaluating capacity formula.", exc_info=e)
            return 0

    @staticmethod
    async def get_room_by_coordinates(*, db_session: AsyncSession, vault_id: int, x_coord: int, y_coord: int):
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
        # Retrieve the existing rooms of the same category in the specified vault
        response = await db_session.execute(
            select(Room).where(Room.vault_id == room_in.vault_id, Room.category == room_in.category)
        )
        rooms = response.scalars().all()

        return room_in.base_cost + (len(rooms) * room_in.incremental_cost)

    @staticmethod
    async def check_is_unique_room(*, db_session: AsyncSession, obj_in: RoomCreate):
        """Raise an exception if a unique room of the same type already exists."""
        if obj_in.is_unique:
            existing_unique_room = await db_session.execute(
                select(Room).where(and_(Room.vault_id == obj_in.vault_id, Room.is_unique is True))
            )
            if existing_unique_room.scalars().first():
                raise UniqueRoomViolationException(room_name=obj_in.name)

    @staticmethod
    async def requires_recalculation(room_obj: RoomCreate) -> bool:
        """Check if the room category needs to be recalculated."""
        if room_obj.category == RoomType.production and room_obj.name != "Radio studio":
            return True
        if room_obj.category == RoomType.capacity:
            return True
        return False

    async def build(self, *, db_session: AsyncSession, obj_in: RoomCreate) -> Room:
        """Implements the steps to build a room checking for business logic constraints."""
        price = await self.get_room_build_price(db_session=db_session, room_in=obj_in)
        vault = await vault_crud.get(db_session, id=obj_in.vault_id)

        if not await vault_crud.is_enough_dwellers(
            db_session=db_session, vault_id=vault.id, population_required=obj_in.population_required
        ):
            raise InsufficientResourcesException(resource_name="dwellers", resource_amount=obj_in.population_required)

        existing_room = await self.get_room_by_coordinates(
            db_session=db_session, vault_id=vault.id, x_coord=obj_in.coordinate_x, y_coord=obj_in.coordinate_y
        )
        if existing_room:
            raise NoSpaceAvailableException(space_needed=obj_in.size_min)

        if obj_in.capacity_formula:
            obj_in.capacity = self.evaluate_capacity_formula(obj_in.capacity_formula, obj_in.level, obj_in.size_min)

        await self.check_is_unique_room(db_session=db_session, obj_in=obj_in)
        await vault_crud.withdraw_caps(db_session=db_session, vault_obj=vault, amount=price)

        obj_in_db = await self.create(db_session, obj_in=obj_in)

        if self.requires_recalculation(obj_in):
            await vault_crud.recalculate_vault_attributes(db_session, vault, obj_in_db)


room = CRUDRoom(Room)
