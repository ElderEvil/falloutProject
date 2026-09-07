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


def test_render_template_bio_no_visited() -> None:
    assert _render_template_bio("Megaton", []) == "Born in Megaton. Before the vault, I wandered the wastes alone."


def test_render_template_bio_single_visited() -> None:
    assert (
        _render_template_bio("Megaton", ["Rivet City"])
        == "Born in Megaton. Before the vault, I wandered through Rivet City."
    )


def test_create_random_common_dweller_state_of_being_for_non_humans() -> None:
    """Non-humans carry a state_of_being from STATE_OF_BEING_OPTIONS; humans carry none."""
    for seed in range(300):
        attrs = create_random_common_dweller(seed=seed)["visual_attributes"]
        race = RaceOption(attrs["race"])
        if race == RaceOption.HUMAN:
            assert "state_of_being" not in attrs
        else:
            assert attrs["state_of_being"] in STATE_OF_BEING_VALUES[race]


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
