"""Grid geometry payload — the backend is the source of truth for the vault grid."""

from pydantic import BaseModel

from app.core.grid_config import (
    ELEVATOR_UNITS,
    FLOOR_UNITS,
    GRID_BUILD_Y_MAX,
    GRID_Y_MAX,
    SHAFT_X,
    UNITS_PER_ROOM,
    room_slot_starts,
)


class GridConfig(BaseModel):
    units_per_room: int
    elevator_units: int
    floor_units: int
    shaft_x: int
    left_slot_starts: list[int]
    right_slot_starts: list[int]
    y_max: int
    build_y_max: int


def grid_config() -> GridConfig:
    left, right = room_slot_starts()
    return GridConfig(
        units_per_room=UNITS_PER_ROOM,
        elevator_units=ELEVATOR_UNITS,
        floor_units=FLOOR_UNITS,
        shaft_x=SHAFT_X,
        left_slot_starts=left,
        right_slot_starts=right,
        y_max=GRID_Y_MAX,
        build_y_max=GRID_BUILD_Y_MAX,
    )
