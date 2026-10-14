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


def response_station_lock_key(room_id: UUID4) -> str:
    """Advisory-lock key guarding one Response Station's footprint and occupancy.

    Expansion and assignment both mutate what the station can hold, so they share
    the key: either side serializes against the other instead of racing the count
    or the 3 -> 6 -> 9 growth.
    """
    return f"response-station:{room_id}"


def vault_placement_lock_key(vault_id: UUID4) -> str:
    """Advisory-lock key guarding every placement change in one vault's grid.

    Construction and in-place expansion both rewrite room footprints against the
    same grid, so they share a vault-scoped key: a build cannot occupy the space an
    expansion is growing into, and two builds cannot land on the same cells.
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


async def validate_response_station_capacity(db_session: AsyncSession, room: Room) -> None:
    """Refuse to overfill the Response Station, whose occupancy must follow its footprint.

    The station is a unique room that grows in place (``RoomService.expand_room``)
    rather than by building an adjacent segment, so its assignment path must enforce
    the 2-per-3-units capacity that expansion raises. Non-response rooms keep their
    existing (uncapped) manual-assignment behaviour.
    """
    if room.category != RoomTypeEnum.RESPONSE:
        return

    # Count-then-move is a TOCTOU race: two assignments can both read the last free
    # slot and both proceed. A transaction-scoped lock taken before the count is
    # held until ``move_to_room`` commits, so the check and the move that follows it
    # are one critical section (a no-op True outside PostgreSQL).
    if not await db_locks.try_advisory_xact_lock(db_session, response_station_lock_key(room.id)):
        raise ResourceConflictException(detail=f"{room.name} is busy — try again")

    room_size = room.size if room.size is not None else room.size_min
    capacity = calculate_room_capacity(room_size)

    from app.crud.dweller import dweller as dweller_crud

    occupants = await dweller_crud.count_in_room(db_session, room.id)
    if occupants >= capacity:
        raise ResourceConflictException(detail=f"{room.name} is at full capacity ({capacity})")


async def validate_room_assignment(db_session: AsyncSession, dweller: Dweller, room: Room) -> None:
    """Allow one youth junior worker in each production room, training its ability.

    A junior worker both assists production (at the reduced junior rate in the
    resource manager) and advances the room's SPECIAL while they are posted there.
    """
    await validate_response_station_capacity(db_session, room)
    if dweller.is_mature:
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
