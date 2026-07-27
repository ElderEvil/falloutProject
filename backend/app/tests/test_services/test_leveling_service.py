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


def test_calculate_xp_required_level_1():
    """Test XP required for level 1 is 0."""
    assert LevelingService.calculate_xp_required(1) == 0


def test_calculate_xp_required_level_2():
    """Test XP required for level 2."""
    expected = int(game_config.leveling.base_xp_requirement * (2**game_config.leveling.xp_curve_exponent))
    assert LevelingService.calculate_xp_required(2) == expected


def test_calculate_xp_required_level_10():
    """Test XP required for level 10."""
    expected = int(game_config.leveling.base_xp_requirement * (10**game_config.leveling.xp_curve_exponent))
    assert LevelingService.calculate_xp_required(10) == expected


def test_calculate_xp_required_level_50():
    """Test XP required for max level."""
    expected = int(
        game_config.leveling.base_xp_requirement
        * (game_config.leveling.max_level**game_config.leveling.xp_curve_exponent)
    )
    assert LevelingService.calculate_xp_required(game_config.leveling.max_level) == expected


@pytest.mark.asyncio
async def test_check_level_up_no_level_up(
    async_session: AsyncSession,
    dweller: Dweller,
    leveling_service: LevelingService,
):
    """Test no level-up when insufficient XP."""
    # Dweller starts at level 1 with 0 XP
    dweller.level = 1
    dweller.experience = 50  # Not enough for level 2 (needs ~282 XP)

    leveled_up, levels_gained = await leveling_service.check_level_up(async_session, dweller)

    assert not leveled_up
    assert levels_gained == 0
    assert dweller.level == 1


@pytest.mark.asyncio
async def test_check_level_up_single_level(
    async_session: AsyncSession,
    dweller: Dweller,
    leveling_service: LevelingService,
):
    """Test single level-up."""
    # Give dweller enough XP for level 2
    dweller.level = 1
    dweller.experience = 300  # More than enough for level 2 (282 XP)
    initial_max_health = dweller.max_health

    leveled_up, levels_gained = await leveling_service.check_level_up(async_session, dweller)

    assert leveled_up
    assert levels_gained == 1
    assert dweller.level == 2
    assert dweller.max_health == initial_max_health + game_config.leveling.hp_gain_per_level
    assert dweller.health == dweller.max_health  # Should be fully healed


@pytest.mark.asyncio
async def test_check_level_up_multiple_levels(
    async_session: AsyncSession,
    dweller: Dweller,
    leveling_service: LevelingService,
):
    """Test multiple level-ups at once."""
    # Give dweller enough XP for level 5
    dweller.level = 1
    dweller.experience = 2000  # Enough for multiple levels
    initial_max_health = dweller.max_health

    leveled_up, levels_gained = await leveling_service.check_level_up(async_session, dweller)

    assert leveled_up
    assert levels_gained > 1
    assert dweller.level > 2
    assert dweller.max_health == initial_max_health + (game_config.leveling.hp_gain_per_level * levels_gained)
    assert dweller.health == dweller.max_health


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


@pytest.mark.asyncio
async def test_level_up_dweller_directly(
    async_session: AsyncSession,
    dweller: Dweller,
    leveling_service: LevelingService,
):
    """Test direct level-up method."""
    # Set dweller to level 5
    dweller.level = 5
    dweller.max_health = 100
    dweller.health = 80  # Partially damaged

    # Level up 3 times
    await leveling_service.level_up_dweller(async_session, dweller, levels=3)

    assert dweller.level == 8
    assert dweller.max_health == 100 + (game_config.leveling.hp_gain_per_level * 3)
    assert dweller.health == dweller.max_health  # Should be fully healed


@pytest.mark.asyncio
async def test_level_up_dweller_caps_at_max(
    async_session: AsyncSession,
    dweller: Dweller,
    leveling_service: LevelingService,
):
    """Test level-up caps at max level."""
    # Set dweller near max level
    dweller.level = game_config.leveling.max_level - 2
    dweller.max_health = 100

    # Try to level up 5 times (should only go to max level)
    await leveling_service.level_up_dweller(async_session, dweller, levels=5)

    assert dweller.level == game_config.leveling.max_level
    # Should only gain HP for the 2 levels gained
    assert dweller.max_health == 100 + (game_config.leveling.hp_gain_per_level * 2)


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


def test_xp_for_level_range_target_below_current() -> None:
    """Test XP needed when target is below current level is 0 (no regression)."""
    xp_needed = LevelingService.calculate_xp_for_level_range(10, 5)
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


def test_xp_curve_is_exponential():
    """Test that XP curve increases exponentially."""
    xp_level_5 = LevelingService.calculate_xp_required(5)
    xp_level_10 = LevelingService.calculate_xp_required(10)
    xp_level_20 = LevelingService.calculate_xp_required(20)

    # XP should increase non-linearly
    diff_5_to_10 = xp_level_10 - xp_level_5
    diff_10_to_20 = xp_level_20 - xp_level_10

    assert diff_10_to_20 > diff_5_to_10 * 2  # More than double the increase
