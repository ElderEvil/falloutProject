from datetime import timedelta
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ExplorationStatus, PlaceKindEnum
from app.crud.vault_slot import vault_slot
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.world_location import WorldLocation
from app.schemas.exploration_event import DiscoveryEventSchema
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service
from app.services.map import discovery
from app.services.map_service import map_service
from app.services.world_snapshot_service import world_snapshot_service
from app.utils import world_terrain
from app.utils.places import normalize_place_name, schematic_coords
from app.utils.time import utcnow
from app.utils.vault_slots import slot_coords


async def _save(db, *objs):
    for obj in objs:
        db.add(obj)
    await db.commit()


async def _depart(async_session: AsyncSession, vault: Vault, dweller: Dweller, *, heading: float = 90):
    slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await async_session.commit()
    snapshot = await world_snapshot_service.get_or_generate(async_session)
    exploration = await exploration_service.send_dweller(
        async_session, vault.id, dweller.id, duration=4, heading_degrees=heading
    )
    return exploration, slot_coords(slot.slot_index), snapshot


async def _discover(async_session: AsyncSession, exploration, name: str):
    exploration.start_time = utcnow() - timedelta(minutes=10)
    await async_session.commit()
    event = DiscoveryEventSchema(location_name=name, description=f"Discovered {name}.")
    with patch.object(event_generator, "generate_event", return_value=event):
        return await exploration_service.process_event(async_session, exploration)


def _place_at(name: str, x: float, y: float) -> WorldLocation:
    return WorldLocation(name=name, normalized_name=name.lower(), kind=PlaceKindEnum.PLACE, coord_x=x, coord_y=y)


async def _placed(db: AsyncSession, name: str, coords: tuple[float, float]) -> WorldLocation:
    place = _place_at(name, *coords)
    db.add(place)
    await db.commit()
    return place


def _radius(snapshot) -> float:
    return world_terrain.reveal_radius_registry(snapshot, world_terrain.SITE_REVEAL_TILES)


def _dist(origin, point) -> float:
    return ((point[0] - origin[0]) ** 2 + (point[1] - origin[1]) ** 2) ** 0.5


class TestSpatialDiscovery:
    pytestmark: ClassVar = [pytest.mark.asyncio, pytest.mark.usefixtures("default_world_snapshot")]

    async def test_spatial_route_follows_the_movement_trail_and_pending_status(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        exploration, _origin, _snapshot = await _depart(async_session, vault, dweller, heading=90)
        await exploration_service.advance(
            async_session, exploration.id, now=exploration.start_time + timedelta(hours=1)
        )

        async def route():
            routes = await discovery.get_discovery_routes(async_session, vault.id)
            return next(r for r in routes if r.exploration_id == exploration.id)

        current = await route()
        assert len(current.points) == 2
        assert [point.location_id for point in current.points] == [None, None]
        assert current.points[0].coord_x < current.points[1].coord_x  # heading east
        assert current.is_active is True

        exploration.start_return()
        await _save(async_session, exploration)
        assert (await route()).is_active is True

        exploration.status = ExplorationStatus.COMPLETED
        await _save(async_session, exploration)
        assert (await route()).is_active is False

    async def test_legacy_route_still_uses_discovery_events(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        """A legacy run (heading NULL) keeps the discovery-event route."""
        exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
        location = await _placed(async_session, "Old Depot", (30.0, 40.0))
        for description, x, y in (("found", 30.0, 40.0), ("found again", 30.5, 40.5)):
            exploration.add_event(
                event_type="discovery",
                description=description,
                location_name="Old Depot",
                location_id=location.id,
                coord_x=x,
                coord_y=y,
            )
        await _save(async_session, exploration)
        routes = await discovery.get_discovery_routes(async_session, vault.id)
        assert next(r for r in routes if r.exploration_id == exploration.id).points[0].location_id == location.id

    async def test_spatial_discovery_reuses_a_nearby_place_and_names_it_everywhere(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        exploration, origin, snapshot = await _depart(async_session, vault, dweller)
        nearby = await _placed(async_session, "Ruined Farm", (origin[0] + _radius(snapshot) / 2, origin[1]))
        original = (nearby.coord_x, nearby.coord_y)
        result = await _discover(async_session, exploration, "Crater of Mystery")
        event = result.events[-1]
        assert (UUID(event["location_id"]), event["location_name"], (nearby.coord_x, nearby.coord_y)) == (
            nearby.id,
            "Ruined Farm",
            original,
        )
        # Journal, map link, and bio all describe the claimed place, never the generated name.
        assert (("Ruined Farm" in event["description"]), "Crater of Mystery" in event["description"]) == (True, False)

    async def test_spatial_discovery_places_a_new_place_near_the_position_on_land(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        exploration, origin, snapshot = await _depart(async_session, vault, dweller)
        result = await _discover(async_session, exploration, "Lonely Water Tower")
        created = await async_session.get(WorldLocation, UUID(result.events[-1]["location_id"]))
        assert created is not None
        assert not world_terrain.is_blocked(snapshot, created.coord_x, created.coord_y)
        assert _dist(origin, (created.coord_x, created.coord_y)) <= _radius(snapshot)

        result = await _discover(async_session, exploration, "Whispering Cave")
        created = await async_session.get(WorldLocation, UUID(result.events[-1]["location_id"]))
        assert (created.coord_x, created.coord_y) != schematic_coords(normalize_place_name("Whispering Cave"))

    async def test_spatial_discovery_ignores_a_distant_same_name_twin(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        exploration, origin, snapshot = await _depart(async_session, vault, dweller)
        twin_spot = max(
            [(10.0, 10.0), (90.0, 10.0), (10.0, 90.0), (90.0, 90.0)],
            key=lambda spot: (spot[0] - origin[0]) ** 2 + (spot[1] - origin[1]) ** 2,
        )
        twin = await _placed(async_session, "Distant Twin Cave", twin_spot)
        twin_coords = (twin.coord_x, twin.coord_y)
        result = await _discover(async_session, exploration, "Distant Twin Cave")
        event = result.events[-1]
        assert UUID(event["location_id"]) != twin.id
        created = await async_session.get(WorldLocation, UUID(event["location_id"]))
        assert created.name == "Distant Twin Cave"
        assert created.normalized_name.startswith(f"{exploration.id}:")
        assert created.normalized_name != twin.normalized_name
        assert _dist(origin, (created.coord_x, created.coord_y)) <= _radius(snapshot)
        assert (twin.coord_x, twin.coord_y) == twin_coords

    async def test_spatial_registration_splits_by_name_and_merges_by_position(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        exploration, _origin, snapshot = await _depart(async_session, vault, dweller)

        async def register(coords):
            return await map_service.register_spatial_discovery(
                async_session, vault.id, exploration.id, dweller.id, "Echo Cave", coords, snapshot.generator_version
            )

        first, second = await register((20.0, 20.0)), await register((80.0, 80.0))
        assert first is not None
        assert second is not None
        assert first.id != second.id
        assert first.normalized_name.startswith(f"{exploration.id}:")
        assert second.normalized_name.startswith(f"{exploration.id}:")
        assert first.normalized_name != second.normalized_name
        assert (await register((20.0, 20.0))).id == first.id

    async def test_nearest_land_escapes_water(self) -> None:
        snap = SimpleNamespace(config={"width": 4, "height": 1}, terrain=["water", "water", "wasteland", "water"])
        x, y = world_terrain.nearest_land(snap, 10.0, 50.0)  # tile 0, water
        assert snap.terrain[int(y / 100 * 1) * 4 + int(x / 100 * 4)] == "wasteland"
