"""Spatial discoveries (slice 2): corridor routes + discoveries local to the path."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import PlaceKindEnum
from app.crud.vault_slot import vault_slot
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.world_location import WorldLocation
from app.schemas.exploration_event import DiscoveryEventSchema
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service
from app.services.world_snapshot_service import world_snapshot_service
from app.utils import world_terrain
from app.utils.vault_slots import slot_coords


async def _depart(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, *, heading: float = 90, duration: int = 4
):
    slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await async_session.commit()
    snapshot = await world_snapshot_service.get_or_generate(async_session)
    exploration = await exploration_service.send_dweller(
        async_session, vault.id, dweller.id, duration=duration, heading_degrees=heading
    )
    return exploration, slot_coords(slot.slot_index), snapshot


async def _discover(async_session: AsyncSession, exploration, name: str):
    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()
    event = DiscoveryEventSchema(location_name=name, description=f"Discovered {name}.")
    with patch.object(event_generator, "generate_event", return_value=event):
        return await exploration_service.process_event(async_session, exploration)


def _place_at(name: str, x: float, y: float) -> WorldLocation:
    return WorldLocation(
        name=name,
        normalized_name=name.lower(),
        kind=PlaceKindEnum.PLACE,
        coord_x=x,
        coord_y=y,
    )


# ---------------------------------------------------------------------------
# step 3: the route follows movement, so the fog corridor follows it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spatial_route_follows_the_movement_trail(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A spatial run's route is its movement trail, not discovery events."""
    exploration, origin, _snapshot = await _depart(async_session, vault, dweller, heading=90)
    await exploration_service.advance(async_session, exploration.id, now=exploration.start_time + timedelta(hours=1))

    routes = await map_service._get_discovery_routes(async_session, vault.id)

    route = next(r for r in routes if r.exploration_id == exploration.id)
    assert len(route.points) == 2
    assert [point.location_id for point in route.points] == [None, None]
    assert route.points[0].coord_x < route.points[1].coord_x  # heading east


@pytest.mark.asyncio
async def test_legacy_route_still_uses_discovery_events(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A legacy run (heading NULL) keeps the discovery-event route."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    location = _place_at("Old Depot", 30.0, 40.0)
    async_session.add(location)
    await async_session.commit()
    exploration.add_event(
        event_type="discovery",
        description="found",
        location_name="Old Depot",
        location_id=location.id,
        coord_x=30.0,
        coord_y=40.0,
    )
    exploration.add_event(
        event_type="discovery",
        description="found again",
        location_name="Old Depot",
        location_id=location.id,
        coord_x=30.5,
        coord_y=40.5,
    )
    async_session.add(exploration)
    await async_session.commit()

    routes = await map_service._get_discovery_routes(async_session, vault.id)

    route = next(r for r in routes if r.exploration_id == exploration.id)
    assert route.points[0].location_id == location.id


# ---------------------------------------------------------------------------
# step 4: discoveries are local to the traveled path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spatial_discovery_reuses_a_nearby_place(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A place within the site radius is claimed in place, coordinates unchanged."""
    exploration, origin, snapshot = await _depart(async_session, vault, dweller)
    radius = world_terrain.reveal_radius_registry(snapshot, world_terrain.SITE_REVEAL_TILES)
    nearby = _place_at("Ruined Farm", origin[0] + radius / 2, origin[1])
    async_session.add(nearby)
    await async_session.commit()
    original = (nearby.coord_x, nearby.coord_y)

    result = await _discover(async_session, exploration, "Crater of Mystery")

    event = result.events[-1]
    assert UUID(event["location_id"]) == nearby.id
    assert event["location_name"] == "Ruined Farm"
    assert (nearby.coord_x, nearby.coord_y) == original


@pytest.mark.asyncio
async def test_spatial_discovery_places_a_new_place_near_the_position_on_land(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """With nothing nearby, a new place is created near the position, on land."""
    exploration, origin, snapshot = await _depart(async_session, vault, dweller)

    result = await _discover(async_session, exploration, "Lonely Water Tower")

    event = result.events[-1]
    created = await async_session.get(WorldLocation, UUID(event["location_id"]))
    assert created is not None
    assert not world_terrain.is_blocked(snapshot, created.coord_x, created.coord_y)
    radius = world_terrain.reveal_radius_registry(snapshot, world_terrain.SITE_REVEAL_TILES)
    distance = ((created.coord_x - origin[0]) ** 2 + (created.coord_y - origin[1]) ** 2) ** 0.5
    assert distance <= radius


@pytest.mark.asyncio
async def test_spatial_discovery_is_not_name_derived(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """The placed discovery does not sit at the name hash's schematic coordinates."""
    from app.utils.places import normalize_place_name, schematic_coords

    exploration, _origin, _snapshot = await _depart(async_session, vault, dweller)

    result = await _discover(async_session, exploration, "Whispering Cave")

    created = await async_session.get(WorldLocation, UUID(result.events[-1]["location_id"]))
    assert (created.coord_x, created.coord_y) != schematic_coords(normalize_place_name("Whispering Cave"))


@pytest.mark.asyncio
async def test_spatial_discovery_ignores_a_distant_same_name_twin(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A same-name row outside the site radius is not this discovery: a journey-keyed row lands near the explorer."""
    exploration, origin, snapshot = await _depart(async_session, vault, dweller)
    radius = world_terrain.reveal_radius_registry(snapshot, world_terrain.SITE_REVEAL_TILES)
    twin_spot = max(
        [(10.0, 10.0), (90.0, 10.0), (10.0, 90.0), (90.0, 90.0)],
        key=lambda spot: (spot[0] - origin[0]) ** 2 + (spot[1] - origin[1]) ** 2,
    )
    twin = _place_at("Distant Twin Cave", *twin_spot)
    async_session.add(twin)
    await async_session.commit()
    twin_coords = (twin.coord_x, twin.coord_y)

    result = await _discover(async_session, exploration, "Distant Twin Cave")

    event = result.events[-1]
    assert UUID(event["location_id"]) != twin.id
    created = await async_session.get(WorldLocation, UUID(event["location_id"]))
    assert created.name == "Distant Twin Cave"
    assert created.normalized_name.startswith(f"{exploration.id}:")
    assert created.normalized_name != twin.normalized_name
    distance = ((created.coord_x - origin[0]) ** 2 + (created.coord_y - origin[1]) ** 2) ** 0.5
    assert distance <= radius
    assert (twin.coord_x, twin.coord_y) == twin_coords


@pytest.mark.asyncio
async def test_same_name_twice_in_one_journey_makes_two_rows(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Journey identity is per discovery: a repeated name at a new position gets its own row."""
    exploration, _origin, snapshot = await _depart(async_session, vault, dweller)

    first = await map_service.register_spatial_discovery(
        async_session, vault.id, exploration.id, dweller.id, "Echo Cave", (20.0, 20.0), snapshot.generator_version
    )
    second = await map_service.register_spatial_discovery(
        async_session, vault.id, exploration.id, dweller.id, "Echo Cave", (80.0, 80.0), snapshot.generator_version
    )

    assert first is not None
    assert second is not None
    assert first.id != second.id
    assert first.normalized_name.startswith(f"{exploration.id}:")
    assert second.normalized_name.startswith(f"{exploration.id}:")
    assert first.normalized_name != second.normalized_name


@pytest.mark.asyncio
async def test_same_position_twice_merges_into_one_row(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Position-derived identity is stable: concurrent discoveries at one spot share the row."""
    exploration, _origin, snapshot = await _depart(async_session, vault, dweller)

    first = await map_service.register_spatial_discovery(
        async_session, vault.id, exploration.id, dweller.id, "Echo Cave", (20.0, 20.0), snapshot.generator_version
    )
    second = await map_service.register_spatial_discovery(
        async_session, vault.id, exploration.id, dweller.id, "Echo Cave", (20.0, 20.0), snapshot.generator_version
    )

    assert first is not None
    assert second is not None
    assert first.id == second.id


@pytest.mark.asyncio
async def test_spatial_discovery_record_names_the_resolved_place(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Journal, map link, and bio all describe the claimed place, never the generated name."""
    exploration, origin, snapshot = await _depart(async_session, vault, dweller)
    radius = world_terrain.reveal_radius_registry(snapshot, world_terrain.SITE_REVEAL_TILES)
    nearby = _place_at("Ruined Farm", origin[0] + radius / 2, origin[1])
    async_session.add(nearby)
    await async_session.commit()

    result = await _discover(async_session, exploration, "Crater of Mystery")

    event = result.events[-1]
    assert UUID(event["location_id"]) == nearby.id
    assert event["location_name"] == "Ruined Farm"
    assert "Ruined Farm" in event["description"]
    assert "Crater of Mystery" not in event["description"]


@pytest.mark.asyncio
async def test_nearest_land_escapes_water() -> None:
    """nearest_land returns a non-water point for a water registry position."""
    snap = SimpleNamespace(config={"width": 4, "height": 1}, terrain=["water", "water", "wasteland", "water"])

    x, y = world_terrain.nearest_land(snap, 10.0, 50.0)  # tile 0, water

    assert snap.terrain[int(y / 100 * 1) * 4 + int(x / 100 * 4)] == "wasteland"
