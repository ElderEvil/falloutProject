"""Vault grid geometry shared by persistence, validation, and CRUD layers.

The grid is measured in *units*: a standard room spans ``UNITS_PER_ROOM`` units,
an elevator a single unit, and a room's persisted footprint is
``coordinate_x .. coordinate_x + size - 1``.
"""

UNITS_PER_ROOM = 3
ELEVATOR_UNITS = 1

# One floor: the vault-door region holds two room slots, then the elevator shaft,
# then the room slots to its right.
DOOR_UNITS = 6
SHAFT_X = DOOR_UNITS
RIGHT_SLOT_COUNT = 7
FLOOR_UNITS = SHAFT_X + ELEVATOR_UNITS + RIGHT_SLOT_COUNT * UNITS_PER_ROOM

# Hard caps include reserved expansion space; build bounds match the current UI.
GRID_X_MIN = 0
GRID_X_MAX = FLOOR_UNITS - 1
GRID_Y_MIN = 0
GRID_Y_MAX = 25
GRID_BUILD_X_MAX = FLOOR_UNITS - 1
GRID_BUILD_Y_MAX = 15


def room_slot_starts() -> tuple[list[int], list[int]]:
    """Build-slot unit offsets left and right of the elevator shaft."""
    left = [0, UNITS_PER_ROOM]
    right = [
        SHAFT_X + ELEVATOR_UNITS + index * UNITS_PER_ROOM for index in range(RIGHT_SLOT_COUNT)
    ]
    return left, right
