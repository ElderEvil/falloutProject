"""Settlement of expedition-held equipment at return (issue #765 workstream 3).

Held rows (Weapon/Outfit with ``exploration_id`` set, no storage/dweller) and
ordinary loot share ONE rarity-first capacity budget at finalization. Entries
already equipped mid-run (``equipped`` truthy) are skipped entirely.
"""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, orm
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ExplorationStatus, RarityEnum
from app.core.event_bus import GameEvent
from app.crud import storage as crud_storage
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.rewards_calculator import rewards_calculator
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.services.leveling_service import LevelingService
from app.tests.factory.items import create_fake_outfit, create_fake_weapon
from app.utils.time import utcnow


def _level_up_events(emit: AsyncMock, vault_id) -> list:
    """Emitted DWELLER_LEVEL_UP calls for one vault."""
    return [
        call
        for call in emit.await_args_list
        if call.args and call.args[0] == GameEvent.DWELLER_LEVEL_UP and call.args[1] == vault_id
    ]


def _junk_payloads(emit: AsyncMock) -> list[dict]:
    """ITEM_COLLECTED payloads for junk from a patched emit."""
    return [
        call.args[2]
        for call in emit.await_args_list
        if call.args and call.args[0] == GameEvent.ITEM_COLLECTED and call.args[2].get("item_type") == "junk"
    ]


@pytest_asyncio.fixture
async def make_vault_storage(async_session: AsyncSession, vault: Vault) -> Callable[[int], Awaitable[Storage]]:
    """Factory for the test vault's storage, emptied and sized via max_space."""
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault.id))
    storage = result.scalar_one_or_none() or await vault_crud.create_storage(
        db_session=async_session, vault_id=vault.id
    )

    async def _make(max_space: int = 10) -> Storage:
        storage.max_space = max_space
        storage.used_space = 0
        async_session.add(storage)
        await async_session.flush()
        return storage

    return _make


async def _expired_exploration(async_session: AsyncSession, vault: Vault, dweller: Dweller, duration: int = 4):
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=duration)
    exploration.start_time = utcnow() - timedelta(hours=duration)
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
    exploration.return_completes_at = utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    return exploration


async def _create_held_weapon(
    async_session: AsyncSession, dweller: Dweller, exploration_id, *, rarity: RarityEnum = RarityEnum.COMMON
) -> Weapon:
    """A weapon row held by the exploration (displaced by a mid-run upgrade)."""
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
    """An outfit row held by the exploration (displaced by a mid-run upgrade)."""
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


def _flaky_update_used_space(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    """Fail the first storage-space update, then behave normally on the retry."""
    calls = {"count": 0}
    original = crud_storage.update_used_space

    async def flaky(db_session, storage_id):
        calls["count"] += 1
        if calls["count"] == 1:
            raise exc
        return await original(db_session, storage_id)

    monkeypatch.setattr(crud_storage, "update_used_space", flaky)


async def _stored_weapons(async_session: AsyncSession, storage_id) -> list[str]:
    rows = (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage_id))).scalars().all()
    return [weapon.name for weapon in rows]


@pytest.mark.parametrize("recalled", [False, True])
async def test_free_space_settles_held_row_and_skips_equipped_entry(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage, recalled: bool
) -> None:
    storage = await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller, recalled=recalled)
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
    assert await _stored_weapons(async_session, storage.id) == [held.name]
    assert not any(call.args[0] == GameEvent.ITEM_COLLECTED for call in emit.await_args_list)
    await async_session.refresh(storage)
    assert storage.used_space == 1
    await _assert_no_orphan_rows(async_session)


async def test_tight_space_splits_held_and_loot_once(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    # Held rows and loot share one rarity-first budget; overflow holds the excess once.
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
    assert await _stored_weapons(async_session, storage.id) == ["Fire hydrant bat"]
    await _assert_no_orphan_rows(async_session)


async def test_no_orphan_rows_after_settlement(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    await _create_held_weapon(async_session, dweller, exploration.id)
    await _create_held_outfit(async_session, dweller, exploration.id)
    exploration.add_loot(item_name="Fire hydrant bat", quantity=1, rarity="Legendary", item_type="weapon")
    async_session.add(exploration)
    await async_session.commit()
    await exploration_coordinator.finalize_return(async_session, exploration.id)
    await _assert_no_orphan_rows(async_session)


async def test_failed_settlement_keeps_run_returning_and_held_rows_intact(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage = await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    exploration.location_xp = 120
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(dweller)
    experience_before = dweller.experience
    level_before = dweller.level
    xp_award = rewards_calculator.calculate_exploration_xp(exploration, dweller)
    held = await _create_held_weapon(async_session, dweller, exploration.id)
    _flaky_update_used_space(monkeypatch, RuntimeError("storage update exploded"))
    with pytest.raises(RuntimeError, match="storage update exploded"):
        await exploration_coordinator.finalize_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(held)
    await async_session.refresh(dweller)
    assert exploration.status == ExplorationStatus.RETURNING
    assert exploration.location_xp == 120
    assert dweller.experience == experience_before
    assert dweller.level == level_before
    assert held.exploration_id == exploration.id
    assert held.storage_id is None
    assert held.dweller_id is None
    await exploration_coordinator.finalize_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    await async_session.refresh(held)
    await async_session.refresh(dweller)
    assert exploration.status == ExplorationStatus.COMPLETED
    assert dweller.experience == experience_before + xp_award
    assert held.storage_id == storage.id
    assert held.exploration_id is None
    await _assert_no_orphan_rows(async_session)


async def test_failed_settlement_discards_level_up_and_retry_delivers_once(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_id = vault.id
    await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    exploration_id = exploration.id
    exploration.location_xp = 500
    async_session.add(exploration)
    await async_session.refresh(dweller)
    dweller.experience = LevelingService.calculate_xp_required(dweller.level + 1) - 1
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    level_before = dweller.level
    await _create_held_weapon(async_session, dweller, exploration.id)
    _flaky_update_used_space(monkeypatch, IntegrityError("UPDATE storage", {}, RuntimeError("storage write failed")))
    with (
        patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(
            "app.services.notification_service.NotificationService.notify_level_up", new_callable=AsyncMock
        ) as notify,
        pytest.raises(IntegrityError),
    ):
        await exploration_coordinator.finalize_return(async_session, exploration_id)
    assert _level_up_events(emit, vault_id) == []
    notify.assert_not_awaited()
    await async_session.refresh(dweller)
    assert dweller.level == level_before
    with (
        patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
        patch(
            "app.services.notification_service.NotificationService.notify_level_up", new_callable=AsyncMock
        ) as notify,
    ):
        await exploration_coordinator.finalize_return(async_session, exploration_id)
    assert len(_level_up_events(emit, vault_id)) == 1
    notify.assert_awaited_once()


async def test_legacy_auto_equip_entry_settles_into_storage(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    # A legacy auto_equip flag without an equipped marker settles the item normally.
    storage = await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    exploration.add_loot(item_name="Fire hydrant bat", quantity=1, rarity="Legendary", item_type="weapon")
    exploration.loot_collected[-1]["auto_equip"] = True
    orm.attributes.flag_modified(exploration, "loot_collected")
    async_session.add(exploration)
    await async_session.commit()
    await exploration_coordinator.finalize_return(async_session, exploration.id)
    assert await _stored_weapons(async_session, storage.id) == ["Fire hydrant bat"]
    await _assert_no_orphan_rows(async_session)


async def test_no_storage_holds_everything_including_held_rows(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
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


async def test_junk_settlement_credits_each_material_once(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    for name, rarity in (
        ("Duct tape", "Common"),
        ("Wonderglue", "Rare"),
        ("Alarm clock", "Common"),
        ("Mystery scrap", "Common"),
    ):
        exploration.add_loot(item_name=name, rarity=rarity, item_type="junk")
    async_session.add(exploration)
    await async_session.commit()
    with patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit:
        await exploration_coordinator.finalize_return(async_session, exploration.id)
    by_material = {payload.get("junk_type"): payload for payload in _junk_payloads(emit)}
    assert by_material["adhesive"]["amount"] == 2  # Duct tape + Wonderglue share the catalog type
    assert by_material["circuitry"]["amount"] == 1
    assert by_material[None]["amount"] == 1  # unknown legacy name keeps generic junk credit
    assert all(payload["source"] == "wasteland" for payload in by_material.values())


async def test_failed_settlement_discards_queued_junk_credit(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    storage = await make_vault_storage(10)
    exploration = await _returning_exploration(async_session, vault, dweller)
    exploration.add_loot(item_name="Duct tape", rarity="Common", item_type="junk")
    async_session.add(exploration)
    await async_session.commit()

    def fail_commit(_session):
        raise IntegrityError("COMMIT", {}, RuntimeError("storage write failed"))

    event.listen(async_session.sync_session, "before_commit", fail_commit)
    try:
        with (
            patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit,
            pytest.raises(IntegrityError),
        ):
            await exploration_coordinator.finalize_return(async_session, exploration.id)
    finally:
        event.remove(async_session.sync_session, "before_commit", fail_commit)
    assert _junk_payloads(emit) == []
    await async_session.refresh(exploration)
    await async_session.refresh(storage)
    assert exploration.status == ExplorationStatus.RETURNING
    assert storage.used_space == 0
    with patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit:
        await exploration_coordinator.finalize_return(async_session, exploration.id)
    credit = _junk_payloads(emit)
    assert len(credit) == 1
    assert (credit[0]["junk_type"], credit[0]["amount"], credit[0]["source"]) == ("adhesive", 1, "wasteland")


async def test_overflow_junk_credits_its_material_when_taken(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    storage = await make_vault_storage(1)
    exploration = await _returning_exploration(async_session, vault, dweller)
    exploration.add_loot(item_name="Duct tape", rarity="Common", item_type="junk")
    exploration.add_loot(item_name="Wonderglue", rarity="Rare", item_type="junk")
    async_session.add(exploration)
    await async_session.commit()
    with patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit:
        await exploration_coordinator.finalize_return(async_session, exploration.id)
    first_credits = _junk_payloads(emit)
    await async_session.refresh(exploration)
    assert len(exploration.unclaimed_loot) == 1
    storage.max_space = 5
    async_session.add(storage)
    await async_session.commit()
    with patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit:
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)
    taken_credits = _junk_payloads(emit)
    assert len(first_credits) == 1
    assert len(taken_credits) == 1
    assert (taken_credits[0]["junk_type"], taken_credits[0]["amount"]) == ("adhesive", 1)
    assert first_credits[0]["amount"] + taken_credits[0]["amount"] == 2  # each stored unit credits once
