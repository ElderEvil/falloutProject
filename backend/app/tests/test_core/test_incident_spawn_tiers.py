"""Incident spawn-rate tier validation (game balance config)."""

import pytest
from pydantic import ValidationError

from app.core.enums import IncidentType, VaultModeEnum
from app.core.game_config import IncidentConfig


def test_default_tiers_cover_a_starter_vault() -> None:
    """Shipped tiers: starter vaults spawn hourly, developed ones every quarter."""
    rate = IncidentConfig().get_spawn_rate

    assert rate(0) == 1.0
    assert rate(15) == 1.0
    assert rate(16) == 2.0
    assert rate(31) == 4.0


def test_empty_tiers_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        IncidentConfig(room_rate_tiers=[])


def test_malformed_tier_is_rejected() -> None:
    with pytest.raises(ValidationError, match=r"must be \[cap, rate\]"):
        IncidentConfig(room_rate_tiers=[[15, 1.0, 2.0]])


def test_descending_caps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="caps must ascend"):
        IncidentConfig(room_rate_tiers=[[30, 1.0], [15, 2.0]])


def test_negative_rate_is_rejected() -> None:
    with pytest.raises(ValidationError, match="rates must be non-negative"):
        IncidentConfig(room_rate_tiers=[[15, -1.0]])


def test_deathclaw_gate_standard_uses_60_boundary() -> None:
    weights = IncidentConfig().get_spawn_weights

    assert IncidentType.DEATHCLAW_ATTACK not in weights(59, VaultModeEnum.STANDARD.value)
    assert IncidentType.DEATHCLAW_ATTACK in weights(60, VaultModeEnum.STANDARD.value)


def test_deathclaw_gate_survival_uses_35_boundary() -> None:
    weights = IncidentConfig().get_spawn_weights

    assert IncidentType.DEATHCLAW_ATTACK not in weights(34, VaultModeEnum.SURVIVAL.value)
    assert IncidentType.DEATHCLAW_ATTACK in weights(35, VaultModeEnum.SURVIVAL.value)


def test_survival_gate_is_reached_before_standard() -> None:
    weights = IncidentConfig().get_spawn_weights

    assert IncidentType.DEATHCLAW_ATTACK not in weights(35, VaultModeEnum.STANDARD.value)
    assert IncidentType.DEATHCLAW_ATTACK in weights(35, VaultModeEnum.SURVIVAL.value)


def test_only_deathclaw_is_population_gated() -> None:
    weights = IncidentConfig().get_spawn_weights(0, VaultModeEnum.STANDARD.value)

    assert IncidentType.FIRE in weights
    assert IncidentType.RADROACH_INFESTATION in weights
    assert IncidentType.DEATHCLAW_ATTACK not in weights


def test_full_balance_table_when_population_omitted() -> None:
    weights = IncidentConfig().get_spawn_weights()

    assert IncidentType.DEATHCLAW_ATTACK in weights
