"""Road geometry is reproducible, connected, and preserves the existing base world."""

from collections import Counter
from itertools import pairwise, starmap

import pytest

from app.services.map.road_generation import generate_roads, road_segment_clear
from app.services.map.world_generation import WorldRecipe, generate_world, snapshot_checksum


@pytest.mark.parametrize("seed", ["wasteland-atlas-v1", "road-test-a", "road-test-b"])
def test_roads_reproduce_without_changing_geography_and_stay_on_land(seed):
    world = generate_world(WorldRecipe(seed=seed))
    original = snapshot_checksum(world)
    args = {
        "terrain": list(world.terrain),
        "width": world.width,
        "height": world.height,
        "seed": seed,
        "base_checksum": original,
    }
    roads = generate_roads(**args)
    assert roads.model_dump_json() == generate_roads(**args).model_dump_json()
    assert snapshot_checksum(world) == original
    assert roads.base_checksum == original
    assert {r.kind for r in roads.segments} == {"highway", "country", "railroad"}
    assert len(roads.segments) <= 85
    assert len({r.id for r in roads.segments}) == len(roads.segments)
    for road in roads.segments:
        for a, b in pairwise(road.points):
            assert road_segment_clear(list(world.terrain), world.width, world.height, a, b)
    # Smoothing must preserve exact junction vertices across the whole network.
    for rail in (False, True):
        network = [r for r in roads.segments if (r.kind == "railroad") == rail]
        joined = {0}
        points = set(network[0].points)
        while True:
            previous = len(joined)
            for i, road in enumerate(network):
                if points.intersection(road.points):
                    joined.add(i)
                    points.update(road.points)
            if len(joined) == previous:
                break
        assert len(joined) == len(network)
    counts = Counter(p for road in roads.segments for p in road.points)
    for road in roads.segments:
        if road.kind == "country":
            assert counts[road.points[-1]] > 1
    assert any(abs(x / 1.25 - 0.5 - round(x / 1.25 - 0.5)) > 0.01 for r in roads.segments for x, _ in r.points)


def test_casing_cannot_clip_water_even_when_the_centerline_is_on_land():
    terrain = ["wasteland"] * 100
    terrain[55] = "water"
    assert not road_segment_clear(terrain, 10, 10, (49.8, 40), (49.8, 70))
    assert road_segment_clear(terrain, 10, 10, (49, 40), (49, 70))
    assert not road_segment_clear(terrain, 10, 10, (40, 40), (70, 70))


def test_water_barrier_and_island_do_not_get_roads():
    width = height = 40
    terrain = ["ruins" if x < 25 or x > 30 else "water" for _y in range(height) for x in range(width)]
    roads = generate_roads(terrain=terrain, width=width, height=height, seed="barrier", base_checksum="base")
    assert roads.segments
    for road in roads.segments:
        assert all(x < 62.5 for x, _y in road.points)
        assert all(road_segment_clear(terrain, width, height, a, b) for a, b in pairwise(road.points))


def test_water_only_world_has_an_explicit_empty_network():
    roads = generate_roads(terrain=["water"] * 4, width=2, height=2, seed="sea", base_checksum="base")
    assert roads.segments == []
    assert roads.checksum


@pytest.mark.parametrize(
    ("terrain", "width", "height"), [(["wasteland"], 0, 1), (["water"], 2, 2), (["unknown"], 1, 1)]
)
def test_invalid_grid_fails_clearly(terrain, width, height):
    with pytest.raises(ValueError, match="terrain grid"):
        generate_roads(terrain=terrain, width=width, height=height, seed="bad", base_checksum="base")


def test_default_network_has_more_local_roads_and_visible_curves():
    import math

    world = generate_world(WorldRecipe(seed="wasteland-atlas-v1"))
    roads = generate_roads(
        terrain=list(world.terrain),
        width=80,
        height=80,
        seed="wasteland-atlas-v1",
        base_checksum=snapshot_checksum(world),
    )
    assert len(roads.segments) >= 30
    local = [r for r in roads.segments if r.kind == "country"]
    assert len(local) >= 22
    # Judge curvature on routes, excluding short access spurs added for coverage.
    # Curvature must affect the road's course, not just round grid corners.
    local = [r for r in local if math.dist(r.points[0], r.points[-1]) >= 6]
    assert len(local) >= 22
    curved = 0
    for road in local:
        chord = math.dist(road.points[0], road.points[-1])
        length = sum(starmap(math.dist, pairwise(road.points)))
        curved += length > chord * 1.04
    assert curved >= len(local) * 0.65


def test_railroad_keeps_open_corridors_straight():
    from random import Random

    from app.services.map.road_generation import _geometry

    points = [(float(x), 50.0) for x in range(10, 91)]
    result = _geometry(points, {(50.0, 50.0)}, lambda a, b: True, Random(1), "railroad")
    assert all(y == 50 for _, y in result)
    assert len(result) <= 4
    assert (50.0, 50.0) in result


def test_default_roads_reach_outer_regions_with_a_denser_network():
    world = generate_world(WorldRecipe(seed="wasteland-atlas-v1"))
    roads = generate_roads(
        terrain=list(world.terrain),
        width=80,
        height=80,
        seed="wasteland-atlas-v1",
        base_checksum=snapshot_checksum(world),
    )
    local = [r for r in roads.segments if r.kind == "country"]
    assert len(local) >= 60
    points = [point for road in local for point in road.points]
    assert min(x for x, _ in points) < 7
    assert max(x for x, _ in points) > 93
    assert min(y for _, y in points) < 7
    assert max(y for _, y in points) > 93


def _access_road_for(origin):
    """Build one country backbone and ask for an access spur at `origin` (0-100 units, all land)."""
    from uuid import uuid4

    from app.schemas.world_snapshot import WorldRoadRead, WorldRoadsRead
    from app.services.map.road_generation import place_access_road

    roads = WorldRoadsRead(
        version=4,
        base_checksum="base",
        checksum="roads",
        segments=[WorldRoadRead(id="main", kind="country", points=[(50.5, 50.5), (50.5, 60.5)])],
    )
    return (
        place_access_road(
            terrain=["wasteland"] * 10000,
            width=100,
            height=100,
            origin=origin,
            land=set(range(10000)),
            vertices=set(roads.segments[0].points),
            location_id=str(uuid4()),
        ),
        set(roads.segments[0].points),
    )


@pytest.mark.parametrize(("origin", "expected"), [((49.5, 50.5), True), ((48.4, 50.5), False)])
def test_access_roads_leave_distant_places_off_road(origin, expected):
    access, _ = _access_road_for(origin)
    assert (access is not None) == expected


@pytest.mark.parametrize(("origin", "on_road"), [((50.5, 50.5), True), ((50.8, 50.5), True), ((49.5, 50.5), False)])
def test_places_already_standing_on_the_network_get_no_access_spur(origin, on_road):
    from app.services.map.road_generation import place_on_road

    access, vertices = _access_road_for(origin)
    assert place_on_road(origin, vertices) is on_road
    if on_road:
        assert access is None
    else:
        assert access is not None


def test_access_road_rejects_short_distance_with_long_water_detour():
    from uuid import uuid4

    from app.services.map.road_generation import place_access_road

    terrain = ["wasteland"] * 10000
    terrain[5050] = "water"
    assert (
        place_access_road(
            terrain=terrain,
            width=100,
            height=100,
            origin=(49.5, 50.5),
            land=set(range(10000)) - {5050},
            vertices={(51.5, 50.5)},
            location_id=str(uuid4()),
        )
        is None
    )
