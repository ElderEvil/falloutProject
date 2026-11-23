import pytest
from pydantic import ValidationError

from app.core.enums import IncidentType, VaultModeEnum
from app.core.game_config import IncidentConfig


def test_default_tiers_cover_a_starter_vault() -> None:
    rate = IncidentConfig().get_spawn_rate

    assert rate(0) == 1.0
    assert rate(15) == 1.0
    assert rate(16) == 2.0
    assert rate(31) == 4.0


def test_empty_tiers_are_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        IncidentConfig(room_rate_tiers=[])
    assert exc.value.errors()[0]["loc"] == ("room_rate_tiers",)
    assert exc.value.errors()[0]["type"] == "too_short"


@pytest.mark.parametrize("tier", [[15], [15, 1.0, 2.0]])
def test_malformed_tier_is_rejected(tier) -> None:
    with pytest.raises(ValidationError) as exc:
        IncidentConfig(room_rate_tiers=[tier])
    assert exc.value.errors()[0]["loc"] == ("room_rate_tiers", 0)


@pytest.mark.parametrize(
    ("tiers", "message"),
    [
        ([[30, 1.0], [15, 2.0]], "caps must ascend"),
        ([[15, -1.0]], "rates must be non-negative"),
    ],
)
def test_invalid_tiers_are_rejected(tiers, message) -> None:
    with pytest.raises(ValidationError, match=message):
        IncidentConfig(room_rate_tiers=tiers)


@pytest.mark.parametrize(
    ("population", "mode", "present"),
    [
        (59, VaultModeEnum.STANDARD.value, False),
        (60, VaultModeEnum.STANDARD.value, True),
        (34, VaultModeEnum.SURVIVAL.value, False),
        (35, VaultModeEnum.SURVIVAL.value, True),
        (35, VaultModeEnum.STANDARD.value, False),
    ],
)
def test_deathclaw_gate_uses_population_and_mode_boundaries(population: int, mode: str, present: bool) -> None:
    weights = IncidentConfig().get_spawn_weights
    assert (IncidentType.DEATHCLAW_ATTACK in weights(population, mode)) is present


def test_only_deathclaw_is_population_gated() -> None:
    weights = IncidentConfig().get_spawn_weights(0, VaultModeEnum.STANDARD.value)

    assert IncidentType.FIRE in weights
    assert IncidentType.RADROACH_INFESTATION in weights
    assert IncidentType.DEATHCLAW_ATTACK not in weights


def test_full_balance_table_when_population_omitted() -> None:
    weights = IncidentConfig().get_spawn_weights()

    assert IncidentType.DEATHCLAW_ATTACK in weights
