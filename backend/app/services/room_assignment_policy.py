"""Eligibility rules shared by manual and automatic room assignment."""

# TODO: relocate this room-assignment kernel outside services so CRUD can share it
# (dweller availability now lives in app/utils/dweller_availability.py).

from pydantic import UUID4
from sqlmodel import col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import db_locks
from app.core.enums import ADULT_AGE_GROUPS, STAT_BY_SPECIAL, RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.dweller import DwellerReadFull
from app.utils.exceptions import ResourceConflictException, ValidationException

ABILITY_TO_STAT_MAP = STAT_BY_SPECIAL


def room_occupancy_lock_key(room_id: UUID4) -> str:
    """Advisory-lock key guarding one room's occupant count.

    Assignment mutates the room's occupant count, so every manual and automatic
    move into the same room takes this key first: concurrent moves serialize
    instead of both reading the last free slot. Footprint changes (build,
    upgrade merge, backfill) serialize separately on the vault placement lock.
    """
    return f"room-occupancy:{room_id}"


def vault_placement_lock_key(vault_id: UUID4) -> str:
    """Advisory-lock key guarding every placement change in one vault's grid.

    Construction, demolition, upgrade merging and the vault-wide merge backfill rewrite
    room footprints against the same grid, so they share a vault-scoped key: two
    placement changes cannot land on the same cells.
    """
    return f"vault-placement:{vault_id}"


def get_highest_special(dweller: Dweller | DwellerReadFull) -> SPECIALEnum:
    """Return the dweller's highest SPECIAL stat (ties resolve to the first listed stat)."""
    return max(ABILITY_TO_STAT_MAP, key=lambda stat: getattr(dweller, ABILITY_TO_STAT_MAP[stat]))


def calculate_room_capacity(room_size: int | None) -> int:
    """Return dweller slots from room size (2 dwellers per 3 size units, 0 when size is unknown)."""
    return (room_size // 3) * 2 if room_size else 0


def adult_assignment_conditions() -> tuple:
    """Return database conditions that select mature dwellers for automatic work assignment."""
    return (col(Dweller.age_group).in_(ADULT_AGE_GROUPS),)


async def validate_room_worker_capacity(db_session: AsyncSession, room: Room) -> None:
    """Refuse to overfill a room's worker slots, whose count must follow its footprint.

    The automatic path selects rooms through ``calculate_room_capacity`` (2 workers
    per 3 size units); the manual path enforces the same count here so a move into
    a full room is rejected instead of persisted. Production apprentices sit
    outside worker capacity (see ``DwellerAssignmentService._get_available_slots``);
    every other room counts all occupants.
    """
    # Count-then-move is a TOCTOU race: two assignments can both read the last free
    # slot and both proceed. A transaction-scoped lock taken before the count is
    # held until ``move_to_room`` commits, so the check and the move that follows it
    # are one critical section (a no-op True outside PostgreSQL).
    if not await db_locks.try_advisory_xact_lock(db_session, room_occupancy_lock_key(room.id)):
        raise ResourceConflictException(detail=f"{room.name} is busy — try again")

    room_size = room.size if room.size is not None else room.size_min
    capacity = calculate_room_capacity(room_size)
    if capacity <= 0:
        # No footprint-based slots (unsized rooms, sub-3 fixtures): the formula
        # does not speak for these rooms, so manual assignment keeps its
        # existing behaviour there.
        return

    from app.crud.dweller import dweller as dweller_crud

    occupants = await dweller_crud.count_in_room(
        db_session, room.id, include_apprentices=room.category != RoomTypeEnum.PRODUCTION
    )
    if occupants >= capacity:
        raise ResourceConflictException(detail=f"{room.name} is at full capacity ({capacity})")


async def validate_room_assignment(db_session: AsyncSession, dweller: Dweller, room: Room) -> None:
    """Allow one youth junior worker in each production room, training its ability.

    A junior worker both assists production (at the reduced junior rate in the
    resource manager) and advances the room's SPECIAL while they are posted there.
    """
    if dweller.is_mature:
        await validate_room_worker_capacity(db_session, room)
        return
    if room.category == RoomTypeEnum.ARENA:
        raise ValidationException(detail="Only adult dwellers can fight in the Arena")
    if room.category != RoomTypeEnum.PRODUCTION:
        raise ValidationException(
            detail="Child and teen dwellers can only be assigned to production rooms as apprentices"
        )
    if room.ability is None:
        raise ValidationException(detail="Production room must have a SPECIAL ability for an apprentice")

    from app.crud.dweller import dweller as dweller_crud

    existing_apprentice = await dweller_crud.has_other_apprentice(
        db_session, room_id=room.id, exclude_dweller_id=dweller.id
    )
    if existing_apprentice:
        raise ValidationException(detail="This production room already has an apprentice")


def validate_automatic_assignment(dweller: Dweller) -> None:
    """Keep single-dweller auto-assign adult-only; youth are placed by the apprentice pass in room auto-assign flows."""
    if not dweller.is_mature:
        raise ValidationException(detail="Child and teen dwellers must be assigned manually as apprentices")
