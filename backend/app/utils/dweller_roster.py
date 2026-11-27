"""Roster shaping helpers shared by the tick and vault seeding."""

from typing import Any


def group_dwellers_by_room(dwellers: list[Any]) -> dict[str, list[Any]]:
    """Group dwellers by their room_id."""
    room_dwellers: dict[str, list[Any]] = {}
    for dweller in dwellers:
        if dweller.room_id not in room_dwellers:
            room_dwellers[dweller.room_id] = []
        room_dwellers[dweller.room_id].append(dweller)
    return room_dwellers
