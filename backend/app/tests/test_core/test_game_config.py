"""Game balance configuration validation."""

import pytest
from pydantic import ValidationError

from app.core.game_config import BioConfig, CombatConfig, CraftingConfig, HappinessConfig


@pytest.mark.parametrize("multiplier", [0, -1, float("inf"), float("nan")])
def test_incident_threat_health_multipliers_reject_non_positive_or_non_finite(multiplier: float):
    with pytest.raises(ValidationError):
        CombatConfig(incident_threat_health_multipliers={"raider_attack": multiplier})


def test_incident_threat_health_multipliers_accept_positive_finite_values():
    config = CombatConfig(incident_threat_health_multipliers={"raider_attack": 1.5})
    assert config.incident_threat_health_multipliers == {"raider_attack": 1.5}


def test_visited_place_caps_accept_zero_and_reject_negative_counts():
    assert BioConfig(visited_by_rarity={"common": 0, "rare": 2}).max_visited("common") == 0
    with pytest.raises(ValidationError) as exc:
        BioConfig(visited_by_rarity={"common": -1})
    assert exc.value.errors()[0]["loc"] == ("visited_by_rarity", "common")


@pytest.mark.parametrize("mapping", [{-6: 0}, {6: 0}, {0: -11}, {0: 11}])
def test_sentiment_mapping_rejects_out_of_range_keys_and_values(mapping):
    with pytest.raises(ValidationError):
        HappinessConfig(sentiment_delta_mapping=mapping)


def test_sentiment_mapping_preserves_json_key_coercion_and_boundary_values(monkeypatch):
    monkeypatch.setenv("HAPPINESS_SENTIMENT_DELTA_MAPPING", '{"-5": -10, "5": 10}')
    config = HappinessConfig()
    assert config.get_happiness_delta(-5) == -10
    assert config.get_happiness_delta(5) == 10
    assert config.get_happiness_delta(0) == 0


@pytest.mark.parametrize(
    "field",
    ["caps_cost_by_rarity", "order_seconds_by_rarity", "unlock_scrap_count_by_rarity", "junk_recipe_by_rarity"],
)
@pytest.mark.parametrize("invalid_count", [-1, True, 1.5, "2"])
def test_crafting_counts_remain_strict_non_negative_integers(field, invalid_count):
    counts = {"common": invalid_count, "rare": 0, "legendary": 0}
    value = (
        {rarity: {"common": count} for rarity, count in counts.items()} if field == "junk_recipe_by_rarity" else counts
    )
    with pytest.raises(ValidationError) as exc:
        CraftingConfig(**{field: value})
    expected_loc = (field, "common", "common") if field == "junk_recipe_by_rarity" else (field, "common")
    assert exc.value.errors()[0]["loc"] == expected_loc


def test_crafting_cost_maps_preserve_case_normalization_and_zero_values():
    config = CraftingConfig(
        caps_cost_by_rarity={"COMMON": 0, "Rare": 10, "legendary": 20},
        order_seconds_by_rarity={"COMMON": 0, "Rare": 60, "legendary": 120},
        unlock_scrap_count_by_rarity={"RARE": 0},
    )
    assert config.caps_cost("common") == 0
    assert config.caps_cost("rare") == 10
    assert config.order_seconds_by_rarity["rare"] == 60
    assert config.scrap_unlock_count("rare") == 0


@pytest.mark.parametrize("field", ["caps_cost_by_rarity", "order_seconds_by_rarity"])
def test_crafting_cost_maps_still_require_all_rarities(field):
    with pytest.raises(ValidationError, match="missing rarities"):
        CraftingConfig(**{field: {"common": 0, "rare": 10}})
