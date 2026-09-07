"""Tests for leveling service logic."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.services.leveling_service import LevelingService


@pytest.fixture
def leveling_service():
    """Get leveling service instance."""
    return LevelingService()


@pytest.mark.asyncio
async def test_level_up_at_max_level(
    async_session: AsyncSession,
    dweller: Dweller,
    leveling_service: LevelingService,
):
    """Test no level-up when already at max level."""
    # Set dweller to max level
    dweller.level = game_config.leveling.max_level
    dweller.experience = 999999

    leveled_up, levels_gained = await leveling_service.check_level_up(async_session, dweller)

    assert not leveled_up
    assert levels_gained == 0
    assert dweller.level == game_config.leveling.max_level


def test_xp_for_level_range_normal() -> None:
    """Test XP needed from level 1 to 5."""
    xp_needed = LevelingService.calculate_xp_for_level_range(1, 5)
    expected = LevelingService.calculate_xp_required(5) - LevelingService.calculate_xp_required(1)
    assert xp_needed == expected
    assert xp_needed > 0


def test_xp_for_level_range_target_equals_current() -> None:
    """Test XP needed when target equals current level is 0."""
    xp_needed = LevelingService.calculate_xp_for_level_range(5, 5)
    assert xp_needed == 0


@pytest.mark.asyncio
async def test_level_up_dweller_at_max_level_direct(
    async_session: AsyncSession,
    dweller: Dweller,
    leveling_service: LevelingService,
):
    """Test direct level_up_dweller call when already at max level."""
    dweller.level = game_config.leveling.max_level
    dweller.max_health = 100
    dweller.health = 50  # Not full, but shouldn't matter

    result = await leveling_service.level_up_dweller(async_session, dweller, levels=5)

    assert result.level == game_config.leveling.max_level
    assert result.max_health == 100  # Unchanged
    assert result.health == 50  # Unchanged — skipped early
