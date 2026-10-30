"""Pet carrier grant, open, and rarity-roll behavior."""

import operator
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ItemTypeEnum, RarityEnum
from app.crud.vault import vault as vault_crud
from app.models.item import Item
from app.models.pet import Pet
from app.models.storage import Storage
from app.models.vault import Vault
from app.services.rewards import pet_carrier
from app.utils.exceptions import ResourceNotFoundException, ValidationException


async def _storage(async_session: AsyncSession, vault: Vault, max_space: int = 10) -> Storage:
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = max_space
    async_session.add(storage)
    await async_session.flush()
    return storage


async def _carrier(async_session: AsyncSession, vault: Vault) -> UUID:
    granted = await pet_carrier.grant_pet_carrier(async_session, vault.id)
    return UUID(granted["item_id"])


@pytest.mark.asyncio
async def test_grant_pet_carrier_creates_a_carrier_item(async_session: AsyncSession, vault: Vault) -> None:
    """The carrier is a generic Item with the dedicated type."""
    await _storage(async_session, vault)

    carrier_id = await _carrier(async_session, vault)
    item = await async_session.get(Item, carrier_id)

    assert item is not None
    assert item.item_type == ItemTypeEnum.PET_CARRIER
    assert item.name == "Pet Carrier"


@pytest.mark.asyncio
async def test_open_pet_carrier_consumes_carrier_and_stores_one_pet(async_session: AsyncSession, vault: Vault) -> None:
    """Opening swaps the carrier for exactly one stored pet."""
    storage = await _storage(async_session, vault)
    carrier_id = await _carrier(async_session, vault)

    opened = await pet_carrier.open_pet_carrier(async_session, vault.id, carrier_id)

    assert opened["reward_type"] == "pet_carrier"
    assert opened["pet"].name
    assert await async_session.get(Item, carrier_id) is None
    stored = (await async_session.execute(select(Pet).where(Pet.storage_id == storage.id))).scalars().all()
    assert [pet.name for pet in stored] == [opened["pet"].name]


@pytest.mark.asyncio
async def test_open_pet_carrier_works_when_storage_is_full(async_session: AsyncSession, vault: Vault) -> None:
    """The carrier frees the slot the pet takes, so a full vault still opens."""
    storage = await _storage(async_session, vault)
    carrier_id = await _carrier(async_session, vault)
    storage.max_space = 1
    async_session.add(storage)
    await async_session.flush()

    opened = await pet_carrier.open_pet_carrier(async_session, vault.id, carrier_id)

    assert opened["pet"].name
    assert await async_session.get(Item, carrier_id) is None


@pytest.mark.asyncio
async def test_open_pet_carrier_rejects_unknown_item(async_session: AsyncSession, vault: Vault) -> None:
    """Unknown, foreign-vault, and wrong-type rows all surface as not found."""
    await _storage(async_session, vault)

    with pytest.raises(ResourceNotFoundException):
        await pet_carrier.open_pet_carrier(async_session, vault.id, uuid4())


@pytest.mark.asyncio
async def test_open_pet_carrier_keeps_the_carrier_when_the_pool_is_empty(
    async_session: AsyncSession, vault: Vault
) -> None:
    """A failed roll must not consume the item."""
    await _storage(async_session, vault)
    carrier_id = await _carrier(async_session, vault)

    with (
        patch("app.services.catalog_service.load_pets", return_value=[]),
        pytest.raises(ValidationException),
    ):
        await pet_carrier.open_pet_carrier(async_session, vault.id, carrier_id)

    assert await async_session.get(Item, carrier_id) is not None


def test_roll_pet_uses_the_rolled_rarity() -> None:
    """The roll picks from the rarity bucket returned by the weighted choice."""
    with (
        patch("app.services.rewards.pet_carrier.random.choices", return_value=[RarityEnum.RARE]),
        patch(
            "app.services.rewards.pet_carrier.random.choice",
            return_value={"name": "Husky", "rarity": "rare"},
        ),
    ):
        assert pet_carrier._roll_pet() == {"name": "Husky", "rarity": "rare"}


def test_roll_pet_falls_back_when_the_rolled_rarity_is_empty() -> None:
    """An empty legendary bucket falls back to the next populated rarity."""
    with (
        patch(
            "app.services.catalog_service.load_pets",
            return_value=[{"name": "Husky", "rarity": "rare"}],
        ),
        patch("app.services.rewards.pet_carrier.random.choices", return_value=[RarityEnum.LEGENDARY]),
        patch("app.services.rewards.pet_carrier.random.choice", side_effect=operator.itemgetter(0)),
    ):
        assert pet_carrier._roll_pet()["name"] == "Husky"


def test_item_type_constraint_covers_every_enum_value() -> None:
    """The DB CHECK cannot drift from ItemTypeEnum."""
    constraint = next(c for c in Item.__table__.constraints if c.name == "ck_item_item_type")
    sql = str(constraint.sqltext)

    assert all(value.value in sql for value in ItemTypeEnum)
