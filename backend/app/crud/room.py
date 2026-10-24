import ast
import logging
import operator
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlalchemy import delete, update
from sqlmodel import and_, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.crud.base import CRUDBase
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomRead, RoomUpdate
from app.utils.exceptions import (
    UniqueRoomViolationException,
)
from app.utils.objective_constants import normalize_room_type

if TYPE_CHECKING:
    from app.models.dweller import Dweller

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
    async def get_remodel_dwellers(db_session: AsyncSession, vault_id: UUID4, room_ids: list[UUID4]) -> list["Dweller"]:
        """Include dispatched residents whose return posting belongs to a remodeled room."""
        from app.models.dweller import Dweller
        from app.models.team import TeamMember

        returning = select(TeamMember.dweller_id).where(TeamMember.origin_room_id.in_(room_ids))
        response = await db_session.execute(
            select(Dweller).where(
                Dweller.vault_id == vault_id,
                ~Dweller.is_deleted,
                or_(Dweller.room_id.in_(room_ids), Dweller.id.in_(returning)),
            )
        )
        return list(response.scalars().all())

    @staticmethod
    async def apply_remodel(
        db_session: AsyncSession, originals: list[Room], replacements: list[Room], destinations: dict[UUID4, UUID4]
    ) -> list[Room]:
        """Persist footprints and all room references in one transaction; caller holds the placement lock."""
        from app.models.crafting_order import CraftingOrder
        from app.models.dweller import Dweller
        from app.models.incident import Incident
        from app.models.team import TeamMember
        from app.models.training import Training

        survivor_id = replacements[0].id
        original_ids = [room.id for room in originals]
        absorbed_ids = [room_id for room_id in original_ids if room_id != survivor_id]
        survivor = next(room for room in originals if room.id == survivor_id)
        # Rush state belongs to the surviving room; a remodel must not reset its stacks.
        survivor.sqlmodel_update(
            replacements[0].model_dump(exclude={"id", "created_at", "updated_at", "rush_stacks", "last_rush_at"})
        )
        replacements[0] = survivor
        db_session.add_all(replacements)
        await db_session.flush()
        residents = (await db_session.execute(select(Dweller).where(Dweller.room_id.in_(original_ids)))).scalars().all()
        for dweller in residents:
            destination = destinations.get(dweller.id, survivor_id)
            dweller.room_id = destination
            await db_session.execute(
                update(Training)
                .where(Training.dweller_id == dweller.id, Training.room_id.in_(original_ids))
                .values(room_id=destination)
            )
        for dweller_id, destination in destinations.items():
            await db_session.execute(
                update(TeamMember)
                .where(TeamMember.dweller_id == dweller_id, TeamMember.origin_room_id.in_(original_ids))
                .values(origin_room_id=destination)
            )
        if absorbed_ids:
            for model, field in [
                (Training, Training.room_id),
                (TeamMember, TeamMember.origin_room_id),
                (Incident, Incident.room_id),
                (CraftingOrder, CraftingOrder.room_id),
            ]:
                await db_session.execute(
                    update(model)
                    .where(field.in_(absorbed_ids))
                    .values(**{"origin_room_id" if model is TeamMember else "room_id": survivor_id})
                )
            # Historical spread/report references must follow the surviving room too.
            incidents = (
                (await db_session.execute(select(Incident).where(Incident.vault_id == survivor.vault_id)))
                .scalars()
                .all()
            )
            absorbed = {str(room_id) for room_id in absorbed_ids}
            for incident in incidents:
                incident.rooms_affected = list(
                    dict.fromkeys(
                        str(survivor_id) if value in absorbed else value for value in (incident.rooms_affected or [])
                    )
                )
            await db_session.flush()
            await db_session.execute(delete(Room).where(Room.id.in_(absorbed_ids)))
        await db_session.commit()
        for room in replacements:
            await db_session.refresh(room)
        return replacements

    @staticmethod
    async def get_living_quarters(db_session: AsyncSession, vault_id: UUID4) -> list[Room]:
        """Storage rooms share CAPACITY, but only Charisma rooms are living quarters."""
        result = await db_session.execute(
            select(Room).where(
                Room.vault_id == vault_id,
                Room.category == RoomTypeEnum.CAPACITY,
                Room.ability == SPECIALEnum.CHARISMA,
            )
        )
        return list(result.scalars().all())

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
    async def get_all_by_vault(db_session: AsyncSession, vault_id: UUID4) -> list[Room]:
        """Every room of a vault, for layout/migration passes."""
        response = await db_session.execute(select(Room).where(Room.vault_id == vault_id))
        return list(response.scalars().all() or [])

    @staticmethod
    async def count_by_vault(db_session: AsyncSession, vault_id: UUID4) -> int:
        """Every room of a vault, transit included, for development-scaled rules."""
        result = await db_session.execute(select(func.count(Room.id)).where(Room.vault_id == vault_id))
        return int(result.scalar_one())

    @staticmethod
    async def get_names_by_ids(db_session: AsyncSession, room_ids: list[UUID4]) -> dict[UUID4, str]:
        """Map room id to name for the given ids; empty when none are given."""
        if not room_ids:
            return {}
        response = await db_session.execute(select(Room.id, Room.name).where(Room.id.in_(room_ids)))
        return {row[0]: row[1] for row in response.all()}

    @staticmethod
    async def get_names_by_vault(db_session: AsyncSession, vault_id: UUID4) -> list[str]:
        """Raw (non-normalized) names of every room in a vault."""
        response = await db_session.execute(select(Room.name).where(Room.vault_id == vault_id))
        return list(response.scalars().all())

    @staticmethod
    async def get_existing_room_names(*, db_session: AsyncSession, vault_id: UUID4) -> set[str]:
        """Get set of lowercase room names that exist in a vault."""
        return {name.lower() for name in await CRUDRoom.get_names_by_vault(db_session, vault_id)}

    @staticmethod
    async def get_maxed_unique_room_names(*, db_session: AsyncSession, vault_id: UUID4) -> set[str]:
        """Lowercase names of unique rooms already at ``size_max``.

        A unique room below its maximum footprint can still merge an adjacent
        segment, so only the maxed ones are blocked from the build menu.
        """
        rooms = await CRUDRoom.get_all_by_vault(db_session, vault_id)
        return {
            room.name.lower()
            for room in rooms
            if room.is_unique and (room.size if room.size is not None else room.size_min) >= room.size_max
        }

    @staticmethod
    async def get_room_tier_by_name(db_session: AsyncSession, vault_id: UUID4, room_name: str) -> int | None:
        """The tier of the vault's room matching the normalized name, or None when absent."""
        normalized = normalize_room_type(room_name)
        if normalized is None:
            return None
        rooms = await CRUDRoom.get_all_by_vault(db_session, vault_id)
        return next((room.tier for room in rooms if normalize_room_type(room.name) == normalized), None)

    @staticmethod
    async def has_room_type(db_session: AsyncSession, vault_id: UUID4, room_type: str) -> bool:
        """Whether the vault has a built room matching the normalized room type."""
        return await CRUDRoom.get_room_tier_by_name(db_session, vault_id, room_type) is not None

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
        """Rooms of a vault currently occupied by at least one dweller, elevators and arenas excluded."""
        from app.models.dweller import Dweller

        query = (
            select(Room)
            .join(Dweller, Room.id == Dweller.room_id)
            .where(
                (Room.vault_id == vault_id)
                & (Dweller.room_id.is_not(None))
                & (Room.name != "Elevator")  # Exclude elevators
                & (Room.category != RoomTypeEnum.ARENA)  # An arena hosts matches, not incidents
                & (Room.category != RoomTypeEnum.RESPONSE)  # A management surface, not a combat destination
            )
            .distinct()
        )
        return list((await db_session.execute(query)).scalars().all())

    @staticmethod
    async def get_adjacent_rooms(
        db_session: AsyncSession, vault_id: UUID4, *, exclude_room_id: UUID4, coord_x: int, coord_y: int
    ) -> list[Room]:
        """Rooms within 1-2 grid units of a coordinate, elevators, arenas and the origin room excluded."""
        query = select(Room).where(
            (Room.vault_id == vault_id)
            & (Room.id != exclude_room_id)
            & (Room.coordinate_x.is_not(None))
            & (Room.coordinate_y.is_not(None))
            & (Room.name != "Elevator")  # Exclude elevators from spread
            & (Room.category != RoomTypeEnum.ARENA)  # An arena hosts matches, not incidents
            & (Room.category != RoomTypeEnum.RESPONSE)  # A management surface, not a combat destination
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
    async def update_rush_state(
        db_session: AsyncSession,
        room: Room,
        *,
        stacks: int,
        last_rush_at: datetime | None,
    ) -> None:
        """Persist the room's rush stacks and last-attempt timestamp."""
        room.rush_stacks = stacks
        room.last_rush_at = last_rush_at
        db_session.add(room)
        await db_session.flush()

    @staticmethod
    def _evaluate_formula_logged(formula: str, level: int, size: int, *, label: str) -> int:
        try:
            result = _evaluate_room_formula(formula, level, size)
            return int(result)
        except (ValueError, SyntaxError) as e:
            logger.exception("Error evaluating %s formula.", label, exc_info=e)
            return 0

    @staticmethod
    def evaluate_capacity_formula(formula: str, level: int, size: int) -> int:
        return CRUDRoom._evaluate_formula_logged(formula, level, size, label="capacity")

    @staticmethod
    def evaluate_output_formula(formula: str, level: int, size: int) -> int:
        return CRUDRoom._evaluate_formula_logged(formula, level, size, label="output")

    @staticmethod
    async def get_room_by_coordinates(
        *, db_session: AsyncSession, vault_id: UUID4, x_coord: int, y_coord: int
    ) -> Room | None:
        """Retrieve a room by its coordinates in a vault."""
        response = await db_session.execute(
            select(Room).where(
                and_(Room.vault_id == vault_id, Room.coordinate_x == x_coord, Room.coordinate_y == y_coord)
            )
        )
        return response.scalars().first()

    @staticmethod
    async def get_adjacent_mergeable_rooms(
        *,
        db_session: AsyncSession,
        vault_id: UUID4,
        name: str,
        tier: int,
        coordinate_x: int,
        coordinate_y: int,
        size: int,
    ) -> list[Room]:
        """Same-name/same-tier rooms on the same row whose footprint touches the candidate footprint.

        A room is mergeable when its right edge is exactly one unit left of the candidate's
        left edge, or its left edge is exactly one unit right of the candidate's right edge.
        The live footprint is ``coalesce(size, size_min)``.
        """
        existing_size = func.coalesce(Room.size, Room.size_min)
        query = select(Room).where(
            Room.vault_id == vault_id,
            Room.name == name,
            Room.tier == tier,
            Room.coordinate_y == coordinate_y,
            Room.coordinate_x.is_not(None),
            or_(
                (Room.coordinate_x + existing_size) == coordinate_x,
                (coordinate_x + size) == Room.coordinate_x,
            ),
        )
        return list((await db_session.execute(query)).scalars().all())

    @staticmethod
    async def get_room_build_price(*, db_session: AsyncSession, room_in: RoomCreate) -> int:
        """
        Calculate the price of building a room in a vault.
        It considers the base cost of the room type and applies an incremental cost
        based on the built segments of this specific room type in the vault.
        A unique room (zero/null incremental cost) charges only its base price.
        """
        if not room_in.incremental_cost:
            return room_in.base_cost
        response = await db_session.execute(
            select(Room).where(Room.vault_id == room_in.vault_id, Room.name == room_in.name)
        )
        count = sum(room.segment_count for room in response.scalars())
        return room_in.base_cost + count * room_in.incremental_cost

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

    @staticmethod
    def requires_recalculation(room_obj: RoomCreate | Room | RoomRead) -> bool:
        """Check if the room category needs to be recalculated."""
        return room_obj.category == RoomTypeEnum.CAPACITY or (
            room_obj.category == RoomTypeEnum.PRODUCTION and room_obj.name != "Radio studio"
        )

    @staticmethod
    async def clear_origin_room_references(db_session: AsyncSession, room_id: UUID4) -> None:
        """Null the dispatch provenance that points at a room about to be demolished.

        Mirrors the ``team_member.origin_room_id`` FK's ``ON DELETE SET NULL`` in the
        application layer, so the documented "a deleted room means no posting to
        restore" invariant holds even where the database does not enforce the
        constraint (e.g. the SQLite test schema). Without it a dangling origin stays
        on the incident roster and the return pass raises resolving it.
        """
        from app.models.team import TeamMember

        await db_session.execute(
            update(TeamMember).where(TeamMember.origin_room_id == room_id).values(origin_room_id=None)
        )


room = CRUDRoom(Room)
