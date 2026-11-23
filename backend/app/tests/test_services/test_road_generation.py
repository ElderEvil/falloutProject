import math
from collections import Counter
from itertools import pairwise, starmap
from random import Random
from uuid import uuid4

import pytest

from app.services.map.road_generation import (
    _geometry,
    generate_roads,
    place_access_road,
    place_on_road,
    road_segment_clear,
)
from app.services.map.world_generation import WorldRecipe, generate_world, snapshot_checksum

SEED = "wasteland-atlas-v1"
_BACKBONE = {(50.5, 50.5), (50.5, 60.5)}


def _roads_for_world(seed):
    world = generate_world(WorldRecipe(seed=seed))
    original = snapshot_checksum(world)
    roads = generate_roads(
        terrain=list(world.terrain), width=world.width, height=world.height, seed=seed, base_checksum=original
    )
    return world, original, roads


def _roads(terrain, width, height, seed):
    return generate_roads(terrain=terrain, width=width, height=height, seed=seed, base_checksum="base")


def _spur(origin, *, terrain=None, land=None, vertices=_BACKBONE):
    return place_access_road(
        terrain=terrain or ["wasteland"] * 10000,
        width=100,
        height=100,
        origin=origin,
        land=land or set(range(10000)),
        vertices=vertices,
        location_id=str(uuid4()),
    )


def _junction_connected(segments):
    # Smoothing must preserve exact junction vertices across the whole network.
    joined, points = {0}, set(segments[0].points)
    while True:
        previous = len(joined)
        for i, road in enumerate(segments):
            if points.intersection(road.points):
                joined.add(i)
                points.update(road.points)
        if len(joined) == previous:
            return len(joined) == len(segments)


@pytest.mark.parametrize("seed", [SEED, "road-test-a", "road-test-b"])
def test_roads_reproduce_without_changing_geography_and_stay_on_land(seed):
    world, original, roads = _roads_for_world(seed)
    assert roads.model_dump_json() == _roads_for_world(seed)[2].model_dump_json()
    assert snapshot_checksum(world) == original
    assert roads.base_checksum == original
    assert {r.kind for r in roads.segments} == {"highway", "country", "railroad"}
    assert len(roads.segments) <= 85
    assert len({r.id for r in roads.segments}) == len(roads.segments)
    for road in roads.segments:
        for a, b in pairwise(road.points):
            assert road_segment_clear(list(world.terrain), world.width, world.height, a, b)
    for rail in (False, True):
        assert _junction_connected([r for r in roads.segments if (r.kind == "railroad") == rail])
    counts = Counter(p for road in roads.segments for p in road.points)
    for road in roads.segments:
        if road.kind == "country":
            assert counts[road.points[-1]] > 1
    assert any(abs(x / 1.25 - 0.5 - round(x / 1.25 - 0.5)) > 0.01 for r in roads.segments for x, _ in r.points)


def test_water_never_gets_roads_and_casing_cannot_clip_it():
    terrain = ["wasteland"] * 100
    terrain[55] = "water"
    assert not road_segment_clear(terrain, 10, 10, (49.8, 40), (49.8, 70))
    assert road_segment_clear(terrain, 10, 10, (49, 40), (49, 70))
    assert not road_segment_clear(terrain, 10, 10, (40, 40), (70, 70))

    width = height = 40
    island = ["ruins" if x < 25 or x > 30 else "water" for _y in range(height) for x in range(width)]
    roads = _roads(island, width, height, "barrier")
    assert roads.segments
    for road in roads.segments:
        assert all(x < 62.5 for x, _y in road.points)
        assert all(road_segment_clear(island, width, height, a, b) for a, b in pairwise(road.points))

    empty = _roads(["water"] * 4, 2, 2, "sea")
    assert empty.segments == []
    assert empty.checksum


@pytest.mark.parametrize(
    ("terrain", "width", "height"), [(["wasteland"], 0, 1), (["water"], 2, 2), (["unknown"], 1, 1)]
)
def test_invalid_grid_fails_clearly(terrain, width, height):
    with pytest.raises(ValueError, match="terrain grid"):
        _roads(terrain, width, height, "bad")


def test_default_network_is_dense_curved_and_reaches_outer_regions():
    _, _, roads = _roads_for_world(SEED)
    assert len(roads.segments) >= 30
    local = [r for r in roads.segments if r.kind == "country"]
    assert len(local) >= 22
    # Judge curvature on routes, excluding short access spurs added for coverage.
    local = [r for r in local if math.dist(r.points[0], r.points[-1]) >= 6]
    assert len(local) >= 22
    curved = 0
    for road in local:
        chord = math.dist(road.points[0], road.points[-1])
        length = sum(starmap(math.dist, pairwise(road.points)))
        curved += length > chord * 1.04
    assert curved >= len(local) * 0.65

    assert len([r for r in roads.segments if r.kind == "country"]) >= 60
    points = [point for road in roads.segments if road.kind == "country" for point in road.points]
    assert min(x for x, _ in points) < 7
    assert max(x for x, _ in points) > 93
    assert min(y for _, y in points) < 7
    assert max(y for _, y in points) > 93


def test_railroad_keeps_open_corridors_straight():
    points = [(float(x), 50.0) for x in range(10, 91)]
    result = _geometry(points, {(50.0, 50.0)}, lambda a, b: True, Random(1), "railroad")
    assert all(y == 50 for _, y in result)
    assert len(result) <= 4
    assert (50.0, 50.0) in result


def _access_road_for(origin):
    # One country backbone (0-100 units, all land) that a spur may join.
    return _spur(origin)


@pytest.mark.parametrize(
    ("origin", "on_road", "spur"),
    [
        ((49.5, 50.5), False, True),
        ((48.4, 50.5), False, False),
        ((50.5, 50.5), True, False),
        ((50.8, 50.5), True, False),
    ],
)
def test_access_spurs_skip_network_vertices_and_distant_places(origin, on_road, spur):
    access = _access_road_for(origin)
    assert place_on_road(origin, _BACKBONE) is on_road
    assert (access is not None) is spur


def test_access_road_rejects_short_distance_with_long_water_detour():
    terrain = ["wasteland"] * 10000
    terrain[5050] = "water"
    access = _spur((49.5, 50.5), terrain=terrain, land=set(range(10000)) - {5050}, vertices={(51.5, 50.5)})
    assert access is None
