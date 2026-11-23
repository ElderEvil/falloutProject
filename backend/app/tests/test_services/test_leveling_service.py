import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.services.dweller_service import dweller_service
from app.services.leveling_service import LevelingService
from app.utils.dwellers import level_progress
from app.utils.reward_delivery import defer_reward_delivery


@pytest.fixture
def leveling_service() -> LevelingService:
    return LevelingService()


async def test_level_up_at_max_level(async_session: AsyncSession, dweller: Dweller, leveling_service: LevelingService):
    dweller.level = game_config.leveling.max_level
    dweller.experience = 999999
    leveled_up, levels_gained = await leveling_service.check_level_up(async_session, dweller)
    assert (leveled_up, levels_gained, dweller.level) == (False, 0, game_config.leveling.max_level)


def test_xp_for_level_range() -> None:
    xp_needed = LevelingService.calculate_xp_for_level_range(1, 5)
    assert xp_needed == LevelingService.calculate_xp_required(5) - LevelingService.calculate_xp_required(1)
    assert xp_needed > 0
    assert LevelingService.calculate_xp_for_level_range(5, 5) == 0


async def test_level_up_dweller_at_max_level_direct(
    async_session: AsyncSession, dweller: Dweller, leveling_service: LevelingService
):
    dweller.level = game_config.leveling.max_level
    dweller.max_health, dweller.health = 100, 50  # Not full, but shouldn't matter
    result = await leveling_service.level_up_dweller(async_session, dweller, levels=5)
    # Unchanged — skipped early.
    assert (result.level, result.max_health, result.health) == (game_config.leveling.max_level, 100, 50)


@pytest.mark.parametrize(("amount", "expected_level"), [(1, 2), (236, 2), (237, 3), (1000, 5)])
async def test_reward_xp_uses_cumulative_thresholds(async_session, dweller, amount, expected_level):
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
    assert (updated.level, updated.experience, updated.health) == (game_config.leveling.max_level, expected_xp + 1, 40)


async def test_reward_xp_level_and_health_roll_back_together(async_session, dweller):
    dweller.level, dweller.experience, dweller.health = 1, 0, 40
    old_max_health = dweller.max_health
    await async_session.commit()
    async with defer_reward_delivery(async_session):
        await dweller_service.add_experience(async_session, dweller, 1000)
        assert dweller.level == 4
        assert dweller.experience == 1000
        assert dweller.max_health == old_max_health + 3 * game_config.leveling.hp_gain_per_level
    await async_session.rollback()
    await async_session.refresh(dweller)
    assert (dweller.level, dweller.experience, dweller.max_health, dweller.health) == (1, 0, old_max_health, 40)


@pytest.mark.parametrize("level", [1, 2, 3, 10, 50])
def test_seeded_xp_matches_leveling_and_model_properties(dweller_data, monkeypatch, level):
    monkeypatch.setattr(game_config.leveling, "base_xp_requirement", 150)
    monkeypatch.setattr(game_config.leveling, "xp_curve_exponent", 2.0)
    max_health, experience = level_progress(level)
    resident = Dweller(**{**dweller_data, "level": level, "experience": experience, "max_health": max_health})
    assert experience == (0 if level == 1 else 150 * level**2)
    assert resident.current_level_xp == experience == LevelingService.calculate_xp_required(level)
    assert resident.xp_progress_percentage == (100.0 if level == 50 else 0.0)
