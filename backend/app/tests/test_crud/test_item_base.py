"""Tests for app.crud.item_base — CRUDItem class and module-level helpers.

Uses AsyncMock to avoid hitting a real database.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.crud.item_base import CRUDItem, get_items_by_vault, get_items_list
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.common import ItemTypeEnum, JunkTypeEnum, RarityEnum
from app.utils.exceptions import (
    ContentNoChangeException,
    InvalidItemAssignmentException,
    ResourceNotFoundException,
)

# ---------------------------------------------------------------------------
# Mock helpers — avoid AsyncMock child-mock coroutine trap
# ---------------------------------------------------------------------------

# When you chain attrs on an AsyncMock (e.g. mock.execute.return_value.scalars),
# each child inherits AsyncMock, so "scalars()" returns a coroutine.
# We build the chain explicitly with plain MagicMock leaves.


def _setup_execute_scalars_all(session_mock: MagicMock, items: list) -> None:
    """Configure session.execute → scalars().all() → *items*.

    Important: MagicMock call (scalars()) returns mock.return_value, so we
    must set return_value to carry the .all chain.
    """
    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock())
    result.scalars.return_value.all = MagicMock(return_value=items)
    session_mock.execute = AsyncMock(return_value=result)


def _setup_execute_first(session_mock: MagicMock, row) -> None:
    """Configure session.execute → .first() → *row*."""
    result_mock = MagicMock()
    result_mock.first = MagicMock(return_value=row)
    session_mock.execute = AsyncMock(return_value=result_mock)


def _setup_execute_scalar_one_or_none(session_mock: MagicMock, value) -> None:
    """Configure session.execute → .scalar_one_or_none() → *value*."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=value)
    session_mock.execute = AsyncMock(return_value=result_mock)


def _make_mock_item(model_class, *, item_id="00000000-0000-0000-0000-000000000001", **overrides) -> MagicMock:
    """Build a mock Weapon or Outfit with explicit attributes."""
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


def _setup_equip_mocks(
    session_mock: MagicMock,
    *,
    dweller: MagicMock | None,
    item: MagicMock | None,
    current_item: MagicMock | None,
) -> None:
    """Configure session.execute (dweller, then current item) and session.get (target item)."""
    dweller_result = MagicMock()
    dweller_result.scalar_one_or_none = MagicMock(return_value=dweller)
    current_result = MagicMock()
    current_result.scalar_one_or_none = MagicMock(return_value=current_item)
    session_mock.execute = AsyncMock(side_effect=[dweller_result, current_result])
    session_mock.get = AsyncMock(return_value=item)


def _new_session() -> MagicMock:
    """Create a base session mock with commit/refresh/delete/rollback as AsyncMock."""
    s = MagicMock()
    s.commit = AsyncMock()
    s.refresh = AsyncMock()
    s.delete = AsyncMock()
    s.rollback = AsyncMock()
    s.get = AsyncMock()
    return s


# ---------------------------------------------------------------------------
# get_items_by_vault
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_items_by_vault_returns_items() -> None:
    session = _new_session()
    mock_item = _make_mock_item(Weapon)
    _setup_execute_scalars_all(session, [mock_item])

    result = await get_items_by_vault(session, Weapon, "00000000-0000-0000-0000-000000000099", skip=0, limit=10)
    assert result == [mock_item]
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_items_by_vault_empty() -> None:
    session = _new_session()
    _setup_execute_scalars_all(session, [])

    result = await get_items_by_vault(session, Outfit, "00000000-0000-0000-0000-000000000099")
    assert result == []
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_items_by_vault_pagination() -> None:
    session = _new_session()
    _setup_execute_scalars_all(session, [])

    await get_items_by_vault(session, Outfit, "v-1", skip=20, limit=5)
    session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_items_list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_items_list_with_vault_id_delegates() -> None:
    session = _new_session()
    crud_instance = MagicMock(spec=CRUDItem)

    with patch("app.crud.item_base.get_items_by_vault", new=AsyncMock(return_value=["item1", "item2"])) as mock_fn:
        result = await get_items_list(crud_instance, session, Weapon, vault_id="v1", skip=0, limit=5)
        mock_fn.assert_called_once_with(session, Weapon, "v1", 0, 5)
        assert result == ["item1", "item2"]


@pytest.mark.asyncio
async def test_get_items_list_without_vault_id() -> None:
    session = _new_session()
    crud_instance = MagicMock(spec=CRUDItem)
    crud_instance.get_multi = AsyncMock(return_value=["a", "b"])

    result = await get_items_list(crud_instance, session, Outfit, skip=10, limit=20)
    crud_instance.get_multi.assert_called_once_with(session, skip=10, limit=20)
    assert result == ["a", "b"]


@pytest.mark.asyncio
async def test_get_items_list_default_args() -> None:
    session = _new_session()
    crud_instance = MagicMock(spec=CRUDItem)
    crud_instance.get_multi = AsyncMock(return_value=[])
    await get_items_list(crud_instance, session, Weapon)
    crud_instance.get_multi.assert_called_once_with(session, skip=0, limit=100)


# ---------------------------------------------------------------------------
# CRUDItem.create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_dict_no_conflict_delegates() -> None:
    """create() with a plain dict validates and delegates to super."""
    session = _new_session()
    crud = CRUDItem(Weapon)
    obj_in = {"name": "New Weapon", "storage_id": "s1"}
    expected = _make_mock_item(Weapon)

    with patch("app.crud.base.CRUDBase.create", new=AsyncMock(return_value=expected)) as mock_super:
        result = await crud.create(session, obj_in)
        mock_super.assert_called_once_with(session, obj_in)
        assert result is expected


@pytest.mark.asyncio
async def test_create_from_mock_schema() -> None:
    """create() from a schema object calls model_dump then super."""
    session = _new_session()
    crud = CRUDItem(Weapon)
    mock_schema = MagicMock()
    mock_schema.model_dump.return_value = {"name": "Axe", "rarity": "common"}
    expected = _make_mock_item(Weapon)

    with patch("app.crud.base.CRUDBase.create", new=AsyncMock(return_value=expected)) as mock_super:
        result = await crud.create(session, mock_schema)
        mock_super.assert_called_once_with(session, {"name": "Axe", "rarity": "common"})
        assert result is expected


@pytest.mark.asyncio
async def test_create_raises_both_storage_and_dweller_dict() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    obj_in = {"storage_id": "s1", "dweller_id": "d1"}
    with pytest.raises(InvalidItemAssignmentException):
        await crud.create(session, obj_in)


@pytest.mark.asyncio
async def test_create_raises_both_storage_and_dweller_schema() -> None:
    session = _new_session()
    crud = CRUDItem(Outfit)
    mock_schema = MagicMock()
    mock_schema.model_dump.return_value = {"storage_id": "s1", "dweller_id": "d1"}
    with pytest.raises(InvalidItemAssignmentException):
        await crud.create(session, mock_schema)


# ---------------------------------------------------------------------------
# CRUDItem.update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_raises_both_storage_and_dweller() -> None:
    session = _new_session()
    crud = CRUDItem(Outfit)
    update_schema = MagicMock()
    update_schema.storage_id = "s1"
    update_schema.dweller_id = "d1"

    with pytest.raises(InvalidItemAssignmentException):
        await crud.update(session, id="item1", obj_in=update_schema)


@pytest.mark.asyncio
async def test_update_no_conflict() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    update_schema = MagicMock()
    update_schema.storage_id = "s1"
    update_schema.dweller_id = None
    expected = _make_mock_item(Weapon)

    with patch("app.crud.base.CRUDBase.update", new=AsyncMock(return_value=expected)) as mock_super:
        result = await crud.update(session, id="item1", obj_in=update_schema)
        mock_super.assert_called_once_with(session, id="item1", obj_in=update_schema)
        assert result is expected


# ---------------------------------------------------------------------------
# CRUDItem.equip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_equip_new_item_to_unequipped_dweller() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    item = _make_mock_item(Weapon, item_id="w-new")

    mock_storage = MagicMock(id="storage-1")
    mock_vault = MagicMock(storage=mock_storage)
    mock_dweller = MagicMock(id="d1", vault=mock_vault, weapon=None)

    _setup_equip_mocks(session, dweller=mock_dweller, item=item, current_item=None)

    await crud.equip(db_session=session, item_id="w-new", dweller_id="d1")

    assert item.dweller_id == mock_dweller.id
    assert item.storage_id is None
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(item)


@pytest.mark.asyncio
async def test_equip_dweller_not_found() -> None:
    session = _new_session()
    crud = CRUDItem(Outfit)

    _setup_equip_mocks(session, dweller=None, item=None, current_item=None)

    with pytest.raises(ResourceNotFoundException) as exc:
        await crud.equip(db_session=session, item_id="o-x", dweller_id="d-999")
    assert "Dweller" in exc.value.detail


@pytest.mark.asyncio
async def test_equip_item_fetched_separately_when_not_in_join() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    item = _make_mock_item(Weapon, item_id="w2")

    mock_storage = MagicMock(id="st-1")
    mock_vault = MagicMock(storage=mock_storage)
    mock_dweller = MagicMock(id="d1", vault=mock_vault, weapon=None)

    _setup_equip_mocks(session, dweller=mock_dweller, item=item, current_item=None)

    await crud.equip(db_session=session, item_id="w2", dweller_id="d1")
    session.get.assert_called_once_with(Weapon, "w2")
    assert item.dweller_id == mock_dweller.id


@pytest.mark.asyncio
async def test_equip_item_not_found_at_all() -> None:
    session = _new_session()
    crud = CRUDItem(Outfit)

    mock_storage = MagicMock(id="st-1")
    mock_vault = MagicMock(storage=mock_storage)
    mock_dweller = MagicMock(id="d1", vault=mock_vault, outfit=None)

    _setup_equip_mocks(session, dweller=mock_dweller, item=None, current_item=None)

    with pytest.raises(ResourceNotFoundException) as exc:
        await crud.equip(db_session=session, item_id="o-missing", dweller_id="d1")
    assert "Outfit" in exc.value.detail


@pytest.mark.asyncio
async def test_equip_same_item_already_equipped() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    item = _make_mock_item(Weapon, item_id="w-same")

    mock_storage = MagicMock(id="st-1")
    mock_vault = MagicMock(storage=mock_storage)
    mock_dweller = MagicMock(id="d1", vault=mock_vault, weapon=item)

    _setup_equip_mocks(session, dweller=mock_dweller, item=item, current_item=item)

    with pytest.raises(ContentNoChangeException):
        await crud.equip(db_session=session, item_id="w-same", dweller_id="d1")


@pytest.mark.asyncio
async def test_equip_replaces_existing_item() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    old_item = _make_mock_item(Weapon, item_id="w-old")
    new_item = _make_mock_item(Weapon, item_id="w-new")

    mock_storage = MagicMock(id="st-1")
    mock_vault = MagicMock(storage=mock_storage)
    mock_dweller = MagicMock(id="d1", vault=mock_vault, weapon=old_item)

    _setup_equip_mocks(session, dweller=mock_dweller, item=new_item, current_item=old_item)

    await crud.equip(db_session=session, item_id="w-new", dweller_id="d1")

    assert old_item.dweller_id is None
    assert old_item.storage_id == mock_storage.id
    assert new_item.dweller_id == mock_dweller.id
    assert new_item.storage_id is None


# ---------------------------------------------------------------------------
# _fetch_unequip_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_unequip_data_weapon() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    mock_dweller = MagicMock()
    row = (mock_dweller, "storage-x", True)
    _setup_execute_first(session, row)

    dweller, storage_id, item_type = await crud._fetch_unequip_data(session, "w-1")
    assert dweller is mock_dweller
    assert storage_id == "storage-x"
    assert item_type == ItemTypeEnum.WEAPON


@pytest.mark.asyncio
async def test_fetch_unequip_data_outfit() -> None:
    session = _new_session()
    crud = CRUDItem(Outfit)
    mock_dweller = MagicMock()
    row = (mock_dweller, "storage-y", False)
    _setup_execute_first(session, row)

    _dweller, _sid, item_type = await crud._fetch_unequip_data(session, "o-1")
    assert item_type == ItemTypeEnum.OUTFIT


@pytest.mark.asyncio
async def test_fetch_unequip_data_not_found() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    _setup_execute_first(session, None)

    result = await crud._fetch_unequip_data(session, "missing")
    assert result == (None, None, None)


# ---------------------------------------------------------------------------
# _get_item_model
# ---------------------------------------------------------------------------


def test_get_item_model_weapon() -> None:
    assert CRUDItem._get_item_model(ItemTypeEnum.WEAPON) is Weapon


def test_get_item_model_outfit() -> None:
    assert CRUDItem._get_item_model(ItemTypeEnum.OUTFIT) is Outfit


# ---------------------------------------------------------------------------
# _update_item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_item_executes_update() -> None:
    session = _new_session()
    session.execute = AsyncMock()
    await CRUDItem._update_item(session, Weapon, "w-id", "st-99")
    session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# _update_dweller
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_dweller_clears_weapon() -> None:
    session = _new_session()
    session.add = MagicMock()
    mock_dweller = MagicMock()

    await CRUDItem._update_dweller(session, mock_dweller, ItemTypeEnum.WEAPON)
    assert mock_dweller.weapon is None
    session.add.assert_called_once_with(mock_dweller)


@pytest.mark.asyncio
async def test_update_dweller_clears_outfit() -> None:
    session = _new_session()
    session.add = MagicMock()
    mock_dweller = MagicMock()

    await CRUDItem._update_dweller(session, mock_dweller, ItemTypeEnum.OUTFIT)
    assert mock_dweller.outfit is None
    session.add.assert_called_once_with(mock_dweller)


# ---------------------------------------------------------------------------
# unequip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unequip_success() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    mock_dweller = MagicMock()

    with (
        patch.object(
            crud,
            "_fetch_unequip_data",
            new=AsyncMock(return_value=(mock_dweller, "st-1", ItemTypeEnum.WEAPON)),
        ),
        patch.object(crud, "_update_item", new=AsyncMock()) as mock_item,
        patch.object(crud, "_update_dweller", new=AsyncMock()) as mock_dweller_patch,
    ):
        await crud.unequip(db_session=session, item_id="w-1")

    mock_item.assert_called_once_with(session, Weapon, "w-1", "st-1")
    mock_dweller_patch.assert_called_once_with(session, mock_dweller, ItemTypeEnum.WEAPON)
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_unequip_not_found() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)

    with (
        patch.object(crud, "_fetch_unequip_data", new=AsyncMock(return_value=(None, None, None))),
        pytest.raises(ResourceNotFoundException) as exc,
    ):
        await crud.unequip(db_session=session, item_id="orphan")
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

    @patch("app.crud.item_base.random.choice")
    @patch("app.crud.item_base.random.random")
    def test_legendary_no_extra_prob(self, mock_random: MagicMock, mock_choice: MagicMock) -> None:
        mock_choice.side_effect = [JunkTypeEnum.CLOTH, JunkTypeEnum.CIRCUITRY, JunkTypeEnum.LEATHER]
        mock_random.return_value = 0.9

        item = _make_mock_item(Weapon, rarity=RarityEnum.LEGENDARY)
        results = CRUDItem.convert_to_junk(item)
        assert len(results) == 1
        assert results[0].rarity == RarityEnum.LEGENDARY

    @patch("app.crud.item_base.random.choice")
    @patch("app.crud.item_base.random.random")
    def test_rare_with_extra_prob(self, mock_random: MagicMock, mock_choice: MagicMock) -> None:
        mock_choice.side_effect = [JunkTypeEnum.LEATHER, JunkTypeEnum.STEEL, JunkTypeEnum.ADHESIVE]
        mock_random.return_value = 0.1

        item = _make_mock_item(Outfit, rarity=RarityEnum.RARE)
        results = CRUDItem.convert_to_junk(item)

        assert results[0].rarity == RarityEnum.RARE
        assert any(j.rarity == RarityEnum.COMMON for j in results[1:])

    @patch("app.crud.item_base.random.choice")
    @patch("app.crud.item_base.random.random")
    def test_rare_no_extra_prob(self, mock_random: MagicMock, mock_choice: MagicMock) -> None:
        mock_choice.side_effect = [JunkTypeEnum.SCIENCE, JunkTypeEnum.CLOTH, JunkTypeEnum.VALUABLES]
        mock_random.return_value = 0.9

        item = _make_mock_item(Outfit, rarity=RarityEnum.RARE)
        results = CRUDItem.convert_to_junk(item)
        assert len(results) == 1
        assert results[0].rarity == RarityEnum.RARE

    @patch("app.crud.item_base.random.choice")
    @patch("app.crud.item_base.random.random")
    def test_common_with_extra_prob(self, mock_random: MagicMock, mock_choice: MagicMock) -> None:
        mock_choice.side_effect = [JunkTypeEnum.ADHESIVE, JunkTypeEnum.STEEL, JunkTypeEnum.LEATHER]
        mock_random.return_value = 0.1  # below 0.6

        item = _make_mock_item(Weapon, rarity=RarityEnum.COMMON)
        results = CRUDItem.convert_to_junk(item)

        assert results[0].rarity == RarityEnum.COMMON

    @patch("app.crud.item_base.random.choice")
    @patch("app.crud.item_base.random.random")
    def test_common_no_extra_prob(self, mock_random: MagicMock, mock_choice: MagicMock) -> None:
        mock_choice.side_effect = [JunkTypeEnum.CIRCUITRY, JunkTypeEnum.VALUABLES, JunkTypeEnum.CLOTH]
        mock_random.return_value = 0.9

        item = _make_mock_item(Weapon, rarity=RarityEnum.COMMON)
        results = CRUDItem.convert_to_junk(item)
        assert len(results) == 1
        assert results[0].rarity == RarityEnum.COMMON

    def test_unsupported_rarity_raises(self) -> None:
        item = _make_mock_item(Weapon, rarity="mythic")
        with pytest.raises(ValueError, match="not supported"):
            CRUDItem.convert_to_junk(item)

    @patch("app.crud.item_base.random.choice")
    @patch("app.crud.item_base.random.random")
    def test_junk_values_from_config(self, mock_random: MagicMock, mock_choice: MagicMock) -> None:
        mock_choice.side_effect = [JunkTypeEnum.CIRCUITRY, JunkTypeEnum.LEATHER, JunkTypeEnum.ADHESIVE]
        mock_random.return_value = 0.9

        item = _make_mock_item(Weapon, rarity=RarityEnum.LEGENDARY)
        results = CRUDItem.convert_to_junk(item)
        # game_config.exploration.get_junk_value("legendary") = 200
        assert results[0].value == 200

    @patch("app.crud.item_base.random.choice")
    @patch("app.crud.item_base.random.random")
    def test_common_no_duplicate_same_type(self, mock_random: MagicMock, mock_choice: MagicMock) -> None:
        """When the random choice for same_rarity happens to match, no duplicate."""
        mock_choice.side_effect = [JunkTypeEnum.ADHESIVE, JunkTypeEnum.STEEL, JunkTypeEnum.LEATHER]
        mock_random.return_value = 0.9

        item = _make_mock_item(Weapon, rarity=RarityEnum.COMMON)
        results = CRUDItem.convert_to_junk(item)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# scrap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scrap_success() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    item = _make_mock_item(Weapon, item_id="w-scrap", storage_id="st-1")
    session.get = AsyncMock(return_value=item)

    with patch.object(crud, "convert_to_junk", return_value=[MagicMock(spec=Junk)]) as mock_cvt:
        results = await crud.scrap(db_session=session, item_id="w-scrap")

    session.get.assert_called_once_with(Weapon, "w-scrap")
    mock_cvt.assert_called_once_with(item)
    session.delete.assert_called_once_with(item)
    session.commit.assert_called_once()
    assert len(results) == 1


@pytest.mark.asyncio
async def test_scrap_not_found() -> None:
    session = _new_session()
    crud = CRUDItem(Outfit)
    session.get = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundException) as exc:
        await crud.scrap(db_session=session, item_id="missing")
    assert "Outfit" in exc.value.detail


@pytest.mark.asyncio
async def test_scrap_no_storage_id() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    item = _make_mock_item(Weapon, item_id="w-nostore", storage_id=None, dweller_id="d1")
    session.get = AsyncMock(return_value=item)

    with patch.object(crud, "convert_to_junk", return_value=[MagicMock(spec=Junk)]) as mock_cvt:
        results = await crud.scrap(db_session=session, item_id="w-nostore")

    mock_cvt.assert_called_once_with(item)
    session.delete.assert_called_once_with(item)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# add_caps_to_vault
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_caps_to_vault_success() -> None:
    session = _new_session()
    mock_vault = MagicMock(spec=Vault, id="v-1")
    session.get = AsyncMock(return_value=mock_vault)

    with patch("app.crud.item_base.vault_crud.deposit_caps", new=AsyncMock()) as mock_deposit:
        await CRUDItem.add_caps_to_vault(session, "v-1", 500)

    session.get.assert_called_once_with(Vault, "v-1")
    mock_deposit.assert_called_once_with(db_session=session, vault_obj=mock_vault, amount=500)
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_add_caps_to_vault_no_commit() -> None:
    session = _new_session()
    mock_vault = MagicMock(spec=Vault)
    session.get = AsyncMock(return_value=mock_vault)

    with patch("app.crud.item_base.vault_crud.deposit_caps", new=AsyncMock()):
        await CRUDItem.add_caps_to_vault(session, "v-1", 100, commit=False)

    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_add_caps_to_vault_vault_not_found() -> None:
    session = _new_session()
    session.get = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundException) as exc:
        await CRUDItem.add_caps_to_vault(session, "bad", 100)
    assert "Vault" in exc.value.detail


# ---------------------------------------------------------------------------
# sell
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sell_from_storage() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    item = _make_mock_item(Weapon, item_id="w-sell", storage_id="st-1", value=50, dweller_id=None)
    session.get = AsyncMock(return_value=item)

    # sell does session.execute → scalar_one_or_none for storage query
    _setup_execute_scalar_one_or_none(session, "v-1")

    with patch.object(crud, "add_caps_to_vault", new=AsyncMock()) as mock_add:
        await crud.sell(session, item_id="w-sell")

    mock_add.assert_called_once_with(session, "v-1", 50, commit=False)
    session.delete.assert_called_once_with(item)
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sell_from_dweller() -> None:
    session = _new_session()
    crud = CRUDItem(Outfit)
    item = _make_mock_item(Outfit, item_id="o-sell", dweller_id="d-1", storage_id=None, value=75)
    session.get = AsyncMock(return_value=item)

    _setup_execute_scalar_one_or_none(session, "v-2")

    with patch.object(crud, "add_caps_to_vault", new=AsyncMock()) as mock_add:
        await crud.sell(session, item_id="o-sell")

    mock_add.assert_called_once_with(session, "v-2", 75, commit=False)
    session.delete.assert_called_once_with(item)
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sell_item_not_found() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    session.get = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundException) as exc:
        await crud.sell(session, item_id="nonexistent")
    assert "Weapon" in exc.value.detail


@pytest.mark.asyncio
async def test_sell_no_vault_raises() -> None:
    session = _new_session()
    crud = CRUDItem(Weapon)
    item = _make_mock_item(Weapon, item_id="w-orphan", storage_id=None, dweller_id=None)
    session.get = AsyncMock(return_value=item)

    with pytest.raises(ResourceNotFoundException) as exc:
        await crud.sell(session, item_id="w-orphan")
    assert "Vault" in exc.value.detail


@pytest.mark.asyncio
async def test_sell_rollback_on_sqlalchemy_error() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    session = _new_session()
    crud = CRUDItem(Weapon)
    item = _make_mock_item(Weapon, item_id="w-err", storage_id="st-1", value=10)
    session.get = AsyncMock(return_value=item)
    _setup_execute_scalar_one_or_none(session, "v-1")

    with (
        patch.object(crud, "add_caps_to_vault", new=AsyncMock(side_effect=SQLAlchemyError)),
        pytest.raises(SQLAlchemyError),
    ):
        await crud.sell(session, item_id="w-err")

    session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# Inheritance / init smoke tests
# ---------------------------------------------------------------------------


def test_initialization() -> None:
    assert CRUDItem(Weapon).model is Weapon
    assert CRUDItem(Outfit).model is Outfit


def test_inherits_crud_base() -> None:
    from app.crud.base import CRUDBase

    assert issubclass(CRUDItem, CRUDBase)
    crud = CRUDItem(Weapon)
    for method in ("get", "get_multi", "delete", "exists"):
        assert hasattr(crud, method)
