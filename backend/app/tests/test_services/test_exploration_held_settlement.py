"""Settlement of expedition-held equipment at return (issue #765 workstream 3).

Held rows (Weapon/Outfit with ``exploration_id`` set, no storage/dweller) and
ordinary loot share ONE rarity-first capacity budget at finalization. Entries
already equipped mid-run (``equipped`` truthy) are skipped entirely. Fixtures
build held rows directly through ``CRUDItem.equip(..., held_exploration_id=...)``
so they do not depend on the mid-run equip workstream.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import orm
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import RarityEnum
from app.core.event_bus import GameEvent
from app.crud import storage as crud_storage
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.outfit import Outfit
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration_service import exploration_service
from app.tests.factory.items import create_fake_outfit, create_fake_weapon


async def _ensure_vault_storage(async_session: AsyncSession, vault_id) -> Storage:
    """Ensure storage exists for a vault, create if missing."""
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault_id))
    storage = result.scalar_one_or_none()
    if storage is None:
        storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault_id)
    return storage


@pytest_asyncio.fixture
async def make_vault_storage(async_session: AsyncSession, vault: Vault) -> Callable[[int], Awaitable[Storage]]:
    """Factory for the test vault's storage, emptied and sized via max_space."""

    async def _make(max_space: int = 10) -> Storage:
        storage = await _ensure_vault_storage(async_session, vault.id)
        storage.max_space = max_space
        storage.used_space = 0
        async_session.add(storage)
        await async_session.flush()
        return storage

    return _make


async def _expired_exploration(async_session: AsyncSession, vault: Vault, dweller: Dweller, duration: int = 4):
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=duration)
    exploration.start_time = datetime.utcnow() - timedelta(hours=duration)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    return exploration


async def _returning_exploration(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, *, recalled: bool = False, duration: int = 4
):
    """An exploration on the return leg that has already arrived home."""
    exploration = await _expired_exploration(async_session, vault, dweller, duration=duration)
    await exploration_coordinator.start_return(async_session, exploration.id, recalled=recalled)
    await async_session.refresh(exploration)
    exploration.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    return exploration


async def _create_held_weapon(
    async_session: AsyncSession, dweller: Dweller, exploration_id, *, rarity: RarityEnum = RarityEnum.COMMON
) -> Weapon:
    """Create a weapon row held by the exploration (displaced by a mid-run upgrade)."""
    data = create_fake_weapon()
    data["rarity"] = rarity
    old = await crud.weapon.create(async_session, obj_in=data)
    new = await crud.weapon.create(async_session, obj_in=create_fake_weapon())
    await crud.weapon.equip(db_session=async_session, item_id=old.id, dweller_id=dweller.id)
    await crud.weapon.equip(
        db_session=async_session, item_id=new.id, dweller_id=dweller.id, held_exploration_id=exploration_id
    )
    return old


async def _create_held_outfit(
    async_session: AsyncSession, dweller: Dweller, exploration_id, *, rarity: RarityEnum = RarityEnum.COMMON
) -> Outfit:
    """Create an outfit row held by the exploration (displaced by a mid-run upgrade)."""
    data = create_fake_outfit()
    data["rarity"] = rarity
    old = await crud.outfit.create(async_session, obj_in=data)
    new = await crud.outfit.create(async_session, obj_in=create_fake_outfit())
    await crud.outfit.equip(db_session=async_session, item_id=old.id, dweller_id=dweller.id)
    await crud.outfit.equip(
        db_session=async_session, item_id=new.id, dweller_id=dweller.id, held_exploration_id=exploration_id
    )
    return old


async def _assert_no_orphan_rows(async_session: AsyncSession) -> None:
    """No row may sit in the unassigned/unheld limbo state after settlement."""
    for model in (Weapon, Outfit):
        orphans = (
            (
                await async_session.execute(
                    select(model).where(
                        model.storage_id.is_(None),
                        model.dweller_id.is_(None),
                        model.exploration_id.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert orphans == []


@pytest.mark.asyncio
async def test_free_space_settles_held_row_and_skips_equipped_entry(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """A held row moves into storage; an already-equipped loot entry creates nothing."""
    storage = await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    held = await _create_held_weapon(async_session, dweller, exploration.id)

    exploration.add_loot(item_name="Fire hydrant bat", quantity=1, rarity="Legendary", item_type="weapon")
    exploration.loot_collected[-1]["equipped"] = True
    exploration.loot_collected[-1]["equipped_item_id"] = str(uuid4())
    orm.attributes.flag_modified(exploration, "loot_collected")
    async_session.add(exploration)
    await async_session.commit()

    with patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit:
        await exploration_coordinator.finalize_return(async_session, exploration.id)

    await async_session.refresh(held)
    assert held.storage_id == storage.id
    assert held.exploration_id is None
    assert held.dweller_id is None

    stored_weapons = (
        (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))).scalars().all()
    )
    assert [w.name for w in stored_weapons] == [held.name]
    assert not any(call.args[0] == GameEvent.ITEM_COLLECTED for call in emit.await_args_list)

    await async_session.refresh(storage)
    assert storage.used_space == 1
    await _assert_no_orphan_rows(async_session)


@pytest.mark.asyncio
async def test_tight_space_splits_held_and_loot_once(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Held rows and loot share one rarity-first budget; overflow holds the excess once."""
    storage = await make_vault_storage(1)
    exploration = await _returning_exploration(async_session, vault, dweller)
    held = await _create_held_weapon(async_session, dweller, exploration.id, rarity=RarityEnum.COMMON)

    exploration.add_loot(item_name="Fire hydrant bat", quantity=1, rarity="Legendary", item_type="weapon")
    async_session.add(exploration)
    await async_session.commit()

    await exploration_coordinator.finalize_return(async_session, exploration.id)

    await async_session.refresh(exploration)
    assert [entry["item_name"] for entry in exploration.unclaimed_loot] == [held.name]
    assert "held_row_id" not in exploration.unclaimed_loot[0]
    assert "held_model" not in exploration.unclaimed_loot[0]

    assert await crud.weapon.get_or_none(async_session, held.id) is None
    assert await crud.weapon.get_held_for_exploration(async_session, exploration.id) == []
    assert await crud.outfit.get_held_for_exploration(async_session, exploration.id) == []

    stored_weapons = (
        (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))).scalars().all()
    )
    assert [w.name for w in stored_weapons] == ["Fire hydrant bat"]
    await _assert_no_orphan_rows(async_session)


@pytest.mark.asyncio
async def test_no_orphan_rows_after_settlement(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Settling held rows plus loot leaves no row in the unassigned/unheld limbo state."""
    await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    await _create_held_weapon(async_session, dweller, exploration.id)
    await _create_held_outfit(async_session, dweller, exploration.id)
    exploration.add_loot(item_name="Fire hydrant bat", quantity=1, rarity="Legendary", item_type="weapon")
    async_session.add(exploration)
    await async_session.commit()

    await exploration_coordinator.finalize_return(async_session, exploration.id)

    await _assert_no_orphan_rows(async_session)


@pytest.mark.asyncio
async def test_failed_settlement_keeps_run_returning_and_held_rows_intact(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
    monkeypatch: pytest.MonkeyPatch,
):
    """A failure after the held move rolls back; a retry then settles exactly once."""
    storage = await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    held = await _create_held_weapon(async_session, dweller, exploration.id)

    calls = {"count": 0}
    original = crud_storage.update_used_space

    async def flaky(db_session, storage_id):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("storage update exploded")
        return await original(db_session, storage_id)

    monkeypatch.setattr(crud_storage, "update_used_space", flaky)

    with pytest.raises(RuntimeError, match="storage update exploded"):
        await exploration_coordinator.finalize_return(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(held)
    assert exploration.status == ExplorationStatus.RETURNING
    assert held.exploration_id == exploration.id
    assert held.storage_id is None
    assert held.dweller_id is None

    await exploration_coordinator.finalize_return(async_session, exploration.id)

    await async_session.refresh(exploration)
    await async_session.refresh(held)
    assert exploration.status == ExplorationStatus.COMPLETED
    assert held.storage_id == storage.id
    assert held.exploration_id is None
    await _assert_no_orphan_rows(async_session)


@pytest.mark.asyncio
async def test_recall_settles_held_rows_like_natural_completion(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """An early recall settles held rows into storage exactly like a natural finish."""
    storage = await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller, recalled=True)
    held = await _create_held_weapon(async_session, dweller, exploration.id)

    await exploration_coordinator.finalize_return(async_session, exploration.id)

    await async_session.refresh(held)
    assert held.storage_id == storage.id
    assert held.exploration_id is None
    await _assert_no_orphan_rows(async_session)


@pytest.mark.asyncio
async def test_legacy_auto_equip_entry_settles_into_storage(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """A legacy auto_equip flag without an equipped marker settles the item normally."""
    storage = await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    exploration.add_loot(item_name="Fire hydrant bat", quantity=1, rarity="Legendary", item_type="weapon")
    exploration.loot_collected[-1]["auto_equip"] = True
    orm.attributes.flag_modified(exploration, "loot_collected")
    async_session.add(exploration)
    await async_session.commit()

    await exploration_coordinator.finalize_return(async_session, exploration.id)

    stored_weapons = (
        (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))).scalars().all()
    )
    assert [w.name for w in stored_weapons] == ["Fire hydrant bat"]
    await _assert_no_orphan_rows(async_session)


@pytest.mark.asyncio
async def test_no_storage_holds_everything_including_held_rows(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Without a storage row every candidate lands in unclaimed_loot; held rows are deleted."""
    exploration = await _returning_exploration(async_session, vault, dweller)
    held = await _create_held_weapon(async_session, dweller, exploration.id)
    exploration.add_loot(item_name="Fire hydrant bat", quantity=1, rarity="Legendary", item_type="weapon")
    async_session.add(exploration)
    await async_session.commit()

    await exploration_coordinator.finalize_return(async_session, exploration.id)

    await async_session.refresh(exploration)
    assert [entry["item_name"] for entry in exploration.unclaimed_loot] == ["Fire hydrant bat", held.name]
    assert all("held_row_id" not in entry for entry in exploration.unclaimed_loot)
    assert await crud.weapon.get_or_none(async_session, held.id) is None
    await _assert_no_orphan_rows(async_session)
