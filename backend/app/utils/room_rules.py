"""Room placement rules — elevator stacking and level-access gating.

Single source of truth for the vault-grid invariants:

- R1: an elevator can only be built directly under another elevator
- R2: non-elevator rooms above row 0 need an elevator on their level
- D1: an elevator that is the only access to its level cannot be destroyed
- D2: an elevator with another elevator stacked directly above cannot be destroyed

Raised exceptions match the pre-existing contract: build violations raise
``VaultOperationException`` (the API maps it to 400); destroy violations raise
``ValueError`` (``room_service.destroy_room`` maps it to 400).
"""

from pydantic import UUID4
from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.room import Room
from app.utils.exceptions import VaultOperationException

ELEVATOR = "elevator"


def is_elevator(room_name: str | None) -> bool:
    """Case-insensitive elevator name check."""
    return room_name is not None and room_name.strip().lower() == ELEVATOR


async def validate_build_placement(
    db_session: AsyncSession,
    vault_id: UUID4,
    room_name: str,
    coordinate_x: int,
    coordinate_y: int,
    size: int,
) -> None:
    """Enforce R1 (elevator stacking), R2 (level access), and footprint rules."""
    if is_elevator(room_name):
        elevator_above = await db_session.execute(
            select(Room).where(
                and_(
                    Room.vault_id == vault_id,
                    Room.name == "Elevator",
                    Room.coordinate_x == coordinate_x,
                    Room.coordinate_y == coordinate_y - 1,
                )
            )
        )
        if elevator_above.scalars().first() is None:
            raise VaultOperationException(
                detail=(
                    f"Cannot build elevator at ({coordinate_x}, {coordinate_y}): "
                    "elevators must be built directly under another elevator."
                )
            )
        return

    if coordinate_y > 0:
        elevator_on_level = await db_session.execute(
            select(Room).where(
                and_(
                    Room.vault_id == vault_id,
                    Room.name == "Elevator",
                    Room.coordinate_y == coordinate_y,
                )
            )
        )
        if elevator_on_level.scalars().first() is None:
            raise VaultOperationException(
                detail=(
                    f"Cannot build {room_name} at ({coordinate_x}, {coordinate_y}): "
                    f"level {coordinate_y} has no elevator. Build an elevator first."
                )
            )

    await _validate_footprint(db_session, vault_id, room_name, coordinate_x, coordinate_y, size)


def _room_span(room: Room) -> tuple[int, int]:
    size = room.size if room.size is not None else room.size_min
    return room.coordinate_x, room.coordinate_x + size - 1


async def _validate_footprint(
    db_session: AsyncSession,
    vault_id: UUID4,
    room_name: str,
    coordinate_x: int,
    coordinate_y: int,
    size: int,
) -> None:
    """Reject overlapping footprints and rooms that touch nothing on their level."""
    rooms_on_level = list(
        (
            await db_session.execute(
                select(Room).where(
                    and_(
                        Room.vault_id == vault_id,
                        Room.coordinate_y == coordinate_y,
                        Room.coordinate_x.is_not(None),
                    )
                )
            )
        )
        .scalars()
        .all()
        or []
    )

    expansion = next(
        (room for room in rooms_on_level if room.coordinate_x == coordinate_x and room.name == room_name),
        None,
    )
    start = coordinate_x
    end = coordinate_x + size - 1
    if expansion is not None:
        end = _room_span(expansion)[1] + size

    for room in rooms_on_level:
        if room is expansion:
            continue
        room_start, room_end = _room_span(room)
        if start <= room_end and room_start <= end:
            raise VaultOperationException(
                detail=(f"Cannot build {room_name} at ({coordinate_x}, {coordinate_y}): overlaps {room.name}.")
            )

    if expansion is not None:
        return

    touches_existing = any(
        _room_span(room)[1] + 1 == start or end + 1 == _room_span(room)[0] for room in rooms_on_level
    )
    if not touches_existing:
        raise VaultOperationException(
            detail=(
                f"Cannot build {room_name} at ({coordinate_x}, {coordinate_y}): "
                "rooms must be built next to another room or an elevator."
            )
        )


async def validate_elevator_destroy(db_session: AsyncSession, elevator_room: Room) -> None:
    """Enforce D2 (nothing stacked above) and D1 (no stranded rooms) before a destroy."""
    if not is_elevator(elevator_room.name):
        return

    # D2: an elevator directly above depends on this one — removing it breaks the stack.
    elevator_above = await db_session.execute(
        select(Room).where(
            and_(
                Room.vault_id == elevator_room.vault_id,
                Room.name == "Elevator",
                Room.coordinate_x == elevator_room.coordinate_x,
                Room.coordinate_y == elevator_room.coordinate_y - 1,
            )
        )
    )
    if elevator_above.scalars().first() is not None:
        raise ValueError("Cannot destroy this elevator: another elevator is stacked directly above it.")

    # D1: if this is the only elevator on its level, rooms there would be stranded.
    elevators_result = await db_session.execute(
        select(Room).where(and_(Room.vault_id == elevator_room.vault_id, Room.name == "Elevator"))
    )
    all_elevators = elevators_result.scalars().all()
    elevator_level = elevator_room.coordinate_y
    elevators_on_level = [
        elevator
        for elevator in all_elevators
        if elevator.coordinate_y == elevator_level and elevator.id != elevator_room.id
    ]
    if elevators_on_level:
        return

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
    other_rooms_on_level = list(rooms_on_level_result.scalars().all())
    if other_rooms_on_level:
        raise ValueError(
            f"Cannot destroy this elevator. It provides the only access to level {elevator_level} "
            f"which contains {len(other_rooms_on_level)} other room(s)."
        )
