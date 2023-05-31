import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_dweller


@pytest.mark.asyncio
async def test_create_user(async_session: AsyncSession) -> None:
    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data)
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    assert dweller.first_name == dweller_data["first_name"]
    assert dweller.last_name == dweller_data["last_name"]
    assert dweller.gender == dweller_data["gender"]
    assert dweller.rarity == dweller_data["rarity"]
    assert dweller.level == dweller_data["level"]
    assert dweller.experience == dweller_data["experience"]
    assert dweller.max_health == dweller_data["max_health"]
    assert dweller.health == dweller_data["health"]
    assert dweller.happiness == dweller_data["happiness"]
    assert dweller.is_adult == dweller_data["is_adult"]


@pytest.mark.asyncio
async def test_read_dweller(async_session: AsyncSession):
    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data)
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)
    dweller_read = await crud.dweller.get(async_session, id=dweller.id)
    assert dweller_read
    assert dweller.first_name == dweller_read.first_name
    assert dweller.last_name == dweller_read.last_name


@pytest.mark.asyncio
async def test_dweller_add_exp(async_session: AsyncSession):
    dweller_data = create_fake_dweller()
    dweller_data["experience"] = 0
    dweller_data["level"] = 1
    dweller_in = DwellerCreate(**dweller_data)
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    assert dweller.experience == dweller_data["experience"]

    crud.dweller.add_experience(async_session, dweller=dweller, amount=10)

    assert dweller.experience == 10

    exp_amount = crud.dweller.calculate_experience_required(dweller=dweller)
    crud.dweller.add_experience(async_session, dweller=dweller, amount=exp_amount)

    assert dweller.experience == 10
    assert dweller.level == 2


@pytest.mark.asyncio
async def test_add_dweller_to_vault(async_session: AsyncSession) -> None:
    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data)
    await crud.dweller.create(async_session, obj_in=dweller_in)

    # TODO add when vaults are implemented
    # assert dweller.vault_id is None
    # assert dweller.vault is None
    #
    # vault = crud.vault.create(async_session, obj_in={"name": "Test vault"})
    # dweller = await crud.dweller.add_to_vault(async_session, db_obj=dweller, vault_id=vault.id)
    #
    # assert dweller.vault_id == vault.id
    # assert dweller.vault == vault
