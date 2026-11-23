from collections.abc import Awaitable, Callable
from datetime import timedelta

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud import storage as crud_storage
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.services.loot_overflow_service import loot_overflow_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException
from app.utils.time import utcnow


def _loot(name: str, quantity: int = 1, rarity: str = "Common", item_type: str = "junk") -> dict:
    return {"item_name": name, "quantity": quantity, "rarity": rarity, "item_type": item_type}


RELICS = _loot("Nonexistent Relic", 1, item_type="weapon")
TWO_ITEMS = [_loot("Item A", 1), _loot("Item B", 1)]


async def _ensure_vault_storage(async_session: AsyncSession, vault_id) -> Storage:
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault_id))
    storage = result.scalar_one_or_none()
    return storage or await vault_crud.create_storage(db_session=async_session, vault_id=vault_id)


@pytest_asyncio.fixture
async def make_vault_storage(async_session: AsyncSession, vault: Vault) -> Callable[[int], Awaitable[Storage]]:
    """Factory for the test vault's storage, emptied and sized via max_space."""

    async def _make(max_space: int = 10) -> Storage:
        storage = await _ensure_vault_storage(async_session, vault.id)
        storage.max_space, storage.used_space = max_space, 0
        async_session.add(storage)
        await async_session.flush()
        return storage

    return _make


async def _completed_with_overflow(async_session, vault, dweller, loots=None):
    """Complete an exploration that overflows; returns (exploration, rewards)."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.start_time = utcnow() - timedelta(hours=exploration.duration)
    for loot in loots or []:
        exploration.add_loot(**loot)
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)
    await exploration_coordinator.start_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    exploration.return_completes_at = utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()
    rewards = await exploration_coordinator.finalize_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    return exploration, rewards


async def _wide_storage(async_session, storage, max_space: int) -> None:
    storage.max_space = max_space
    async_session.add(storage)
    await async_session.flush()


@pytest.mark.asyncio
async def test_pending_overflow_is_available_after_returning_to_exploration(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
):
    await make_vault_storage(1)
    exploration, _ = await _completed_with_overflow(async_session, vault, dweller, loots=TWO_ITEMS)

    pending = await rewards_service.get_pending_overflow(async_session, vault.id)

    assert [(entry.exploration_id, entry.unclaimed_loot) for entry in pending] == [
        (exploration.id, exploration.unclaimed_loot)
    ]


@pytest.mark.asyncio
async def test_take_unclaimed_item_stacks_units_but_conflicts_when_full(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
):
    storage = await make_vault_storage(1)
    exploration, _ = await _completed_with_overflow(
        async_session, vault, dweller, loots=[_loot("Item A", 1), _loot("Item B", 2)]
    )

    with pytest.raises(ResourceConflictException):
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)
    await async_session.refresh(exploration)
    assert len(exploration.unclaimed_loot or []) == 1

    await _wide_storage(async_session, storage, 3)
    remaining = await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)

    assert remaining == []
    stored = (await async_session.execute(select(Junk).where(Junk.storage_id == storage.id))).scalars().all()
    assert [item.name for item in stored].count("Item B") == 2


@pytest.mark.asyncio
async def test_sell_unclaimed_item_grants_caps_without_space(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
):
    await make_vault_storage(1)
    await async_session.refresh(vault)
    caps_before = vault.bottle_caps
    exploration, _ = await _completed_with_overflow(
        async_session, vault, dweller, loots=[_loot("Item A", 1), _loot("Item B", 2)]
    )

    caps, remaining = await rewards_service.sell_unclaimed_item(async_session, exploration.id, 0)

    assert caps == game_config.exploration.junk_value_common * 2
    assert remaining == []
    await async_session.refresh(vault)
    assert vault.bottle_caps > caps_before


@pytest.mark.asyncio
async def test_unclaimed_rejects_bad_index_and_active_exploration(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
):
    await make_vault_storage(1)
    exploration, _ = await _completed_with_overflow(async_session, vault, dweller, loots=TWO_ITEMS)

    with pytest.raises(ResourceNotFoundException):
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 5)

    active = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    with pytest.raises(ValidationException):
        await rewards_service.sell_unclaimed_item(async_session, active.id, 0)


@pytest.mark.asyncio
async def test_require_space_locks_the_shared_storage_row(
    async_session: AsyncSession, vault: Vault, make_vault_storage, monkeypatch: pytest.MonkeyPatch
):
    """Two claims must not both read the same free slot, so the check takes a row lock."""
    await make_vault_storage(5)
    locked_vaults: list = []
    original = crud_storage.get_storage_by_vault_for_update

    async def spy(db_session, vault_id):
        locked_vaults.append(vault_id)
        return await original(db_session, vault_id)

    monkeypatch.setattr(crud_storage, "get_storage_by_vault_for_update", spy)

    assert await loot_overflow_service.require_space(async_session, vault.id, 1) is not None
    assert locked_vaults == [vault.id]


@pytest.mark.parametrize("starting_caps", [0, 999_998, 999_999])
async def test_overflow_sale_emits_only_committed_caps(
    async_session, vault, dweller, make_vault_storage, starting_caps
):
    await make_vault_storage(1)
    exploration, _ = await _completed_with_overflow(
        async_session, vault, dweller, loots=[_loot("Item A", 1), _loot("Item B", 2)]
    )
    vault_id, exploration_id = vault.id, exploration.id
    vault.bottle_caps = starting_caps
    async_session.add(vault)
    await async_session.commit()
    observed = []

    async def caps_event(_kind, event_vault_id, data):
        if event_vault_id == vault_id and data.get("resource_type") == "caps":
            observed.append((async_session.in_transaction(), data["amount"]))

    event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, caps_event)
    try:
        caps, remaining = await rewards_service.sell_unclaimed_item(async_session, exploration_id, 0)
    finally:
        event_bus.unsubscribe(GameEvent.RESOURCE_COLLECTED, caps_event)
    assert remaining == []
    await async_session.refresh(vault)
    assert caps == vault.bottle_caps - starting_caps
    assert observed == ([(False, caps)] if caps else [])


async def test_failed_overflow_sale_does_not_emit_caps(async_session, vault, dweller, make_vault_storage):
    from sqlalchemy import event

    await make_vault_storage(1)
    exploration, _ = await _completed_with_overflow(async_session, vault, dweller, loots=TWO_ITEMS)
    exploration_id, vault_id = exploration.id, vault.id
    observed = []

    async def caps_event(_kind, event_vault_id, data):
        if event_vault_id == vault_id and data.get("resource_type") == "caps":
            observed.append(data)

    def fail_commit(_session):
        raise RuntimeError("Overflow sale commit failed")

    event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, caps_event)
    event.listen(async_session.sync_session, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="Overflow sale commit failed"):
            await rewards_service.sell_unclaimed_item(async_session, exploration_id, 0)
        assert observed == []
    finally:
        event_bus.unsubscribe(GameEvent.RESOURCE_COLLECTED, caps_event)
        event.remove(async_session.sync_session, "before_commit", fail_commit)
        await async_session.rollback()
    restored = await crud.exploration.get(async_session, exploration_id)
    assert len(restored.unclaimed_loot) == 1


@pytest.mark.asyncio
async def test_catalog_miss_loot_is_held_but_never_minted(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
):
    """A weapon the catalog does not know must never mint a defaulted row, and must stay held."""
    storage = await make_vault_storage(0)
    exploration, rewards = await _completed_with_overflow(async_session, vault, dweller, loots=[RELICS])

    await async_session.refresh(exploration)
    assert rewards.items == []
    assert [entry["item_name"] for entry in exploration.unclaimed_loot or []] == ["Nonexistent Relic"]

    await _wide_storage(async_session, storage, 1)
    with pytest.raises(ValidationException):
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)
    await async_session.refresh(exploration)
    assert len(exploration.unclaimed_loot or []) == 1
    assert (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))).scalars().all() == []


@pytest.mark.asyncio
async def test_sell_catalog_miss_loot_clears_the_entry(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
):
    await make_vault_storage(0)
    exploration, _ = await _completed_with_overflow(
        async_session, vault, dweller, loots=[_loot("Nonexistent Relic", 1, "Legendary", "weapon")]
    )
    await async_session.refresh(vault)
    caps_before = vault.bottle_caps

    caps, remaining = await rewards_service.sell_unclaimed_item(async_session, exploration.id, 0)

    await async_session.refresh(vault)
    assert remaining == []
    assert caps == game_config.exploration.get_junk_value("Legendary")
    assert vault.bottle_caps == caps_before + caps


@pytest.mark.asyncio
async def test_take_weapon_emits_item_collected_after_commit(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
):
    storage = await make_vault_storage(0)
    exploration, _ = await _completed_with_overflow(
        async_session, vault, dweller, loots=[_loot("Laser pistol", 1, "Rare", "weapon")]
    )
    await _wide_storage(async_session, storage, 1)
    vault_id = vault.id
    observed = []

    async def item_event(_kind, event_vault_id, data):
        if event_vault_id == vault_id and data.get("item_type") == "weapon":
            observed.append((async_session.in_transaction(), data["amount"]))

    event_bus.subscribe(GameEvent.ITEM_COLLECTED, item_event)
    try:
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)
    finally:
        event_bus.unsubscribe(GameEvent.ITEM_COLLECTED, item_event)

    assert observed == [(False, 1)]


@pytest.mark.asyncio
async def test_take_junk_emits_its_catalog_material(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
):
    storage = await make_vault_storage(0)
    exploration, _ = await _completed_with_overflow(async_session, vault, dweller, loots=[_loot("Wonderglue")])
    await _wide_storage(async_session, storage, 1)
    vault_id = vault.id
    observed = []

    async def item_event(_kind, event_vault_id, data):
        if event_vault_id == vault_id:
            observed.append(data)

    event_bus.subscribe(GameEvent.ITEM_COLLECTED, item_event)
    try:
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)
    finally:
        event_bus.unsubscribe(GameEvent.ITEM_COLLECTED, item_event)

    assert observed == [{"item_type": "junk", "amount": 1, "source": "wasteland", "junk_type": "adhesive"}]
