"""Tests for dweller medical supply usage (stimpack/radaway)."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services import medical_service
from app.utils.exceptions import ContentNoChangeException, ResourceConflictException


async def _set_dweller_state(async_session: AsyncSession, dweller: Dweller, **state: int) -> None:
    for key, value in state.items():
        setattr(dweller, key, value)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)


class TestUseRadaway:
    @pytest.mark.asyncio
    async def test_removes_configured_share_of_radiation(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        await _set_dweller_state(async_session, dweller, radiation=10, radaway=2)
        result = await medical_service.use_radaway(async_session, dweller.id)
        assert result.radiation == 10 - int(10 * game_config.health.radaway_removal_percent)
        assert result.radaway == 1

    @pytest.mark.asyncio
    async def test_requires_supplies(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, radiation=10, radaway=0)
        with pytest.raises(ResourceConflictException):
            await medical_service.use_radaway(async_session, dweller.id)

    @pytest.mark.asyncio
    async def test_without_radiation_is_no_change(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, radiation=0, radaway=2)
        with pytest.raises(ContentNoChangeException):
            await medical_service.use_radaway(async_session, dweller.id)


class TestUseStimpack:
    @pytest.mark.asyncio
    async def test_heals_configured_share_of_max_health(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        await _set_dweller_state(async_session, dweller, max_health=100, health=10, radiation=0, stimpack=1)
        result = await medical_service.use_stimpack(async_session, dweller.id)
        assert result.health == 10 + int(100 * game_config.health.stimpack_heal_percent)
        assert result.stimpack == 0

    @pytest.mark.asyncio
    async def test_requires_supplies(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, health=10, stimpack=0)
        with pytest.raises(ResourceConflictException):
            await medical_service.use_stimpack(async_session, dweller.id)

    @pytest.mark.asyncio
    async def test_at_full_health_is_no_change(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, max_health=100, health=100, radiation=0, stimpack=1)
        with pytest.raises(ContentNoChangeException):
            await medical_service.use_stimpack(async_session, dweller.id)
