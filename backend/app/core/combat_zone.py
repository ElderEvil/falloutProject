"""Shared Combat Zone constants.

The POI id is fixed so the migration seed and the map read agree even before the
row is visible in a test database (SQLite builds from metadata, not migrations).
"""

from uuid import UUID

from app.utils.places import normalize_place_name

COMBAT_ZONE_NAME = "The Combat Zone"
COMBAT_ZONE_NORMALIZED = normalize_place_name(COMBAT_ZONE_NAME)
COMBAT_ZONE_COORDS = (50.0, 50.0)
COMBAT_ZONE_LOCATION_ID = UUID("c0b4a7e2-5d3f-4a91-8c6e-2f7b1d9a4e83")
