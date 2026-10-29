"""Incident math helpers used by the per-attack journal."""

import pytest

from app.core.enums import IncidentType
from app.services.combat import incident_math
from app.services.combat.incident_math import split_proportional


def test_split_proportional_attributes_the_whole_total():
    assert split_proportional(20, [1, 1]) == [10, 10]


def test_split_proportional_gives_remainders_to_the_largest_fractions():
    assert split_proportional(10, [1, 2]) == [3, 7]
    assert split_proportional(1, [1, 1, 1]) == [1, 0, 0]


def test_split_proportional_handles_zero_total_and_weights():
    assert split_proportional(0, [1, 2]) == [0, 0]
    assert split_proportional(5, [0, 0]) == [0, 0]


def test_threat_health_multiplier_only_applies_to_mid_tier_threats():
    threat = 50.0
    for incident_type in (
        IncidentType.RAIDER_ATTACK,
        IncidentType.FERAL_GHOUL_ATTACK,
        IncidentType.MOLE_RAT_ATTACK,
    ):
        assert incident_math.threat_health(incident_type, threat) == pytest.approx(100.0)
    for incident_type in (IncidentType.FIRE, IncidentType.DEATHCLAW_ATTACK):
        assert incident_math.threat_health(incident_type, threat) == threat
