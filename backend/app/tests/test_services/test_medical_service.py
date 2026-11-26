import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerStatusEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.storage import Storage
from app.models.vault import Vault
from app.services import medical_service as med
from app.utils.exceptions import ContentNoChangeException, ResourceConflictException

HEAL = int(100 * game_config.health.stimpack_heal_percent)
RADAWAY_REMOVAL = int(100 * game_config.health.radaway_removal_percent)


async def _set_dweller_state(async_session: AsyncSession, dweller: Dweller, **state: int) -> None:
    for key, value in state.items():
        setattr(dweller, key, value)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)


async def _stock(async_session: AsyncSession, vault: Vault, **supplies: int) -> Storage:
    storage = Storage(vault_id=vault.id, **supplies)
    async_session.add(storage)
    await async_session.commit()
    return storage


@pytest.mark.parametrize(
    ("race", "state"),
    [("ghoul", None), ("super_mutant", None), ("synth", "gen_1"), ("synth", "gen_2")],
)
async def test_non_immune_dwellers_are_offered_stimpaks_but_not_radaway(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, race: str, state: str | None
) -> None:
    dweller.visual_attributes = {"race": race}
    if state is not None:
        dweller.visual_attributes["state_of_being"] = state
    dweller.health = 20
    dweller.max_health = 1000
    dweller.radiation = 35  # Legacy state before immunity was introduced.
    dweller.stimpack = 1
    dweller.radaway = 1
    async_session.add(dweller)
    await async_session.commit()
    status = await med.get_dweller_medical_status(async_session, dweller, vault.id)
    assert (status.recommended_action, status.available_radaways) == ("request_stimpak", 0)
    with pytest.raises(ResourceConflictException, match="cannot use RadAway"):
        await med.use_radaway(async_session, dweller.id)
    assert (await med.use_stimpack(async_session, dweller.id)).health > 20


async def test_gen_3_synth_can_use_radaway(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    dweller.visual_attributes = {"race": "synth", "state_of_being": "gen_3"}
    dweller.health = 20
    dweller.max_health = 1000
    dweller.radiation = 35
    dweller.stimpack = 1
    dweller.radaway = 1
    async_session.add(dweller)
    await async_session.commit()
    status = await med.get_dweller_medical_status(async_session, dweller, vault.id)
    assert status.available_radaways == 1
    assert (await med.use_radaway(async_session, dweller.id)).radiation < 35


class TestUseRadaway:
    async def test_removes_share_of_max_health(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, max_health=100, radiation=80, radaway=2)
        result = await med.use_radaway(async_session, dweller.id)
        assert (result.radiation, result.radaway) == (80 - RADAWAY_REMOVAL, 1)

    async def test_clears_remainder_below_half_bar(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, max_health=100, radiation=10, radaway=2)
        result = await med.use_radaway(async_session, dweller.id)
        assert (result.radiation, result.radaway) == (0, 1)

    async def test_requires_supplies(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, radiation=10, radaway=0)
        with pytest.raises(ResourceConflictException):
            await med.use_radaway(async_session, dweller.id)

    async def test_without_radiation_is_no_change(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, radiation=0, radaway=2)
        with pytest.raises(ContentNoChangeException):
            await med.use_radaway(async_session, dweller.id)

    async def test_dead_dweller_cannot_use_radaway(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, max_health=100, radiation=50, radaway=1, is_dead=True)
        with pytest.raises(ResourceConflictException, match="revived"):
            await med.use_radaway(async_session, dweller.id)
        await async_session.refresh(dweller)
        assert (dweller.radiation, dweller.radaway) == (50, 1)


class TestUseStimpack:
    @pytest.mark.parametrize(("health", "radiation"), [(10, 0), (30, 40)])
    async def test_uses_vault_storage_when_no_stimpack_is_carried(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller, health: int, radiation: int
    ):
        await _set_dweller_state(async_session, dweller, max_health=100, health=health, radiation=radiation, stimpack=0)
        storage = await _stock(async_session, vault, stimpack=2, radaway=3)
        healed = await med.use_stimpack(async_session, dweller.id)
        await async_session.refresh(storage)
        assert healed.health == min(health + HEAL, 100 - radiation)
        assert (healed.stimpack, storage.stimpack, storage.radaway) == (0, 1, 3)

    async def test_prefers_carried_stimpack_without_spending_vault_stock(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        await _set_dweller_state(async_session, dweller, max_health=100, health=10, radiation=0, stimpack=1)
        storage = await _stock(async_session, vault, stimpack=2)
        healed = await med.use_stimpack(async_session, dweller.id)
        await async_session.refresh(storage)
        assert (healed.stimpack, storage.stimpack) == (0, 2)

    @pytest.mark.parametrize("status", [DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING])
    async def test_outside_dwellers_cannot_use_vault_stock(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller, status: DwellerStatusEnum
    ):
        await _set_dweller_state(async_session, dweller, max_health=100, health=10, radiation=0, stimpack=0)
        dweller.status = status
        storage = await _stock(async_session, vault, stimpack=2)
        with pytest.raises(ResourceConflictException, match="No stimpacks"):
            await med.use_stimpack(async_session, dweller.id)
        await async_session.refresh(storage)
        assert (storage.stimpack, dweller.health) == (2, 10)

    @pytest.mark.parametrize(("health", "dead"), [(100, False), (0, True)])
    async def test_does_not_waste_vault_stock_on_full_health_or_dead_dweller(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller, health: int, dead: bool
    ):
        await _set_dweller_state(async_session, dweller, max_health=100, health=health, radiation=0, stimpack=0)
        dweller.is_dead = dead
        storage = await _stock(async_session, vault, stimpack=2)
        expected = ResourceConflictException if dead else ContentNoChangeException
        with pytest.raises(expected):
            await med.use_stimpack(async_session, dweller.id)
        await async_session.refresh(storage)
        assert (storage.stimpack, dweller.health) == (2, health)

    async def test_heals_configured_share_of_max_health(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        await _set_dweller_state(async_session, dweller, max_health=100, health=10, radiation=0, stimpack=1)
        result = await med.use_stimpack(async_session, dweller.id)
        assert (result.health, result.stimpack) == (10 + HEAL, 0)

    async def test_requires_supplies(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, health=10, stimpack=0)
        with pytest.raises(ResourceConflictException):
            await med.use_stimpack(async_session, dweller.id)

    async def test_healing_clamps_at_radiation_ceiling(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        await _set_dweller_state(async_session, dweller, max_health=100, health=30, radiation=40, stimpack=1)
        result = await med.use_stimpack(async_session, dweller.id)
        assert (result.health, result.stimpack) == (min(30 + max(1, HEAL), 60), 0)

    async def test_at_full_health_is_no_change(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, max_health=100, health=100, radiation=0, stimpack=1)
        with pytest.raises(ContentNoChangeException):
            await med.use_stimpack(async_session, dweller.id)

    async def test_dead_dweller_cannot_be_healed(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(
            async_session, dweller, max_health=100, health=0, radiation=0, stimpack=1, is_dead=True
        )
        with pytest.raises(ResourceConflictException, match="revived"):
            await med.use_stimpack(async_session, dweller.id)
        await async_session.refresh(dweller)
        assert (dweller.health, dweller.stimpack) == (0, 1)


class TestDistributeRecoverySupplies:
    async def test_treats_dweller_with_radaway_then_stimpack(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        await _set_dweller_state(async_session, dweller, max_health=100, radiation=100, health=1)
        await _stock(async_session, vault, radaway=10, stimpack=10)
        result = await med.distribute_recovery_supplies(async_session, vault.id)
        assert (result.dwellers_treated, result.radaways_used, result.stimpaks_used) == (1, 1, 1)
        assert (result.vault_radaways, result.vault_stimpacks) == (9, 9)
        await async_session.refresh(dweller)
        assert dweller.radiation == 50
        assert dweller.health == min(1 + max(1, HEAL), dweller.effective_max_health)
        assert dweller.health >= 40

    async def test_skips_clean_dead_and_away_dwellers(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        await _set_dweller_state(async_session, dweller, radiation=40, status=DwellerStatusEnum.EXPLORING)
        await _stock(async_session, vault, radaway=10, stimpack=10)
        result = await med.distribute_recovery_supplies(async_session, vault.id)
        assert (result.dwellers_treated, result.vault_radaways, result.vault_stimpacks) == (0, 10, 10)

    async def test_empty_stock_is_noop(self, async_session: AsyncSession, vault: Vault, dweller: Dweller):
        await _set_dweller_state(async_session, dweller, radiation=50)
        await _stock(async_session, vault, radaway=0, stimpack=0)
        result = await med.distribute_recovery_supplies(async_session, vault.id)
        assert (result.dwellers_treated, result.radaways_used, result.stimpaks_used) == (0, 0, 0)
        await async_session.refresh(dweller)
        assert dweller.radiation == 50
