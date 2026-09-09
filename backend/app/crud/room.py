import ast
import logging
import operator

from pydantic import UUID4
from sqlmodel import and_, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RoomTypeEnum
from app.crud.base import CRUDBase
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomUpdate
from app.utils.exceptions import (
    InsufficientResourcesException,
    UniqueRoomViolationException,
)

logger = logging.getLogger(__name__)

_ROOM_FORMULA_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ROOM_FORMULA_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _evaluate_room_formula(formula: str, level: int, size: int) -> int:
    """Evaluate a backend-owned room formula containing only arithmetic over L and S."""

    def evaluate(node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return node.value
        if isinstance(node, ast.Name) and node.id in {"L", "S"}:
            return {"L": level, "S": size}[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _ROOM_FORMULA_OPERATORS:
            return _ROOM_FORMULA_OPERATORS[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ROOM_FORMULA_UNARY_OPERATORS:
            return _ROOM_FORMULA_UNARY_OPERATORS[type(node.op)](evaluate(node.operand))
        raise ValueError(f"Unsupported room formula: {formula!r}")

    try:
        expression = ast.parse(formula, mode="eval")
        return int(evaluate(expression.body))
    except (ArithmeticError, SyntaxError, ValueError) as exc:
        raise ValueError(f"Invalid room formula: {formula!r}") from exc


class CRUDRoom(CRUDBase[Room, RoomCreate, RoomUpdate]):
    @staticmethod
    async def get_by_category(db_session: AsyncSession, vault_id: UUID4, category: RoomTypeEnum) -> list[Room]:
        """Rooms of one category for a vault."""
        query = select(Room).where(Room.vault_id == vault_id).where(Room.category == category)
        return list((await db_session.execute(query)).scalars().all())

    @staticmethod
    async def get_by_categories(
        db_session: AsyncSession, vault_id: UUID4, categories: list[RoomTypeEnum]
    ) -> list[Room]:
        """Rooms of a vault in any of the given categories."""
        response = await db_session.execute(
            select(Room).where(Room.vault_id == vault_id, Room.category.in_(categories))
        )
        return list(response.scalars().all())

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
    async def get_by_name_pattern(db_session: AsyncSession, vault_id: UUID4, pattern: str) -> list[Room]:
        """Rooms of a vault whose name matches a LIKE pattern (e.g. ``%radio%``)."""
        response = await db_session.execute(select(Room).where(Room.vault_id == vault_id, Room.name.ilike(pattern)))
        return list(response.scalars().all())

    @staticmethod
    async def get_production_with_ability(db_session: AsyncSession, vault_id: UUID4) -> Room | None:
        """Oldest production room that trains a SPECIAL ability, if any."""
        response = await db_session.execute(
            select(Room)
            .where(
                Room.vault_id == vault_id,
                Room.category == RoomTypeEnum.PRODUCTION,
                Room.ability.is_not(None),
            )
            .order_by(Room.created_at)
        )
        return response.scalars().first()

    @staticmethod
    async def get_occupied_rooms(db_session: AsyncSession, vault_id: UUID4) -> list[Room]:
        """Rooms of a vault currently occupied by at least one dweller, elevators excluded."""
        from app.models.dweller import Dweller

        query = (
            select(Room)
            .join(Dweller, Room.id == Dweller.room_id)
            .where(
                (Room.vault_id == vault_id)
                & (Dweller.room_id.is_not(None))
                & (Room.name != "Elevator")  # Exclude elevators
            )
            .distinct()
        )
        return list((await db_session.execute(query)).scalars().all())

    @staticmethod
    async def get_adjacent_rooms(
        db_session: AsyncSession, vault_id: UUID4, *, exclude_room_id: UUID4, coord_x: int, coord_y: int
    ) -> list[Room]:
        """Rooms within 1-2 grid units of a coordinate, elevators and the origin room excluded."""
        query = select(Room).where(
            (Room.vault_id == vault_id)
            & (Room.id != exclude_room_id)
            & (Room.coordinate_x.is_not(None))
            & (Room.coordinate_y.is_not(None))
            & (Room.name != "Elevator")  # Exclude elevators from spread
            & (
                # Adjacent horizontally (same floor, next to each other)
                ((Room.coordinate_y == coord_y) & (Room.coordinate_x.between(coord_x - 2, coord_x + 2)))
                # Adjacent vertically (same column, one floor up/down)
                | ((Room.coordinate_x == coord_x) & (Room.coordinate_y.between(coord_y - 1, coord_y + 1)))
            )
        )
        return list((await db_session.execute(query)).scalars().all())

    @staticmethod
    async def get_arena_rooms(
        db_session: AsyncSession, *, room_id: UUID4 | None = None, vault_id: UUID4 | None = None
    ) -> list[Room]:
        """Arena rooms, optionally narrowed to one room id and/or one vault."""
        query = select(Room).where(Room.category == RoomTypeEnum.ARENA)
        if room_id is not None:
            query = query.where(Room.id == room_id)
        if vault_id is not None:
            query = query.where(Room.vault_id == vault_id)
        return list((await db_session.execute(query)).scalars().all())

    @staticmethod
    async def get_arena_rooms_with_fighter(db_session: AsyncSession, dweller_id: UUID4) -> list[Room]:
        """Arena rooms where the dweller occupies either fighter slot."""
        query = select(Room).where(
            Room.category == RoomTypeEnum.ARENA,
            (Room.arena_fighter_a_id == dweller_id) | (Room.arena_fighter_b_id == dweller_id),
        )
        return list((await db_session.execute(query)).scalars().all())

    @staticmethod
    def evaluate_capacity_formula(formula: str, level: int, size: int) -> int:
        try:
            result = _evaluate_room_formula(formula, level, size)
            return int(result)
        except (ValueError, SyntaxError) as e:
            logger.exception("Error evaluating capacity formula.", exc_info=e)
            return 0

    @staticmethod
    def evaluate_output_formula(formula: str, level: int, size: int) -> int:
        try:
            result = _evaluate_room_formula(formula, level, size)
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


room = CRUDRoom(Room)
