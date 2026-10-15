"""Incident spawn-rate tier validation (game balance config)."""

import pytest
from pydantic import ValidationError

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
