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
) -> None:
    """Enforce R1 (elevator stacking) and R2 (level access) before a build."""
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
                Room.coordinate_y == elevator_room.coordinate_y + 1,
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
