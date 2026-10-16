"""Survival-mode vault behavior: immediate permanent death, standard mode unchanged."""

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import AvailabilityEnum, LifecycleEnum, VaultModeEnum
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import DeathCauseEnum, DwellerStatusEnum
from app.schemas.dweller import DwellerCreate
from app.services.family.death_service import death_service
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.exceptions import ContentNoChangeException


@pytest_asyncio.fixture(name="survival_vault")
async def survival_vault_fixture(async_session: AsyncSession, vault: Vault) -> Vault:
    vault.vault_mode = VaultModeEnum.SURVIVAL.value
    async_session.add(vault)
    await async_session.commit()
    await async_session.refresh(vault)
    return vault


async def _alive_dweller(async_session: AsyncSession, vault: Vault) -> Dweller:
    data = create_fake_dweller()
    data.update({"status": DwellerStatusEnum.IDLE.value, "is_dead": False, "is_permanently_dead": False, "health": 100})
    return await crud.dweller.create(db_session=async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))


async def test_survival_death_is_immediately_permanent(async_session: AsyncSession, survival_vault: Vault) -> None:
    dweller = await _alive_dweller(async_session, survival_vault)

    updated = await death_service.mark_as_dead(async_session, dweller, DeathCauseEnum.INCIDENT)

    assert updated.is_permanently_dead is True
    assert updated.lifecycle == LifecycleEnum.DEAD_PERMANENT
    assert updated.availability == AvailabilityEnum.ARCHIVE
    assert updated.room_id is None


async def test_survival_death_skips_revivable_list_in_favor_of_graveyard(
    async_session: AsyncSession, survival_vault: Vault
) -> None:
    dweller = await _alive_dweller(async_session, survival_vault)
    await death_service.mark_as_dead(async_session, dweller, DeathCauseEnum.COMBAT)

    revivable = await crud.dweller.get_dead_dwellers(async_session, survival_vault.id, include_permanent=False)
    assert dweller.id not in {row.id for row in revivable}

    graveyard = await crud.dweller.get_graveyard(async_session, survival_vault.id)
    assert dweller.id in {row.id for row in graveyard}


async def test_survival_death_cannot_be_revived(async_session: AsyncSession, survival_vault: Vault) -> None:
    dweller = await _alive_dweller(async_session, survival_vault)
    await death_service.mark_as_dead(async_session, dweller, DeathCauseEnum.EXPLORATION)
    owner = await crud.user.get(async_session, survival_vault.user_id)

    with pytest.raises(ContentNoChangeException):
        await death_service.revive_dweller(async_session, dweller.id, owner)


async def test_standard_death_stays_revivable(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _alive_dweller(async_session, vault)

    updated = await death_service.mark_as_dead(async_session, dweller, DeathCauseEnum.HEALTH)

    assert updated.is_permanently_dead is False
    assert updated.lifecycle == LifecycleEnum.DEAD_REVIVABLE
    assert updated.availability == AvailabilityEnum.VAULT

    vault.bottle_caps = 10_000
    async_session.add(vault)
    await async_session.commit()
    owner = await crud.user.get(async_session, vault.user_id)

    revived = await death_service.revive_dweller(async_session, updated.id, owner)

    assert revived.dweller.is_dead is False
    refreshed = await crud.dweller.get(async_session, updated.id)
    assert refreshed.lifecycle == LifecycleEnum.ALIVE
