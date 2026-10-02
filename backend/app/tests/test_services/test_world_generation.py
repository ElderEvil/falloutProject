"""Focused regression tests for the backend world generation core.

NOTE: written but NOT executed (per the current instruction: no test runs).
They lock the contract guarantees: determinism, land-safe slots, and occupancy
independence.
"""

from app.services.world_generation_service import (
    TRAVEL_COST,
    PublicAnchor,
    WorldConfig,
    WorldRecipe,
    generate_slots,
    generate_terrain,
    generate_world,
)


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


def test_every_slot_is_land_safe_unique_and_spaced():
    recipe = _recipe()
    world = generate_world(recipe)
    assert len(world.slots) == recipe.config.slot_count
    seen: set[tuple[int, int]] = set()
    for slot in world.slots:
        assert world.terrain[slot.tile_y * world.width + slot.tile_x] != "water"
        assert 0 <= slot.tile_x < world.width and 0 <= slot.tile_y < world.height
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
    try:
        generate_slots(recipe, terrain)
    except RuntimeError as exc:
        assert "slots" in str(exc)
    else:  # pragma: no cover - guard
        raise AssertionError("expected RuntimeError when slots cannot be placed")


def test_canonical_serialization_is_stable():
    world = generate_world(_recipe())
    assert world.recipe_fingerprint == generate_world(_recipe()).recipe_fingerprint
