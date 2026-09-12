"""Vault grid geometry shared by persistence, validation, and CRUD layers.

The grid is measured in *units*: a standard room spans ``UNITS_PER_ROOM`` units,
an elevator a single unit, and a room's persisted footprint is
``coordinate_x .. coordinate_x + size - 1``.
"""

UNITS_PER_ROOM = 3
ELEVATOR_UNITS = 1

# One floor is as wide as the vault door plus the elevator shaft plus eight
# room slots, so a full floor fits the viewport without horizontal scrolling.
FLOOR_UNITS = 6 + ELEVATOR_UNITS + 8 * UNITS_PER_ROOM

# Hard caps include reserved expansion space; build bounds match the current UI.
GRID_X_MIN = 0
GRID_X_MAX = FLOOR_UNITS - 1
GRID_Y_MIN = 0
GRID_Y_MAX = 25
GRID_BUILD_X_MAX = FLOOR_UNITS - 1
GRID_BUILD_Y_MAX = 15
