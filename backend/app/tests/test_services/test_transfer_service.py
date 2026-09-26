"""Transfer population-capacity accounting."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.transfer_service import TransferService
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ValidationException


async def _vault(async_session: AsyncSession, *, population_max: int):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    vault.population_max = population_max
    async_session.add(vault)
    await async_session.commit()
    return vault


async def _dweller(async_session: AsyncSession, vault_id, **overrides):
    dweller = await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=vault_id)
    )
    for key, value in overrides.items():
        setattr(dweller, key, value)
    async_session.add(dweller)
    await async_session.commit()
    return dweller


@pytest.mark.asyncio
async def test_transfer_of_dead_dweller_is_not_blocked_by_a_full_destination(async_session: AsyncSession) -> None:
    """A dead dweller adds no living population, so a full destination still accepts it."""
    source = await _vault(async_session, population_max=8)
    dest = await _vault(async_session, population_max=1)
    await _dweller(async_session, dest.id)
    dead = await _dweller(async_session, source.id, is_dead=True)

    moved = await TransferService.transfer_dwellers(async_session, [dead.id], dest.id)

    assert [dweller.id for dweller in moved] == [dead.id]


@pytest.mark.asyncio
async def test_transfer_of_living_dweller_is_rejected_by_a_full_destination(async_session: AsyncSession) -> None:
    """A living arrival needs a free slot; a full destination refuses it."""
    source = await _vault(async_session, population_max=8)
    dest = await _vault(async_session, population_max=1)
    await _dweller(async_session, dest.id)
    living = await _dweller(async_session, source.id)

    with pytest.raises(ValidationException, match="Destination vault full"):
        await TransferService.transfer_dwellers(async_session, [living.id], dest.id)
