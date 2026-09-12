"""Re-lay existing vaults onto the unit grid.

Backend rooms are stored in a unit space where a room occupies
``coordinate_x .. coordinate_x + size - 1`` (a standard room is 3 units, an
elevator 1). Older vaults were laid out with one room per column, which overlaps
under unit semantics, so they are re-laid floor by floor:

    door | elevator shaft | rooms to the right
    resource rooms fill the slots to the LEFT of the shaft

Every room keeps its floor, and every level gets an elevator in the shaft beside
the vault door.
"""

from __future__ import annotations

import logging
from operator import itemgetter
from typing import TYPE_CHECKING

from app import crud
from app.core.grid_config import ELEVATOR_UNITS, FLOOR_UNITS
from app.schemas.room import RoomCreate
from app.utils.room_rules import is_elevator
from app.utils.static_data import game_data_store

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.room import Room

logger = logging.getLogger(__name__)

RESOURCE_ROOM_NAMES = {"Power Generator", "Diner", "Water Treatment"}


def _size(room: Room) -> int:
    return room.size if room.size is not None else room.size_min


class VaultLayoutBackfillService:
    async def relayout(self, db_session: AsyncSession, vault_id: UUID, *, dry_run: bool = True) -> dict:
        rooms = await crud.room.get_all_by_vault(db_session, vault_id)
        if not rooms:
            return {"rooms": 0, "moved": 0, "elevators_to_add": 0, "overlaps": 0, "floating": 0}

        door = next((room for room in rooms if room.name.lower() == "vault door"), None)
        if door is not None:
            door.coordinate_x = 0
            door.coordinate_y = 0
        shaft_x = door.size if door is not None and door.size is not None else 6

        max_y = max((room.coordinate_y or 0) for room in rooms)
        targets: dict[UUID, tuple[int, int]] = {}

        for y in range(max_y + 1):
            level = [room for room in rooms if (room.coordinate_y or 0) == y]
            resource = sorted(
                (room for room in level if room.name in RESOURCE_ROOM_NAMES),
                key=lambda room: room.coordinate_x,
            )
            others = sorted(
                (
                    room
                    for room in level
                    if room is not door and not is_elevator(room.name) and room.name not in RESOURCE_ROOM_NAMES
                ),
                key=lambda room: room.coordinate_x,
            )

            right = shaft_x + ELEVATOR_UNITS
            for room in others:
                targets[room.id] = (right, y)
                right += _size(room)

            left = shaft_x
            for room in resource:
                size = _size(room)
                if left - size >= 0:
                    left -= size
                    targets[room.id] = (left, y)
                else:
                    targets[room.id] = (right, y)
                    right += size

            placed_elevator = next((room for room in level if is_elevator(room.name)), None)
            if placed_elevator is not None:
                targets[placed_elevator.id] = (shaft_x, y)

        elevators_by_level = {room.coordinate_y for room in rooms if is_elevator(room.name)}
        elevators_to_add = [y for y in range(max_y + 1) if y not in elevators_by_level]

        moved = sum(
            1 for room in rooms if room.id in targets and (room.coordinate_x, room.coordinate_y) != targets[room.id]
        )

        if not dry_run:
            for room in rooms:
                target = targets.get(room.id)
                if target is not None:
                    room.coordinate_x, room.coordinate_y = target
            await self._add_elevators(db_session, vault_id, shaft_x, elevators_to_add)

        overlaps, floating, floor_width_ok = self._validate(rooms, targets, elevators_to_add, shaft_x)
        return {
            "rooms": len(rooms),
            "moved": moved,
            "elevators_to_add": len(elevators_to_add),
            "overlaps": overlaps,
            "floating": floating,
            "floor_width_ok": floor_width_ok,
        }

    async def _add_elevators(self, db_session: AsyncSession, vault_id: UUID, shaft_x: int, levels: list[int]) -> None:
        template = game_data_store.get_room("Elevator")
        if template is None:
            raise ValueError("Elevator template missing from game data")
        for y in levels:
            room_in = RoomCreate(
                **template.model_dump()
                | {
                    "vault_id": vault_id,
                    "size": template.size_min,
                    "coordinate_x": shaft_x,
                    "coordinate_y": y,
                }
            )
            await crud.room.create(db_session, obj_in=room_in)

    def _validate(
        self,
        rooms: list[Room],
        targets: dict[UUID, tuple[int, int]],
        elevators_to_add: list[int],
        shaft_x: int,
    ) -> tuple[int, int, bool]:
        spans = [
            (
                targets.get(room.id, (room.coordinate_x or 0, room.coordinate_y or 0))[1],
                targets.get(room.id, (room.coordinate_x or 0, room.coordinate_y or 0))[0],
                targets.get(room.id, (room.coordinate_x or 0, room.coordinate_y or 0))[0] + _size(room) - 1,
            )
            for room in rooms
        ]
        spans.extend((y, shaft_x, shaft_x) for y in elevators_to_add)

        overlaps = 0
        floating = 0
        floor_width_ok = all(end < FLOOR_UNITS for _, _, end in spans)
        for y in {span[0] for span in spans}:
            level = sorted((span for span in spans if span[0] == y), key=itemgetter(1))
            for index, (_, start, end) in enumerate(level):
                if index + 1 < len(level) and level[index + 1][1] <= end:
                    overlaps += 1
                touches = (index > 0 and level[index - 1][2] + 1 == start) or (
                    index + 1 < len(level) and level[index + 1][1] == end + 1
                )
                if not touches:
                    floating += 1
        return overlaps, floating, floor_width_ok


vault_layout_backfill_service = VaultLayoutBackfillService()
