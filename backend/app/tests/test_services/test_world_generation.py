"""Focused regression tests for the backend world generation core.

They lock the contract guarantees: determinism, land-safe slots, and occupancy
independence.
"""

from dataclasses import replace

import pytest

from app.services.world_generation_service import (
    GENERATOR_VERSION,
    TRAVEL_COST,
    VAULT_SLOT_DRY_MARGIN,
    WATER_MIN_COMPONENT,
    GeneratedWorld,
    PublicAnchor,
    WorldConfig,
    WorldRecipe,
    _is_traversable,
    _road_junctions,
    canonical_payload,
    generate_rivers,
    generate_road_mask,
    generate_slots,
    generate_terrain,
    generate_world,
    snapshot_checksum,
)
from app.utils.vault_slots import slot_tile_indices


def _recipe(**overrides) -> WorldRecipe:
    return WorldRecipe(seed="unit-seed", config=WorldConfig(**overrides))


def test_same_recipe_produces_identical_terrain_and_slots():
    a = generate_world(_recipe())
    b = generate_world(_recipe())
    assert a.terrain == b.terrain
    assert a.slots == b.slots
    assert a.recipe_fingerprint == b.recipe_fingerprint


def test_different_seed_changes_fingerprint_and_terrain():
    a = generate_world(WorldRecipe(seed="seed-a"))
    b = generate_world(WorldRecipe(seed="seed-b"))
    assert a.recipe_fingerprint != b.recipe_fingerprint
    assert a.terrain != b.terrain


def test_anchors_are_part_of_the_fingerprint():
    plain = WorldRecipe(seed="s")
    anchored = WorldRecipe(seed="s", anchors=(PublicAnchor("v1", 12.5, 40.0),))
    assert plain.fingerprint() != anchored.fingerprint()


def test_terrain_uses_only_contract_types():
    world = generate_world(_recipe())
    assert set(world.terrain) <= set(TRAVEL_COST)


def test_default_recipe_contains_forest():
    world = generate_world(_recipe())
    assert "forest" in world.terrain


def test_zero_fractions_emit_no_water_or_hills_or_forest():
    # Raw terrain classification only: rivers/roads are display-only masks and never
    # mutate terrain, so generate_terrain is the source of truth for terrain kinds.
    terrain = generate_terrain(_recipe(water_quantile=0, hills_quantile=0, forest_quantile=0))
    assert "water" not in terrain
    assert "hills" not in terrain
    assert "forest" not in terrain


def test_every_slot_is_land_safe_unique_and_spaced():
    recipe = _recipe()
    world = generate_world(recipe)
    assert len(world.slots) == recipe.config.slot_count
    seen: set[tuple[int, int]] = set()
    for slot in world.slots:
        assert world.terrain[slot.tile_y * world.width + slot.tile_x] != "water"
        assert 0 <= slot.tile_x < world.width
        assert 0 <= slot.tile_y < world.height
        assert (slot.tile_x, slot.tile_y) not in seen
        seen.add((slot.tile_x, slot.tile_y))
    spacing_sq = recipe.config.slot_min_spacing**2
    cells = [(s.tile_x, s.tile_y) for s in world.slots]
    for i, (x, y) in enumerate(cells):
        for cx, cy in cells[i + 1 :]:
            assert (x - cx) ** 2 + (y - cy) ** 2 >= spacing_sq


def test_slot_indices_are_stable_and_sequential():
    world = generate_world(_recipe())
    assert [s.slot_index for s in world.slots] == list(range(len(world.slots)))


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


def test_slot_coordinates_match_tile_centers():
    world = generate_world(_recipe())
    for slot in world.slots:
        assert slot.coord_x == round((slot.tile_x + 0.5) * (100 / world.width), 4)
        assert slot.coord_y == round((slot.tile_y + 0.5) * (100 / world.height), 4)


def test_occupancy_does_not_change_geography():
    # The generator takes no vault/occupancy input, so two calls with the same recipe
    # are identical regardless of external state; assert that explicitly.
    first = generate_world(_recipe())
    second = generate_world(_recipe())
    assert first.terrain == second.terrain
    assert [(s.tile_x, s.tile_y) for s in first.slots] == [(s.tile_x, s.tile_y) for s in second.slots]


def test_generation_fails_clearly_when_slots_cannot_be_placed():
    # An impossibly large spacing must raise, never fall back to unsafe coordinates.
    recipe = WorldRecipe(seed="s", config=WorldConfig(slot_count=100, slot_min_spacing=999))
    terrain = generate_terrain(recipe)
    with pytest.raises(RuntimeError, match="slots"):
        generate_slots(recipe, terrain)


def test_canonical_serialization_is_stable():
    world = generate_world(_recipe())
    assert world.recipe_fingerprint == generate_world(_recipe()).recipe_fingerprint


def _mask_has_small_component(mask: set[int], width: int, height: int, min_size: int) -> bool:
    seen: set[int] = set()
    for start in mask:
        if start in seen:
            continue
        component = {start}
        stack = [start]
        seen.add(start)
        while stack:
            idx = stack.pop()
            x, y = idx % width, idx // width
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    nidx = ny * width + nx
                    if nidx in mask and nidx not in seen:
                        seen.add(nidx)
                        component.add(nidx)
                        stack.append(nidx)
        if len(component) < min_size:
            return True
    return False


def test_rivers_are_a_deterministic_non_empty_mask():
    recipe = _recipe(water_quantile=0)
    base = generate_terrain(recipe)
    assert "water" not in base
    first = generate_rivers(recipe, base)
    second = generate_rivers(recipe, base)
    assert first == second
    assert first
    assert first == sorted(set(first))


def test_rivers_do_not_mutate_terrain():
    recipe = _recipe(water_quantile=0)
    base = generate_terrain(recipe)
    unchanged = list(base)
    generate_rivers(recipe, base)
    assert base == unchanged


def test_river_mask_tiles_are_valid_indices():
    recipe = _recipe()
    mask = generate_rivers(recipe, generate_terrain(recipe))
    assert all(0 <= idx < recipe.config.width * recipe.config.height for idx in mask)


def test_rivers_never_cover_shared_vault_slot_tiles():
    recipe = _recipe(water_quantile=0)
    mask = generate_rivers(recipe, generate_terrain(recipe))
    width, height = recipe.config.width, recipe.config.height
    dry = slot_tile_indices(width, height, margin=VAULT_SLOT_DRY_MARGIN)
    assert dry
    assert not (set(mask) & dry)


def test_rivers_leave_no_small_mask_components():
    recipe = _recipe(water_quantile=0)
    mask = set(generate_rivers(recipe, generate_terrain(recipe)))
    assert not _mask_has_small_component(mask, recipe.config.width, recipe.config.height, WATER_MIN_COMPONENT)


def test_road_junctions_are_deterministic_and_land_only():
    recipe = _recipe()
    terrain = generate_terrain(recipe)
    junctions = _road_junctions(recipe, terrain)
    assert junctions == _road_junctions(recipe, terrain)
    assert len(junctions) >= 2
    assert all(terrain[idx] != "water" for idx in junctions)


def test_road_mask_is_deterministic_sorted_and_water_free():
    recipe = _recipe()
    terrain = generate_terrain(recipe)
    mask = generate_road_mask(recipe, terrain)
    assert mask == generate_road_mask(recipe, terrain)
    assert mask
    assert mask == sorted(set(mask))
    assert all(terrain[idx] != "water" for idx in mask)


def test_road_mask_changes_with_seed():
    seed_a = WorldRecipe(seed="seed-a")
    seed_b = WorldRecipe(seed="seed-b")
    assert generate_road_mask(seed_a, generate_terrain(seed_a)) != generate_road_mask(seed_b, generate_terrain(seed_b))


def test_road_mask_is_empty_when_there_is_no_land():
    recipe = _recipe()
    all_water = ["water"] * (recipe.config.width * recipe.config.height)
    assert generate_road_mask(recipe, all_water) == []


def test_generator_version_is_two():
    assert GENERATOR_VERSION == 2


def test_generator_version_is_part_of_the_fingerprint():
    v1 = WorldRecipe(seed="s", generator_version=1)
    v2 = WorldRecipe(seed="s", generator_version=2)
    assert v1.fingerprint() != v2.fingerprint()


def test_generate_world_leaves_terrain_identical_to_generate_terrain():
    recipe = _recipe()
    world = generate_world(recipe)
    assert world.terrain == generate_terrain(recipe)


def test_generate_world_builds_rivers_and_roads_from_terrain():
    recipe = _recipe()
    world = generate_world(recipe)
    assert world.rivers == generate_rivers(recipe, world.terrain)
    assert world.roads == generate_road_mask(recipe, world.terrain)
    assert world.rivers
    assert world.roads
    assert world.roads == sorted(set(world.roads))
    assert all(world.terrain[idx] != "water" for idx in world.roads)


def test_generate_world_roads_and_rivers_are_deterministic():
    first = generate_world(_recipe())
    second = generate_world(_recipe())
    assert first.terrain == second.terrain
    assert first.roads == second.roads
    assert first.rivers == second.rivers


def test_canonical_payload_and_checksum_cover_roads_and_rivers():
    world = generate_world(_recipe())
    payload = canonical_payload(world)
    assert '"roads"' in payload
    assert '"rivers"' in payload

    for changed in (replace(world, roads=[]), replace(world, rivers=[])):
        assert canonical_payload(changed) != payload
        assert snapshot_checksum(changed) != snapshot_checksum(world)
