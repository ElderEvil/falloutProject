"""Tests for app.services.item_service — the canonical item-sell flow.

Uses AsyncMock to avoid hitting a real database.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.outfit import Outfit
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.services.item_service import item_service
from app.utils.exceptions import ResourceNotFoundException


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
    m.value = 10
    m.storage_id = None
    m.dweller_id = None
    for key, val in overrides.items():
        setattr(m, key, val)
    return m


def _new_session() -> MagicMock:
    """Create a base session mock with commit/refresh/delete/rollback as AsyncMock."""
    s = MagicMock()
    s.commit = AsyncMock()
    s.refresh = AsyncMock()
    s.delete = AsyncMock()
    s.rollback = AsyncMock()
    s.get = AsyncMock()
    return s


@pytest.mark.asyncio
async def test_sell_item_not_found() -> None:
    session = _new_session()
    session.get = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundException) as exc:
        await item_service.sell_item(session, item_id="missing", model=Weapon)
    assert "Weapon" in exc.value.detail


@pytest.mark.asyncio
async def test_sell_from_storage() -> None:
    session = _new_session()
    item = _make_mock_item(Weapon, item_id="w-sell", storage_id="st-1", value=75)
    session.get = AsyncMock(return_value=item)
    _setup_execute_scalar_one_or_none(session, "v-2")

    with patch.object(item_service, "_credit_caps", new=AsyncMock()) as mock_credit:
        await item_service.sell_item(session, item_id="w-sell", model=Weapon)

    mock_credit.assert_called_once_with(session, "v-2", 75)
    session.delete.assert_called_once_with(item)
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sell_from_dweller() -> None:
    session = _new_session()
    item = _make_mock_item(Outfit, item_id="o-sell", dweller_id="d-1", storage_id=None, value=75)
    session.get = AsyncMock(return_value=item)
    _setup_execute_scalar_one_or_none(session, "v-2")

    with patch.object(item_service, "_credit_caps", new=AsyncMock()) as mock_credit:
        await item_service.sell_item(session, item_id="o-sell", model=Outfit)

    mock_credit.assert_called_once_with(session, "v-2", 75)
    session.delete.assert_called_once_with(item)
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sell_no_vault_raises() -> None:
    session = _new_session()
    item = _make_mock_item(Weapon, item_id="w-orphan", storage_id=None, dweller_id=None)
    session.get = AsyncMock(return_value=item)

    with pytest.raises(ResourceNotFoundException) as exc:
        await item_service.sell_item(session, item_id="w-orphan", model=Weapon)
    assert "Vault" in exc.value.detail


@pytest.mark.asyncio
async def test_sell_rollback_on_sqlalchemy_error() -> None:
    session = _new_session()
    item = _make_mock_item(Weapon, item_id="w-err", storage_id="st-1", value=10)
    session.get = AsyncMock(return_value=item)
    _setup_execute_scalar_one_or_none(session, "v-1")

    with (
        patch.object(item_service, "_credit_caps", new=AsyncMock(side_effect=SQLAlchemyError)),
        pytest.raises(SQLAlchemyError),
    ):
        await item_service.sell_item(session, item_id="w-err", model=Weapon)

    session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_credit_caps_deposits_via_vault_service_without_commit() -> None:
    session = _new_session()
    mock_vault = MagicMock(spec=Vault, id="v-1")
    session.get = AsyncMock(return_value=mock_vault)

    with patch("app.services.item_service.vault_service.deposit_caps", new=AsyncMock()) as mock_deposit:
        await item_service._credit_caps(session, "v-1", 500)

    session.get.assert_called_once_with(Vault, "v-1")
    mock_deposit.assert_called_once_with(db_session=session, vault_obj=mock_vault, amount=500, commit=False)
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_credit_caps_vault_not_found() -> None:
    session = _new_session()
    session.get = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundException) as exc:
        await item_service._credit_caps(session, "bad", 100)
    assert "Vault" in exc.value.detail
