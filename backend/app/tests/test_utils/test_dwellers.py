"""Tests for dweller bio generation utilities."""

import random
from datetime import UTC, datetime

import pytest

from app.core.game_config import DwellerConfig, game_config
from app.options.factions import faction_restrictions
from app.options.races import STATE_OF_BEING_VALUES, RaceOption
from app.schemas.common import AgeGroupEnum, RarityEnum
from app.utils.dwellers import (
    _PLACE_POOL,
    _calendar_years_ago,
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
    assert data["is_adult"] is True
    assert data["age_group"] == AgeGroupEnum.ADULT
    assert data["birth_date"] <= _calendar_years_ago(datetime(2000, 1, 1), 18)


def test_create_random_common_dweller_identity_deterministic() -> None:
    """Same seed reproduces the same race/faction/state_of_being triple."""
    for seed in range(20):
        a = create_random_common_dweller(seed=seed)["visual_attributes"]
        b = create_random_common_dweller(seed=seed)["visual_attributes"]
        assert a == b


def test_create_random_common_dweller_race_distribution() -> None:
    """1000 seeded draws approximate the configured race weights."""
    weights = game_config.dweller.get_race_weights()
    total = sum(weights.values())
    draws = 1000
    counts: dict[str, int] = {}
    for seed in range(draws):
        race = create_random_common_dweller(seed=seed)["visual_attributes"]["race"]
        counts[race] = counts.get(race, 0) + 1
    assert set(counts) == {race.value for race in RaceOption}
    for race, weight in weights.items():
        assert counts[race] == pytest.approx(draws * weight / total, rel=0.4)


def test_create_random_common_dweller_human_faction_vault_dominant() -> None:
    """Humans stay lore-coherent: vault_dweller outweighs all other factions combined."""
    vault_dweller = 0
    other = 0
    for seed in range(1000):
        attrs = create_random_common_dweller(seed=seed)["visual_attributes"]
        if attrs["race"] == RaceOption.HUMAN:
            if attrs["faction"] == "vault_dweller":
                vault_dweller += 1
            else:
                other += 1
    assert vault_dweller > other * 2


def test_create_random_common_dweller_state_of_being_for_non_humans() -> None:
    """Non-humans carry a state_of_being from STATE_OF_BEING_OPTIONS; humans carry none."""
    for seed in range(300):
        attrs = create_random_common_dweller(seed=seed)["visual_attributes"]
        race = RaceOption(attrs["race"])
        if race == RaceOption.HUMAN:
            assert "state_of_being" not in attrs
        else:
            assert attrs["state_of_being"] in STATE_OF_BEING_VALUES[race]


def test_create_random_common_dweller_identity_pairs_pass_schema_validator() -> None:
    """Every generated race/faction pair survives DwellerVisualAttributes validation."""
    from app.schemas.dweller import DwellerVisualAttributes

    for seed in range(100):
        attrs = create_random_common_dweller(seed=seed)["visual_attributes"]
        DwellerVisualAttributes(race=attrs["race"], faction=attrs["faction"])


def test_create_random_common_dweller_identity_serializes_through_read_schema() -> None:
    """Generated state-of-being values must satisfy the API response schema."""
    from app.schemas.dweller import DwellerVisualAttributes

    for seed in range(300):
        DwellerVisualAttributes.model_validate(create_random_common_dweller(seed=seed)["visual_attributes"])


def test_dweller_config_race_weights_defaults() -> None:
    """Default race weights implement the 70/15/10/5 diversity policy; accessor returns a copy."""
    weights = game_config.dweller.get_race_weights()
    assert weights == {"human": 70, "ghoul": 15, "synth": 10, "super_mutant": 5}
    weights["human"] = 1
    assert game_config.dweller.race_weights["human"] == 70


def test_dweller_config_race_weights_normalizes_enum_strings() -> None:
    cfg = DwellerConfig(race_weights={"Human": 70, "ghoul": 15, "Synth": 10, "Super Mutant": 5})
    assert cfg.race_weights == {"human": 70, "ghoul": 15, "synth": 10, "super_mutant": 5}
    cfg = DwellerConfig(race_weights={"human": 70, "GHOUL": 15, "synth": 10, "super-mutant": 5})
    assert cfg.race_weights["super_mutant"] == 5
    assert cfg.race_weights["ghoul"] == 15


def test_dweller_config_race_weights_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown race"):
        DwellerConfig(race_weights={"human": 70, "ghoul": 15, "synth": 10, "super_mutant": 5, "robot": 10})


def test_dweller_config_race_weights_rejects_missing_race() -> None:
    with pytest.raises(ValueError, match="missing"):
        DwellerConfig(race_weights={"human": 70, "ghoul": 30})


def test_dweller_config_race_weights_rejects_negative_and_non_int() -> None:
    with pytest.raises(ValueError, match="integer"):
        DwellerConfig(race_weights={"human": 70, "ghoul": 15, "synth": 10, "super_mutant": -5})
    with pytest.raises(ValueError, match="integer"):
        DwellerConfig(race_weights={"human": 70.5, "ghoul": 15, "synth": 10, "super_mutant": 5})


def test_dweller_config_race_weights_rejects_zero_total() -> None:
    with pytest.raises(ValueError, match="positive total"):
        DwellerConfig(race_weights={"human": 0, "ghoul": 0, "synth": 0, "super_mutant": 0})


def test_dweller_config_human_faction_weights_policy() -> None:
    """human_faction_weights: vault_dweller dominant, keys within human faction_restrictions."""
    weights = game_config.dweller.human_faction_weights
    assert weights["vault_dweller"] == max(weights.values())
    assert set(weights) <= {faction.value for faction in faction_restrictions[RaceOption.HUMAN]}


def test_vault_start_config_rare_chances() -> None:
    """Standard seeding stays at 4% RARE; boosted vaults get the 12% P0 boost."""
    assert game_config.vault_start.standard_rare_chance == 0.04
    assert game_config.vault_start.boosted_rare_chance == 0.12
