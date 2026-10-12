"""Tests for the deterministic resource-economy simulator."""

import pytest

from app.cli.simulate_resources import ResourceEconomyConfig, simulate


@pytest.mark.parametrize("field", ["population", "workers_per_room"])
def test_simulate_rejects_negative_population_and_worker_counts(field: str) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        simulate(ResourceEconomyConfig(**{field: -1}))


@pytest.mark.parametrize("field", ["room_tier", "room_size"])
def test_simulate_rejects_invalid_room_geometry(field: str) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        simulate(ResourceEconomyConfig(**{field: 0}))


def test_higher_room_tier_produces_and_consumes_more() -> None:
    tier_one = simulate(ResourceEconomyConfig(room_tier=1, base_production_rate=0.1))
    tier_two = simulate(ResourceEconomyConfig(room_tier=2, base_production_rate=0.1))
    assert tier_two.initial_rates_per_minute["power"] > tier_one.initial_rates_per_minute["power"]
    assert tier_two.initial_rates_per_minute["food"] > tier_one.initial_rates_per_minute["food"]


def test_default_room_size_matches_catalog_minimum() -> None:
    explicit = simulate(ResourceEconomyConfig(room_size=3, base_production_rate=0.1))
    implicit = simulate(ResourceEconomyConfig(base_production_rate=0.1))
    assert explicit.initial_rates_per_minute == implicit.initial_rates_per_minute
