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
    async def test_removes_share_of_max_health(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, max_health=100, radiation=80, radaway=2)
        result = await medical_service.use_radaway(async_session, dweller.id)
        assert result.radiation == 80 - int(100 * game_config.health.radaway_removal_percent)
        assert result.radaway == 1

    @pytest.mark.asyncio
    async def test_clears_remainder_below_half_bar(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, max_health=100, radiation=10, radaway=2)
        result = await medical_service.use_radaway(async_session, dweller.id)
        assert result.radiation == 0
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
    async def test_healing_clamps_at_radiation_ceiling(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        await _set_dweller_state(async_session, dweller, max_health=100, health=30, radiation=40, stimpack=1)
        result = await medical_service.use_stimpack(async_session, dweller.id)
        heal_amount = max(1, int(100 * game_config.health.stimpack_heal_percent))
        assert result.health == min(30 + heal_amount, 60)
        assert result.stimpack == 0

    @pytest.mark.asyncio
    async def test_at_full_health_is_no_change(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, max_health=100, health=100, radiation=0, stimpack=1)
        with pytest.raises(ContentNoChangeException):
            await medical_service.use_stimpack(async_session, dweller.id)


class TestDistributeRecoverySupplies:
    @pytest.mark.asyncio
    async def test_treats_dweller_with_radaway_then_stimpack(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        from app.models.storage import Storage

        await _set_dweller_state(async_session, dweller, max_health=100, radiation=100, health=1)
        async_session.add(Storage(vault_id=vault.id, radaway=10, stimpack=10))
        await async_session.commit()

        result = await medical_service.distribute_recovery_supplies(async_session, vault.id)

        assert result.dwellers_treated == 1
        assert result.radaways_used == 1
        assert result.stimpaks_used == 1
        assert result.vault_radaways == 9
        assert result.vault_stimpacks == 9
        await async_session.refresh(dweller)
        assert dweller.radiation == 50
        heal = max(1, int(100 * game_config.health.stimpack_heal_percent))
        assert dweller.health == min(1 + heal, dweller.effective_max_health)
        assert dweller.health >= 40

    @pytest.mark.asyncio
    async def test_skips_clean_dead_and_away_dwellers(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        from app.models.storage import Storage
        from app.schemas.common import DwellerStatusEnum

        await _set_dweller_state(async_session, dweller, radiation=40, status=DwellerStatusEnum.EXPLORING)
        async_session.add(Storage(vault_id=vault.id, radaway=10, stimpack=10))
        await async_session.commit()

        result = await medical_service.distribute_recovery_supplies(async_session, vault.id)

        assert result.dwellers_treated == 0
        assert result.vault_radaways == 10
        assert result.vault_stimpacks == 10

    @pytest.mark.asyncio
    async def test_empty_stock_is_noop(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        from app.models.storage import Storage

        await _set_dweller_state(async_session, dweller, radiation=50)
        async_session.add(Storage(vault_id=vault.id, radaway=0, stimpack=0))
        await async_session.commit()

        result = await medical_service.distribute_recovery_supplies(async_session, vault.id)

        assert result.dwellers_treated == 0
        assert result.radaways_used == 0
        assert result.stimpaks_used == 0
        await async_session.refresh(dweller)
        assert dweller.radiation == 50
