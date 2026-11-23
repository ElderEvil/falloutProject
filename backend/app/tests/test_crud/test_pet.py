from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import RarityEnum
from app.crud.item_base import get_items_by_vault
from app.models.pet import Pet
from app.utils.exceptions import ContentNoChangeException, InvalidItemAssignmentException, ResourceNotFoundException


def _pet_data(**overrides) -> dict:
    return {"name": "Dogmeat", "rarity": RarityEnum.LEGENDARY, "value": 500, **overrides}


async def _pet(async_session: AsyncSession, **overrides) -> Pet:
    return await crud.pet.create(async_session, obj_in=_pet_data(**overrides))


async def _storage(async_session: AsyncSession, vault_id):
    return await crud.vault.create_storage(db_session=async_session, vault_id=vault_id)


async def test_pet_model_instantiation(async_session: AsyncSession) -> None:
    pet = Pet(**_pet_data())
    async_session.add(pet)
    await async_session.flush()
    assert pet.id is not None
    assert pet.dweller_id is None
    assert pet.storage_id is None
    assert pet.legacy_item_id is None


async def test_pet_check_constraint_rejects_both_storage_and_dweller(async_session: AsyncSession, dweller) -> None:
    storage = await _storage(async_session, dweller.vault_id)
    async_session.add(Pet(**_pet_data(), storage_id=storage.id, dweller_id=dweller.id))
    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


async def test_pet_create_rejects_both_storage_and_dweller(async_session: AsyncSession, dweller) -> None:
    storage = await _storage(async_session, dweller.vault_id)
    with pytest.raises(InvalidItemAssignmentException):
        await _pet(async_session, storage_id=storage.id, dweller_id=dweller.id)


async def test_first_equip_assigns_dweller_only(async_session: AsyncSession, dweller) -> None:
    pet = await _pet(async_session)
    equipped = await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)
    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None


async def test_reequip_routes_displaced_pet_to_storage_without_deleting_it(
    async_session: AsyncSession, dweller, vault
) -> None:
    storage = await _storage(async_session, vault.id)
    old = await _pet(async_session, name="Old Pet")
    new = await _pet(async_session, name="New Pet")
    await crud.pet.equip(db_session=async_session, item_id=old.id, dweller_id=dweller.id)
    await crud.pet.equip(db_session=async_session, item_id=new.id, dweller_id=dweller.id)
    displaced = await crud.pet.get(async_session, old.id)
    assert displaced.dweller_id is None
    assert displaced.storage_id == storage.id
    equipped = await crud.pet.get(async_session, new.id)
    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None
    result = await async_session.execute(select(Pet).where(Pet.id == old.id))
    assert result.scalar_one_or_none() is not None


async def test_unequip_returns_pet_to_storage(async_session: AsyncSession, dweller, vault) -> None:
    storage = await _storage(async_session, vault.id)
    pet = await _pet(async_session)
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)
    await crud.pet.unequip(db_session=async_session, item_id=pet.id)
    reloaded = await crud.pet.get(async_session, pet.id)
    assert reloaded.dweller_id is None
    assert reloaded.storage_id == storage.id


async def test_equip_same_pet_raises_content_no_change(async_session: AsyncSession, dweller) -> None:
    pet = await _pet(async_session)
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)
    with pytest.raises(ContentNoChangeException):
        await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)


@pytest.mark.parametrize("op", ["equip_missing_dweller", "equip_missing_pet", "unequip_missing_pet"])
async def test_missing_resource_raises(async_session: AsyncSession, dweller, op) -> None:
    pet = await _pet(async_session)
    item_id, dweller_id = (pet.id, uuid4()) if op == "equip_missing_dweller" else (uuid4(), dweller.id)
    call = (
        crud.pet.unequip(db_session=async_session, item_id=item_id)
        if op == "unequip_missing_pet"
        else crud.pet.equip(db_session=async_session, item_id=item_id, dweller_id=dweller_id)
    )
    with pytest.raises(ResourceNotFoundException):
        await call


async def test_storage_buckets_include_pets_only(async_session: AsyncSession, vault) -> None:
    storage = await _storage(async_session, vault.id)
    pet = await _pet(async_session, storage_id=storage.id)
    assert await crud.storage.count_storage_items(async_session, storage.id) == 1
    items = await crud.storage.get_all_items(async_session, storage.id)
    assert [p.id for p in items["pets"]] == [pet.id]
    assert items["weapons"] == []
    assert items["outfits"] == []
    assert items["junk"] == []
    assert items["items"] == []


async def test_get_items_by_vault_scopes_pets(async_session: AsyncSession, vault, dweller) -> None:
    storage = await _storage(async_session, vault.id)
    in_storage = await _pet(async_session, name="Stored Pet", storage_id=storage.id)
    equipped = await _pet(async_session, name="Equipped Pet")
    await crud.pet.equip(db_session=async_session, item_id=equipped.id, dweller_id=dweller.id)
    pets = await get_items_by_vault(async_session, Pet, vault.id)
    assert {p.id for p in pets} == {in_storage.id, equipped.id}
