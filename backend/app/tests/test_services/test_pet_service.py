"""PetService tests (Phase A): vault-scoped list, equip, unequip."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import RarityEnum
from app.models.user import User
from app.services.pet_service import pet_service
from app.utils.exceptions import ResourceNotFoundException


def _pet_data(**overrides) -> dict:
    return {
        "name": "Dogmeat",
        "rarity": RarityEnum.LEGENDARY,
        "value": 500,
        **overrides,
    }


@pytest.mark.asyncio
async def test_list_pets_scoped_to_vault(async_session: AsyncSession, vault, dweller, superuser: User) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    in_storage = await crud.pet.create(async_session, {**_pet_data(name="Stored Pet"), "storage_id": storage.id})
    equipped = await crud.pet.create(async_session, _pet_data(name="Equipped Pet"))
    await crud.pet.equip(db_session=async_session, item_id=equipped.id, dweller_id=dweller.id)

    pets = await pet_service.list_pets(async_session, vault.id, superuser)

    assert {p.id for p in pets} == {in_storage.id, equipped.id}


@pytest.mark.asyncio
async def test_get_pet(async_session: AsyncSession, vault, superuser: User) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    pet = await crud.pet.create(async_session, {**_pet_data(), "storage_id": storage.id})

    fetched = await pet_service.get_pet(async_session, pet.id, superuser)

    assert fetched.id == pet.id


@pytest.mark.asyncio
async def test_get_pet_not_found(async_session: AsyncSession, superuser: User) -> None:
    with pytest.raises(ResourceNotFoundException):
        await pet_service.get_pet(async_session, uuid4(), superuser)


@pytest.mark.asyncio
async def test_equip_pet(async_session: AsyncSession, vault, dweller, superuser: User) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    pet = await crud.pet.create(async_session, {**_pet_data(), "storage_id": storage.id})

    equipped = await pet_service.equip(async_session, dweller.id, pet.id, superuser)

    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None


@pytest.mark.asyncio
async def test_equip_pet_from_other_vault_raises(async_session: AsyncSession, vault, dweller, superuser: User) -> None:
    other_vault = await crud.vault.create(
        async_session,
        {
            "number": 777,
            "bottle_caps": 0,
            "happiness": 50,
            "power": 0,
            "food": 0,
            "water": 0,
            "user_id": superuser.id,
        },
    )
    other_storage = await crud.vault.create_storage(db_session=async_session, vault_id=other_vault.id)
    foreign_pet = await crud.pet.create(async_session, {**_pet_data(), "storage_id": other_storage.id})

    with pytest.raises(ResourceNotFoundException):
        await pet_service.equip(async_session, dweller.id, foreign_pet.id, superuser)


@pytest.mark.asyncio
async def test_unequip_pet(async_session: AsyncSession, vault, dweller, superuser: User) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    pet = await crud.pet.create(async_session, {**_pet_data(), "storage_id": storage.id})
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)

    await pet_service.unequip(async_session, pet.id, superuser)

    reloaded = await crud.pet.get(async_session, pet.id)
    assert reloaded.dweller_id is None
    assert reloaded.storage_id == storage.id
