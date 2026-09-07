"""Vault grid geometry shared by persistence, validation, and CRUD layers."""

# Hard caps include reserved expansion space; build bounds match the current UI.
GRID_X_MIN = 0
GRID_X_MAX = 9
GRID_Y_MIN = 0
GRID_Y_MAX = 25
GRID_BUILD_X_MAX = 7
GRID_BUILD_Y_MAX = 15
