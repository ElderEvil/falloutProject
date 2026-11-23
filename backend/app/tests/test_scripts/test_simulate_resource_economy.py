import pytest

from app.cli.simulate_resources import ResourceEconomyConfig, simulate


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("population", -1, "non-negative"),
        ("workers_per_room", -1, "non-negative"),
        ("room_tier", 0, "at least 1"),
        ("room_size", 0, "at least 1"),
    ],
)
def test_simulate_rejects_invalid_config(field: str, value: int, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        simulate(ResourceEconomyConfig(**{field: value}))


def test_higher_room_tier_produces_and_consumes_more() -> None:
    tier_one = simulate(ResourceEconomyConfig(room_tier=1, base_production_rate=0.1))
    tier_two = simulate(ResourceEconomyConfig(room_tier=2, base_production_rate=0.1))
    assert tier_two.initial_rates_per_minute["power"] > tier_one.initial_rates_per_minute["power"]
    assert tier_two.initial_rates_per_minute["food"] > tier_one.initial_rates_per_minute["food"]


def test_default_room_size_matches_catalog_minimum() -> None:
    explicit = simulate(ResourceEconomyConfig(room_size=3, base_production_rate=0.1))
    implicit = simulate(ResourceEconomyConfig(base_production_rate=0.1))
    assert explicit.initial_rates_per_minute == implicit.initial_rates_per_minute
