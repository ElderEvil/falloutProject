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
from sqlalchemy import and_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.grid_config import GRID_X_MAX
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
    tier: int | None = None,
) -> None:
    """Enforce R1 (elevator stacking), R2 (level access), and footprint rules."""
    if is_elevator(room_name):
        elevator_above = await db_session.exec(
            select(Room).where(
                and_(
                    col(Room.vault_id) == vault_id,
                    col(Room.name) == "Elevator",
                    col(Room.coordinate_x) == coordinate_x,
                    col(Room.coordinate_y) == coordinate_y - 1,
                )
            )
        )
        if elevator_above.first() is None:
            raise VaultOperationException(
                detail=(
                    f"Cannot build elevator at ({coordinate_x}, {coordinate_y}): "
                    "elevators must be built directly under another elevator."
                )
            )
        await _validate_footprint(
            db_session, vault_id, room_name, coordinate_x, coordinate_y, size, tier=tier, require_adjacency=False
        )
        return

    if coordinate_y > 0:
        elevator_on_level = await db_session.exec(
            select(Room).where(
                and_(
                    col(Room.vault_id) == vault_id,
                    col(Room.name) == "Elevator",
                    col(Room.coordinate_y) == coordinate_y,
                )
            )
        )
        if elevator_on_level.first() is None:
            raise VaultOperationException(
                detail=(
                    f"Cannot build {room_name} at ({coordinate_x}, {coordinate_y}): "
                    f"level {coordinate_y} has no elevator. Build an elevator first."
                )
            )

    await _validate_footprint(db_session, vault_id, room_name, coordinate_x, coordinate_y, size, tier=tier)


def _room_span(room: Room) -> tuple[int, int]:
    start = room.coordinate_x
    if start is None:
        raise VaultOperationException(detail=f"Room {room.name} has no grid position.")
    size = room.size if room.size is not None else room.size_min
    return start, start + size - 1


def _reject_overlaps(
    rooms: list[Room],
    *,
    start: int,
    end: int,
    action: str,
    room_name: str,
    coordinate_x: int,
    coordinate_y: int,
    exclude: Room | None = None,
) -> None:
    """Raise if the closed span ``start..end`` intersects any room footprint.

    Shared by the build/merge path and the in-place expansion path so both reject
    the same overlaps with the same exception contract.
    """
    for room in rooms:
        if room is exclude:
            continue
        room_start, room_end = _room_span(room)
        if start <= room_end and room_start <= end:
            raise VaultOperationException(
                detail=f"Cannot {action} {room_name} at ({coordinate_x}, {coordinate_y}): overlaps {room.name}."
            )


async def _validate_footprint(
    db_session: AsyncSession,
    vault_id: UUID4,
    room_name: str,
    coordinate_x: int,
    coordinate_y: int,
    size: int,
    tier: int | None = None,
    require_adjacency: bool = True,
) -> None:
    """Reject overlapping footprints and rooms that touch nothing on their level."""
    rooms_on_level = list(
        (
            await db_session.exec(
                select(Room).where(
                    and_(
                        col(Room.vault_id) == vault_id,
                        col(Room.coordinate_y) == coordinate_y,
                        col(Room.coordinate_x).is_not(None),
                    )
                )
            )
        ).all()
        or []
    )

    expansion = next(
        (
            room
            for room in rooms_on_level
            if room.coordinate_x == coordinate_x and room.name == room_name and (tier is None or room.tier == tier)
        ),
        None,
    )
    start = coordinate_x
    end = coordinate_x + size - 1
    if expansion is not None:
        end = _room_span(expansion)[1] + size

    _reject_overlaps(
        rooms_on_level,
        start=start,
        end=end,
        action="build",
        room_name=room_name,
        coordinate_x=coordinate_x,
        coordinate_y=coordinate_y,
        exclude=expansion,
    )

    if expansion is not None or not require_adjacency:
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


async def validate_expansion_placement(db_session: AsyncSession, room: Room, target_size: int) -> None:
    """Reject an in-place footprint growth that leaves the grid or overlaps a room.

    Reuses the build/merge footprint rules: the grown span is checked against every
    other room on the level. Level access (R2) is already satisfied because the room
    exists where it was placed, and adjacency is not required for a room that
    already occupies the level.
    """
    if room.coordinate_x is None or room.coordinate_y is None:
        raise VaultOperationException(detail=f"Cannot expand {room.name}: room has no grid position.")

    start = room.coordinate_x
    end = start + target_size - 1
    if end > GRID_X_MAX:
        raise VaultOperationException(detail=f"Cannot expand {room.name}: max X {end} > {GRID_X_MAX}")

    rooms_on_level = list(
        (
            await db_session.exec(
                select(Room).where(
                    and_(
                        col(Room.vault_id) == room.vault_id,
                        col(Room.coordinate_y) == room.coordinate_y,
                        col(Room.coordinate_x).is_not(None),
                    )
                )
            )
        ).all()
        or []
    )

    _reject_overlaps(
        rooms_on_level,
        start=start,
        end=end,
        action="expand",
        room_name=room.name,
        coordinate_x=start,
        coordinate_y=room.coordinate_y,
        exclude=room,
    )


async def validate_elevator_destroy(db_session: AsyncSession, elevator_room: Room) -> None:
    """Enforce D2 (nothing stacked above) and D1 (no stranded rooms) before a destroy."""
    if not is_elevator(elevator_room.name):
        return
    if elevator_room.coordinate_x is None or elevator_room.coordinate_y is None:
        return

    # D2: an elevator directly above depends on this one — removing it breaks the stack.
    elevator_above = await db_session.exec(
        select(Room).where(
            and_(
                col(Room.vault_id) == elevator_room.vault_id,
                col(Room.name) == "Elevator",
                col(Room.coordinate_x) == elevator_room.coordinate_x,
                col(Room.coordinate_y) == elevator_room.coordinate_y - 1,
            )
        )
    )
    if elevator_above.first() is not None:
        raise ValueError("Cannot destroy this elevator: another elevator is stacked directly above it.")

    # D1: if this is the only elevator on its level, rooms there would be stranded.
    elevators_result = await db_session.exec(
        select(Room).where(and_(col(Room.vault_id) == elevator_room.vault_id, col(Room.name) == "Elevator"))
    )
    all_elevators = elevators_result.all()
    elevator_level = elevator_room.coordinate_y
    elevators_on_level = [
        elevator
        for elevator in all_elevators
        if elevator.coordinate_y == elevator_level and elevator.id != elevator_room.id
    ]
    if elevators_on_level:
        return

    rooms_on_level_result = await db_session.exec(
        select(Room).where(
            and_(
                col(Room.vault_id) == elevator_room.vault_id,
                col(Room.coordinate_y) == elevator_level,
                col(Room.name) != "Elevator",
                col(Room.id) != elevator_room.id,
            )
        )
    )
    other_rooms_on_level = list(rooms_on_level_result.all())
    if other_rooms_on_level:
        raise ValueError(
            f"Cannot destroy this elevator. It provides the only access to level {elevator_level} "
            f"which contains {len(other_rooms_on_level)} other room(s)."
        )
