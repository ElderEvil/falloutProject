"""Tests for leveling service logic."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.services.dweller_service import dweller_service
from app.services.leveling_service import LevelingService
from app.utils.dwellers import level_progress
from app.utils.reward_delivery import defer_reward_delivery


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


@pytest.mark.parametrize(("amount", "expected_level"), [(1, 2), (236, 2), (237, 3), (1000, 5)])
async def test_reward_xp_uses_cumulative_thresholds(async_session, dweller, amount, expected_level):
    """A seeded level-2 dweller needs 519 total XP for level 3, and keeps all earned XP."""
    dweller.level = 2
    dweller.experience = 282
    dweller.max_health = 105
    dweller.health = 40
    dweller.radiation = 10
    await async_session.commit()

    updated = await dweller_service.add_experience(async_session, dweller, amount)
    await async_session.refresh(updated)

    assert updated.experience == 282 + amount
    assert updated.level == expected_level
    assert updated.max_health == 105 + (expected_level - 2) * game_config.leveling.hp_gain_per_level
    assert updated.health == (updated.max_health - 10 if expected_level > 2 else 40)
    assert await LevelingService().check_level_up(async_session, updated) == (False, 0)


async def test_reward_xp_caps_level_and_preserves_total(async_session, dweller):
    dweller.level = game_config.leveling.max_level - 1
    dweller.experience = LevelingService.calculate_xp_required(dweller.level)
    dweller.health = 40
    old_max_health = dweller.max_health
    await async_session.commit()
    amount = LevelingService.calculate_xp_required(game_config.leveling.max_level) * 2
    expected_xp = dweller.experience + amount

    updated = await dweller_service.add_experience(async_session, dweller, amount)
    assert updated.level == game_config.leveling.max_level
    assert updated.experience == expected_xp
    assert updated.max_health == old_max_health + game_config.leveling.hp_gain_per_level

    updated.health = 40
    await async_session.commit()
    await dweller_service.add_experience(async_session, updated, 1)
    await async_session.refresh(updated)
    assert updated.level == game_config.leveling.max_level
    assert updated.experience == expected_xp + 1
    assert updated.health == 40


async def test_reward_xp_level_and_health_roll_back_together(async_session, dweller):
    dweller.level = 1
    dweller.experience = 0
    dweller.health = 40
    old_max_health = dweller.max_health
    await async_session.commit()

    async with defer_reward_delivery(async_session):
        await dweller_service.add_experience(async_session, dweller, 1000)
        assert dweller.level == 4
        assert dweller.experience == 1000
        assert dweller.max_health == old_max_health + 3 * game_config.leveling.hp_gain_per_level
    await async_session.rollback()
    await async_session.refresh(dweller)

    assert dweller.level == 1
    assert dweller.experience == 0
    assert dweller.max_health == old_max_health
    assert dweller.health == 40


@pytest.mark.parametrize("level", [1, 2, 3, 10, 50])
def test_seeded_xp_matches_leveling_and_model_properties(dweller_data, monkeypatch, level):
    monkeypatch.setattr(game_config.leveling, "base_xp_requirement", 150)
    monkeypatch.setattr(game_config.leveling, "xp_curve_exponent", 2.0)
    max_health, experience = level_progress(level)
    resident = Dweller(**{**dweller_data, "level": level, "experience": experience, "max_health": max_health})

    assert experience == (0 if level == 1 else 150 * level**2)
    assert resident.current_level_xp == experience == LevelingService.calculate_xp_required(level)
    assert resident.xp_progress_percentage == (100.0 if level == 50 else 0.0)
