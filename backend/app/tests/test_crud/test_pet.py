"""Pet model + CRUDItem equip/unequip + storage bucket tests (Phase A)."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import RarityEnum
from app.models.pet import Pet
from app.utils.exceptions import ContentNoChangeException, InvalidItemAssignmentException, ResourceNotFoundException


def _pet_data(**overrides) -> dict:
    return {
        "name": "Dogmeat",
        "rarity": RarityEnum.LEGENDARY,
        "value": 500,
        **overrides,
    }


@pytest.mark.asyncio
async def test_pet_model_instantiation(async_session: AsyncSession) -> None:
    pet = Pet(**_pet_data())
    async_session.add(pet)
    await async_session.flush()

    assert pet.id is not None
    assert pet.dweller_id is None
    assert pet.storage_id is None
    assert pet.legacy_item_id is None


@pytest.mark.asyncio
async def test_pet_check_constraint_rejects_both_storage_and_dweller(async_session: AsyncSession, dweller) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=dweller.vault_id)
    pet = Pet(**_pet_data(), storage_id=storage.id, dweller_id=dweller.id)

    async_session.add(pet)
    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


@pytest.mark.asyncio
async def test_pet_create_rejects_both_storage_and_dweller(async_session: AsyncSession, dweller) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=dweller.vault_id)
    with pytest.raises(InvalidItemAssignmentException):
        await crud.pet.create(async_session, {**_pet_data(), "storage_id": storage.id, "dweller_id": dweller.id})


@pytest.mark.asyncio
async def test_first_equip_assigns_dweller_only(async_session: AsyncSession, dweller) -> None:
    pet = await crud.pet.create(async_session, obj_in=_pet_data())

    equipped = await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)

    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None


@pytest.mark.asyncio
async def test_reequip_returns_displaced_pet_to_storage(async_session: AsyncSession, dweller, vault) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    old = await crud.pet.create(async_session, obj_in=_pet_data(name="Old Pet"))
    new = await crud.pet.create(async_session, obj_in=_pet_data(name="New Pet"))
    await crud.pet.equip(db_session=async_session, item_id=old.id, dweller_id=dweller.id)

    await crud.pet.equip(db_session=async_session, item_id=new.id, dweller_id=dweller.id)

    displaced = await crud.pet.get(async_session, old.id)
    assert displaced.dweller_id is None
    assert displaced.storage_id == storage.id
    equipped = await crud.pet.get(async_session, new.id)
    assert equipped.dweller_id == dweller.id
    assert equipped.storage_id is None


@pytest.mark.asyncio
async def test_unequip_returns_pet_to_storage(async_session: AsyncSession, dweller, vault) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    pet = await crud.pet.create(async_session, obj_in=_pet_data())
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)

    await crud.pet.unequip(db_session=async_session, item_id=pet.id)

    reloaded = await crud.pet.get(async_session, pet.id)
    assert reloaded.dweller_id is None
    assert reloaded.storage_id == storage.id


@pytest.mark.asyncio
async def test_equip_same_pet_raises_content_no_change(async_session: AsyncSession, dweller) -> None:
    pet = await crud.pet.create(async_session, obj_in=_pet_data())
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)

    with pytest.raises(ContentNoChangeException):
        await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)


@pytest.mark.asyncio
async def test_equip_missing_dweller_raises(async_session: AsyncSession) -> None:
    pet = await crud.pet.create(async_session, obj_in=_pet_data())

    with pytest.raises(ResourceNotFoundException):
        await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=uuid4())


@pytest.mark.asyncio
async def test_equip_missing_pet_raises(async_session: AsyncSession, dweller) -> None:
    with pytest.raises(ResourceNotFoundException):
        await crud.pet.equip(db_session=async_session, item_id=uuid4(), dweller_id=dweller.id)


@pytest.mark.asyncio
async def test_unequip_missing_pet_raises(async_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFoundException):
        await crud.pet.unequip(db_session=async_session, item_id=uuid4())


@pytest.mark.asyncio
async def test_count_items_includes_pets(async_session: AsyncSession, vault) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    await crud.pet.create(async_session, obj_in={**_pet_data(), "storage_id": storage.id})

    assert await crud.storage.count_storage_items(async_session, storage.id) == 1


@pytest.mark.asyncio
async def test_get_all_items_includes_pets_bucket(async_session: AsyncSession, vault) -> None:
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    pet = await crud.pet.create(async_session, obj_in={**_pet_data(), "storage_id": storage.id})

    items = await crud.storage.get_all_items(async_session, storage.id)

    assert [p.id for p in items["pets"]] == [pet.id]
    assert items["weapons"] == []
    assert items["outfits"] == []
    assert items["junk"] == []
    assert items["items"] == []


@pytest.mark.asyncio
async def test_get_items_by_vault_scopes_pets(async_session: AsyncSession, vault, dweller) -> None:
    from app.crud.item_base import get_items_by_vault

    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    in_storage = await crud.pet.create(async_session, obj_in={**_pet_data(name="Stored Pet"), "storage_id": storage.id})
    equipped = await crud.pet.create(async_session, obj_in=_pet_data(name="Equipped Pet"))
    await crud.pet.equip(db_session=async_session, item_id=equipped.id, dweller_id=dweller.id)

    pets = await get_items_by_vault(async_session, Pet, vault.id)

    assert {p.id for p in pets} == {in_storage.id, equipped.id}


@pytest.mark.asyncio
async def test_equip_does_not_delete_displaced_pet(async_session: AsyncSession, dweller, vault) -> None:
    """The displaced pet survives re-equip (FK-only writes, no cascade delete)."""
    await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    old = await crud.pet.create(async_session, obj_in=_pet_data(name="Old Pet"))
    new = await crud.pet.create(async_session, obj_in=_pet_data(name="New Pet"))
    await crud.pet.equip(db_session=async_session, item_id=old.id, dweller_id=dweller.id)

    await crud.pet.equip(db_session=async_session, item_id=new.id, dweller_id=dweller.id)

    result = await async_session.execute(select(Pet).where(Pet.id == old.id))
    assert result.scalar_one_or_none() is not None
