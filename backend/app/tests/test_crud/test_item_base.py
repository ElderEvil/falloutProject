"""Tests for app.crud.item_base — CRUDItem class and module-level helpers.

The CRUD/equip/unequip/scrap tests drive the real async_session fixture (SQLite);
only convert_to_junk's probability branches keep their random-boundary mocks.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from faker import Faker
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import AgeGroupEnum, ItemTypeEnum, JunkTypeEnum, RarityEnum
from app.crud.item_base import CRUDItem, get_item_vault_id, get_items_by_vault
from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.items import create_fake_weapon
from app.tests.factory.vaults import random_vault_number
from app.utils.exceptions import (
    ContentNoChangeException,
    InvalidItemAssignmentException,
    ResourceConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from app.utils.item_factory import build_outfit, build_pet, build_weapon

fake = Faker()


# ---------------------------------------------------------------------------
# Helpers — persist factory-built rows through the real session
# ---------------------------------------------------------------------------


def _make_mock_item(model_class, *, item_id="00000000-0000-0000-0000-000000000001", **overrides) -> MagicMock:
    """Build a mock Weapon or Outfit with explicit attributes (convert_to_junk tests)."""
    m = MagicMock(spec=model_class)
    m.id = item_id
    m.name = "Test Item"
    m.rarity = RarityEnum.COMMON
    m.value = 10
    m.storage_id = None
    m.dweller_id = None
    for key, val in overrides.items():
        setattr(m, key, val)
    return m


async def _create_weapon(async_session: AsyncSession, *, storage_id=None, dweller_id=None, rarity=RarityEnum.COMMON):
    """Persist a factory-built weapon into storage, onto a dweller, or unattached."""
    weapon = build_weapon(create_fake_weapon(), rarity, storage_id=storage_id)
    weapon.dweller_id = dweller_id
    return await crud.weapon.create(db_session=async_session, obj_in=weapon)


async def _create_storage(async_session: AsyncSession, vault_id, *, max_space: int | None = None) -> Storage:
    """Create a vault's storage row, optionally with a non-default capacity."""
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault_id)
    if max_space is not None:
        storage.max_space = max_space
        async_session.add(storage)
        await async_session.commit()
        await async_session.refresh(storage)
    return storage


async def _create_other_vault_storage(async_session: AsyncSession) -> Storage:
    """A second vault's own storage, to prove vault-scoped queries exclude it."""
    user = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username=fake.user_name(), email=fake.email(), password="password123"),
    )
    other_vault = await crud.vault.create(
        db_session=async_session,
        obj_in=VaultCreateWithUserID(number=random_vault_number(), user_id=user.id),
    )
    return await crud.vault.create_storage(db_session=async_session, vault_id=other_vault.id)


# ---------------------------------------------------------------------------
# get_items_by_vault
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_items_by_vault_returns_items(async_session: AsyncSession, vault: Vault, dweller) -> None:
    storage = await _create_storage(async_session, vault.id)
    stored = [await _create_weapon(async_session, storage_id=storage.id) for _ in range(2)]
    equipped = await _create_weapon(async_session, dweller_id=dweller.id)
    # A weapon in another vault's storage must not leak into this vault's results.
    await _create_weapon(async_session, storage_id=(await _create_other_vault_storage(async_session)).id)

    result = await get_items_by_vault(async_session, Weapon, vault.id, skip=0, limit=10)

    assert {weapon.id for weapon in result} == {stored[0].id, stored[1].id, equipped.id}


# ---------------------------------------------------------------------------
# CRUDItem.create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_raises_both_storage_and_dweller_schema(async_session: AsyncSession) -> None:
    with pytest.raises(InvalidItemAssignmentException):
        await CRUDItem(Outfit).create(async_session, {"storage_id": uuid4(), "dweller_id": uuid4()})


# ---------------------------------------------------------------------------
# CRUDItem.equip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_equip_dweller_not_found(async_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFoundException) as exc:
        await CRUDItem(Outfit).equip(db_session=async_session, item_id=uuid4(), dweller_id=uuid4())
    assert "Dweller" in exc.value.detail


@pytest.mark.asyncio
async def test_equip_item_not_found_at_all(async_session: AsyncSession, dweller) -> None:
    with pytest.raises(ResourceNotFoundException) as exc:
        await CRUDItem(Outfit).equip(db_session=async_session, item_id=uuid4(), dweller_id=dweller.id)
    assert "Outfit" in exc.value.detail


@pytest.mark.asyncio
async def test_equip_same_item_already_equipped(async_session: AsyncSession, equipped_dweller) -> None:
    dweller, _, weapon = equipped_dweller

    with pytest.raises(ContentNoChangeException):
        await CRUDItem(Weapon).equip(db_session=async_session, item_id=weapon.id, dweller_id=dweller.id)


@pytest.mark.asyncio
@pytest.mark.parametrize("item_attr", ["weapon", "outfit", "pet"])
@pytest.mark.parametrize("age_group", list(AgeGroupEnum))
async def test_equipment_maturity_gate(
    async_session: AsyncSession, vault: Vault, dweller, item_attr, age_group
) -> None:
    dweller.age_group = age_group
    storage = await _create_storage(async_session, vault.id)
    factory = {"weapon": build_weapon, "outfit": build_outfit, "pet": build_pet}[item_attr]
    item = factory({"name": "Test Gear", "value": 5}, RarityEnum.COMMON, storage_id=storage.id)
    async_session.add(item)
    async_session.add(dweller)
    await async_session.commit()

    if age_group in (AgeGroupEnum.CHILD, AgeGroupEnum.TEEN):
        with pytest.raises(ValidationException, match="adult"):
            await CRUDItem(type(item)).equip(db_session=async_session, item_id=item.id, dweller_id=dweller.id)
    else:
        equipped = await CRUDItem(type(item)).equip(db_session=async_session, item_id=item.id, dweller_id=dweller.id)
        assert equipped.dweller_id == dweller.id


# ---------------------------------------------------------------------------
# _fetch_unequip_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_unequip_data_weapon(async_session: AsyncSession, vault: Vault, equipped_dweller) -> None:
    dweller, _, weapon = equipped_dweller
    storage = await _create_storage(async_session, vault.id)

    result_dweller, storage_id, item_type = await CRUDItem._fetch_unequip_data(async_session, weapon.id)

    assert result_dweller.id == dweller.id
    assert storage_id == storage.id
    assert item_type == ItemTypeEnum.WEAPON


@pytest.mark.asyncio
async def test_fetch_unequip_data_pet(async_session: AsyncSession, vault: Vault, dweller) -> None:
    storage = await _create_storage(async_session, vault.id)
    pet = build_pet({"name": "Dogmeat", "value": 5}, RarityEnum.RARE)
    pet.dweller_id = dweller.id
    pet = await crud.pet.create(db_session=async_session, obj_in=pet)

    result_dweller, storage_id, item_type = await CRUDItem._fetch_unequip_data(async_session, pet.id)

    assert result_dweller.id == dweller.id
    assert storage_id == storage.id
    assert item_type == ItemTypeEnum.PET


@pytest.mark.asyncio
async def test_fetch_unequip_data_not_found(async_session: AsyncSession) -> None:
    assert await CRUDItem._fetch_unequip_data(async_session, uuid4()) == (None, None, None)


# ---------------------------------------------------------------------------
# _get_item_model
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _update_item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_item_executes_update(async_session: AsyncSession, vault: Vault) -> None:
    source = await _create_storage(async_session, vault.id)
    target = await _create_storage(async_session, vault.id)
    weapon = await _create_weapon(async_session, storage_id=source.id)

    await CRUDItem._update_item(async_session, Weapon, weapon.id, target.id)
    await async_session.commit()

    reloaded = await crud.weapon.get(async_session, weapon.id)
    assert reloaded.dweller_id is None
    assert reloaded.storage_id == target.id


# ---------------------------------------------------------------------------
# _update_dweller
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_dweller_clears_weapon(async_session: AsyncSession, equipped_dweller) -> None:
    dweller, _, _ = equipped_dweller
    result = await async_session.execute(
        select(Dweller).where(Dweller.id == dweller.id).options(selectinload(Dweller.weapon))
    )
    loaded_dweller = result.scalar_one()
    assert loaded_dweller.weapon is not None

    await CRUDItem._update_dweller(async_session, loaded_dweller, ItemTypeEnum.WEAPON)

    assert loaded_dweller.weapon is None


# ---------------------------------------------------------------------------
# unequip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unequip_success(async_session: AsyncSession, vault: Vault, equipped_dweller) -> None:
    dweller, _, weapon = equipped_dweller
    storage = await _create_storage(async_session, vault.id)

    await CRUDItem(Weapon).unequip(db_session=async_session, item_id=weapon.id)

    reloaded = await crud.weapon.get(async_session, weapon.id)
    assert reloaded.dweller_id is None
    assert reloaded.storage_id == storage.id


@pytest.mark.asyncio
async def test_unequip_not_found(async_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFoundException) as exc:
        await CRUDItem(Weapon).unequip(db_session=async_session, item_id=uuid4())
    assert "Dweller" in exc.value.detail


# ---------------------------------------------------------------------------
# convert_to_junk
# ---------------------------------------------------------------------------


class TestConvertToJunk:
    """Tests for CRUDItem.convert_to_junk static method."""

    @patch("app.crud.item_base.random.choice")
    @patch("app.crud.item_base.random.random")
    def test_legendary_with_both_probs(self, mock_random: MagicMock, mock_choice: MagicMock) -> None:
        mock_choice.side_effect = [JunkTypeEnum.CIRCUITRY, JunkTypeEnum.LEATHER, JunkTypeEnum.ADHESIVE]
        mock_random.return_value = 0.1  # below 0.4 and 0.6

        item = _make_mock_item(Weapon, rarity=RarityEnum.LEGENDARY)
        results = CRUDItem.convert_to_junk(item)

        rarities = {j.rarity for j in results}
        assert RarityEnum.LEGENDARY in rarities
        assert RarityEnum.RARE in rarities
        assert len(results) == 2

    def test_unsupported_rarity_raises(self) -> None:
        item = _make_mock_item(Weapon, rarity="mythic")
        with pytest.raises(ValueError, match="not supported"):
            CRUDItem.convert_to_junk(item)


# ---------------------------------------------------------------------------
# scrap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrap_success(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _create_storage(async_session, vault.id, max_space=10)
    weapon = await _create_weapon(async_session, storage_id=storage.id, rarity=RarityEnum.COMMON)

    results = await CRUDItem(Weapon).scrap(db_session=async_session, item_id=weapon.id)

    assert len(results) == 1
    assert all(junk.storage_id == storage.id for junk in results)
    assert await crud.weapon.get_or_none(async_session, weapon.id) is None
    assert [junk.id for junk in await crud.junk.get_in_storage(async_session, storage.id)] == [results[0].id]


@pytest.mark.asyncio
async def test_scrap_rejects_when_junk_would_exceed_capacity(async_session: AsyncSession, vault: Vault) -> None:
    """A scrap whose junk would overflow storage is rejected before anything changes."""
    storage = await _create_storage(async_session, vault.id, max_space=1)
    weapon = await _create_weapon(async_session, storage_id=storage.id, rarity=RarityEnum.LEGENDARY)

    # Pin the RNG so a LEGENDARY scrap always yields two junk rows.
    with (
        patch(
            "app.crud.item_base.random.choice",
            side_effect=[JunkTypeEnum.CIRCUITRY, JunkTypeEnum.LEATHER, JunkTypeEnum.ADHESIVE],
        ),
        patch("app.crud.item_base.random.random", return_value=0.0),
        pytest.raises(ResourceConflictException, match="Storage is full"),
    ):
        await CRUDItem(Weapon).scrap(db_session=async_session, item_id=weapon.id)

    assert await crud.weapon.get_or_none(async_session, weapon.id) is not None
    assert await crud.junk.get_in_storage(async_session, storage.id) == []


@pytest.mark.asyncio
async def test_scrap_not_found(async_session: AsyncSession) -> None:
    with pytest.raises(ResourceNotFoundException) as exc:
        await CRUDItem(Outfit).scrap(db_session=async_session, item_id=uuid4())
    assert "Outfit" in exc.value.detail


# ---------------------------------------------------------------------------
# get_item_vault_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_item_vault_id_from_storage(async_session: AsyncSession, vault: Vault) -> None:
    storage = await _create_storage(async_session, vault.id)
    weapon = await _create_weapon(async_session, storage_id=storage.id)

    assert await get_item_vault_id(async_session, weapon) == vault.id


@pytest.mark.asyncio
async def test_get_item_vault_id_from_dweller(async_session: AsyncSession, vault: Vault, dweller) -> None:
    weapon = await _create_weapon(async_session, dweller_id=dweller.id)

    assert await get_item_vault_id(async_session, weapon) == vault.id


@pytest.mark.asyncio
async def test_get_item_vault_id_unattached(async_session: AsyncSession) -> None:
    weapon = await _create_weapon(async_session)

    assert await get_item_vault_id(async_session, weapon) is None


# ---------------------------------------------------------------------------
# Inheritance / init smoke tests
# ---------------------------------------------------------------------------
