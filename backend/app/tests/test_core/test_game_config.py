"""Game balance configuration validation."""

import pytest
from pydantic import ValidationError

from app.core.game_config import CombatConfig


@pytest.mark.parametrize("multiplier", [0, -1, float("inf"), float("nan")])
def test_incident_threat_health_multipliers_reject_non_positive_or_non_finite(multiplier: float):
    with pytest.raises(ValidationError):
        CombatConfig(incident_threat_health_multipliers={"raider_attack": multiplier})


def test_incident_threat_health_multipliers_accept_positive_finite_values():
    config = CombatConfig(incident_threat_health_multipliers={"raider_attack": 1.5})
    assert config.incident_threat_health_multipliers == {"raider_attack": 1.5}
