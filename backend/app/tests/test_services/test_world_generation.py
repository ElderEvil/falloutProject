import pytest

from app.services.map.world_generation import (
    TRAVEL_COST,
    PublicAnchor,
    WorldConfig,
    WorldRecipe,
    _is_traversable,
    generate_slots,
    generate_terrain,
    generate_world,
)


def _recipe(**overrides):
    return WorldRecipe(seed="unit-seed", config=WorldConfig(**overrides))


def test_same_recipe_is_fully_deterministic_and_ignores_occupancy():
    a = generate_world(_recipe())
    b = generate_world(_recipe())
    assert a.terrain == b.terrain
    assert a.slots == b.slots
    assert a.recipe_fingerprint == b.recipe_fingerprint
    assert a.recipe_fingerprint == generate_world(_recipe()).recipe_fingerprint
    assert [(s.tile_x, s.tile_y) for s in a.slots] == [(s.tile_x, s.tile_y) for s in b.slots]


def test_fingerprint_reacts_to_seed_and_anchors():
    a = generate_world(WorldRecipe(seed="seed-a"))
    b = generate_world(WorldRecipe(seed="seed-b"))
    assert a.recipe_fingerprint != b.recipe_fingerprint
    assert a.terrain != b.terrain

    plain = WorldRecipe(seed="s")
    anchored = WorldRecipe(seed="s", anchors=(PublicAnchor("v1", 12.5, 40.0),))
    assert plain.fingerprint() != anchored.fingerprint()


def test_terrain_uses_only_contract_types_and_quantiles():
    world = generate_world(_recipe())
    assert set(world.terrain) <= set(TRAVEL_COST)
    assert "forest" in world.terrain

    empty = generate_world(_recipe(water_quantile=0, hills_quantile=0, forest_quantile=0))
    assert "water" not in empty.terrain
    assert "hills" not in empty.terrain
    assert "forest" not in empty.terrain


def test_slots_are_land_safe_unique_spaced_sequential_and_on_tile_centers():
    recipe = _recipe()
    world = generate_world(recipe)
    assert len(world.slots) == recipe.config.slot_count
    assert [s.slot_index for s in world.slots] == list(range(len(world.slots)))
    seen: set[tuple[int, int]] = set()
    for slot in world.slots:
        assert world.terrain[slot.tile_y * world.width + slot.tile_x] != "water"
        assert 0 <= slot.tile_x < world.width
        assert 0 <= slot.tile_y < world.height
        assert (slot.tile_x, slot.tile_y) not in seen
        assert slot.coord_x == round((slot.tile_x + 0.5) * (100 / world.width), 4)
        assert slot.coord_y == round((slot.tile_y + 0.5) * (100 / world.height), 4)
        seen.add((slot.tile_x, slot.tile_y))
    spacing_sq = recipe.config.slot_min_spacing**2
    cells = [(s.tile_x, s.tile_y) for s in world.slots]
    for i, (x, y) in enumerate(cells):
        for cx, cy in cells[i + 1 :]:
            assert (x - cx) ** 2 + (y - cy) ** 2 >= spacing_sq


def test_slots_share_one_traversable_component():
    world = generate_world(_recipe())
    reached = {world.slots[0].tile_y * world.width + world.slots[0].tile_x}
    frontier = list(reached)
    while frontier:
        idx = frontier.pop()
        x, y = idx % world.width, idx // world.width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < world.width and 0 <= ny < world.height:
                nidx = ny * world.width + nx
                if nidx not in reached and _is_traversable(world.terrain, world.width, nx, ny):
                    reached.add(nidx)
                    frontier.append(nidx)
    for slot in world.slots:
        assert slot.tile_y * world.width + slot.tile_x in reached


def test_generation_fails_clearly_when_slots_cannot_be_placed():
    # An impossibly large spacing must raise, never fall back to unsafe coordinates.
    recipe = WorldRecipe(seed="s", config=WorldConfig(slot_count=100, slot_min_spacing=999))
    terrain = generate_terrain(recipe)
    with pytest.raises(RuntimeError, match="slots"):
        generate_slots(recipe, terrain)
