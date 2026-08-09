"""Tests for dweller bio generation utilities."""

import random
from datetime import UTC, datetime

from app.core.game_config import game_config
from app.schemas.common import AgeGroupEnum, RarityEnum
from app.utils.dwellers import (
    _PLACE_POOL,
    _procedural_bio_places,
    _render_template_bio,
    create_random_common_dweller,
)


def test_place_pool_has_no_unregistrable_names() -> None:
    """Every pool name must survive map registration (none in the origin skip list)."""
    from app.utils.places import GENERIC_ORIGIN_SKIP

    normalized = {name.strip().lower() for name in GENERIC_ORIGIN_SKIP}
    for place in _PLACE_POOL:
        assert place.strip().lower() not in normalized


def test_procedural_bio_places_origin_in_pool() -> None:
    origin, visited = _procedural_bio_places(random.Random(1), RarityEnum.COMMON)
    assert origin in _PLACE_POOL
    assert set(visited) <= set(_PLACE_POOL)


def test_procedural_bio_places_visited_excludes_origin() -> None:
    for seed in range(10):
        origin, visited = _procedural_bio_places(random.Random(seed), RarityEnum.LEGENDARY)
        assert origin not in visited


def test_procedural_bio_places_count_scales_with_rarity() -> None:
    _, common_visited = _procedural_bio_places(random.Random(1), RarityEnum.COMMON)
    _, rare_visited = _procedural_bio_places(random.Random(1), RarityEnum.RARE)
    _, legendary_visited = _procedural_bio_places(random.Random(1), RarityEnum.LEGENDARY)
    assert len(common_visited) == game_config.bio.max_visited("common")
    assert len(rare_visited) == game_config.bio.max_visited("rare")
    assert len(legendary_visited) == game_config.bio.max_visited("legendary")
    assert len(common_visited) < len(rare_visited) < len(legendary_visited)


def test_procedural_bio_places_deterministic() -> None:
    a = _procedural_bio_places(random.Random(42), RarityEnum.RARE)
    b = _procedural_bio_places(random.Random(42), RarityEnum.RARE)
    assert a == b


def test_render_template_bio_no_visited() -> None:
    assert _render_template_bio("Megaton", []) == "Born in Megaton. Before the vault, I wandered the wastes alone."


def test_render_template_bio_single_visited() -> None:
    assert (
        _render_template_bio("Megaton", ["Rivet City"])
        == "Born in Megaton. Before the vault, I wandered through Rivet City."
    )


def test_render_template_bio_multiple_visited() -> None:
    assert (
        _render_template_bio("Megaton", ["Rivet City", "Tenpenny Tower"])
        == "Born in Megaton. Before the vault, I wandered through Rivet City, and Tenpenny Tower."
    )


def test_create_random_common_dweller_bio_matches_places() -> None:
    for seed in range(10):
        data = create_random_common_dweller(seed=seed)
        origin, visited = data["_bio_places"]
        assert origin in data["bio"]
        for place in visited:
            assert place in data["bio"]


def test_create_random_common_dweller_rarity_scales_bio() -> None:
    common = create_random_common_dweller(seed=1, rarity=RarityEnum.COMMON)
    legendary = create_random_common_dweller(seed=1, rarity=RarityEnum.LEGENDARY)
    assert len(common["_bio_places"][1]) == game_config.bio.max_visited("common")
    assert len(legendary["_bio_places"][1]) == game_config.bio.max_visited("legendary")


def test_create_random_common_dweller_age_fields_coherent() -> None:
    """Seeded dweller keeps deterministic age fields (regression for the Andrea Freeman bug)."""
    data = create_random_common_dweller(seed=7)
    if data["is_adult"]:
        assert data["age_group"] == AgeGroupEnum.ADULT
        assert data["birth_date"] < datetime(2000, 1, 1)
    else:
        assert data["age_group"] == AgeGroupEnum.CHILD
        assert data["birth_date"] == datetime(2000, 1, 1)
