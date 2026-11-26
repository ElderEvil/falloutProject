from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum, WorldEventStatus
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.exploration import Exploration
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.models.world_event import WorldEvent, WorldEventParticipation
from app.schemas.exploration_event import (
    ItemSchema,
    LootEventSchema,
    LootSchema,
    OutfitSchema,
    WeaponSchema,
)
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.event_service import event_service
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.services.world_event_service import world_event_service
from app.utils.exceptions import ValidationException
from app.utils.time import utcnow

JUNK_LOOT = LootEventSchema(
    description="Found some Wonderglue",
    loot=LootSchema(item=ItemSchema(name="Wonderglue", rarity="Common", value=5), item_type="junk", caps=0),
)


async def _ensure_vault_storage(async_session: AsyncSession, vault_id) -> Storage:
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault_id))
    storage = result.scalar_one_or_none()
    if storage is None:
        storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault_id)
    return storage


@pytest_asyncio.fixture
async def make_vault_storage(async_session: AsyncSession, vault: Vault) -> Callable[[int], Awaitable[Storage]]:
    """Factory for the test vault's storage, emptied and sized via max_space."""
    storage = await _ensure_vault_storage(async_session, vault.id)

    async def _make(max_space: int = 10) -> Storage:
        storage.max_space = max_space
        storage.used_space = 0
        async_session.add(storage)
        await async_session.flush()
        return storage

    return _make


async def _equip_weapon(
    async_session: AsyncSession,
    dweller: Dweller,
    *,
    name: str,
    rarity: RarityEnum,
    damage_min: int,
    damage_max: int,
    value: int = 10,
) -> Weapon:
    weapon = Weapon(
        name=name,
        rarity=rarity,
        value=value,
        weapon_type=WeaponTypeEnum.GUN,
        weapon_subtype=WeaponSubtypeEnum.PISTOL,
        stat="agility",
        damage_min=damage_min,
        damage_max=damage_max,
        dweller_id=dweller.id,
    )
    async_session.add(weapon)
    await async_session.flush()
    return weapon


async def _equip_outfit(
    async_session: AsyncSession,
    dweller: Dweller,
    *,
    name: str,
    rarity: RarityEnum,
    value: int,
    outfit_type: OutfitTypeEnum,
) -> Outfit:
    outfit = Outfit(name=name, rarity=rarity, value=value, outfit_type=outfit_type, dweller_id=dweller.id)
    async_session.add(outfit)
    await async_session.flush()
    return outfit


def _weapon_loot_event(name: str, rarity: str, damage_min: int, damage_max: int, value: int) -> LootEventSchema:
    item = WeaponSchema(
        name=name,
        rarity=rarity,
        value=value,
        weapon_type="MELEE",
        weapon_subtype="BLUNT",
        stat="strength",
        damage_min=damage_min,
        damage_max=damage_max,
    )
    return LootEventSchema(description=f"Found a {name}", loot=LootSchema(item=item, item_type="weapon", caps=5))


async def _process_loot_event(async_session: AsyncSession, exploration, loot_event: LootEventSchema) -> AsyncMock:
    with (
        patch("app.services.exploration.event_service.event_generator.generate_event", return_value=loot_event),
        patch("app.services.exploration.event_service.sse_manager.publish", new_callable=AsyncMock),
        patch(
            "app.services.exploration.event_service.notification_service.notify_exploration_update",
            new_callable=AsyncMock,
        ) as notify,
    ):
        await event_service.process_event(async_session, exploration)
    return notify


async def _finish(async_session: AsyncSession, exploration, *, recalled: bool = False, **fields) -> None:
    """Walk the run onto its return leg and backdate the arrival."""
    for key, value in fields.items():
        setattr(exploration, key, value)
    exploration.start_time = utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()
    await exploration_coordinator.start_return(async_session, exploration.id, recalled=recalled)
    await async_session.refresh(exploration)
    exploration.return_completes_at = utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()


async def test_transfer_skips_medical_loot_entries(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    await make_vault_storage(5)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.add_loot(item_name="Stimpak", quantity=1, rarity="Common", item_type="stimpak")
    exploration.add_loot(item_name="RadAway", quantity=1, rarity="Common", item_type="radaway")
    exploration.add_loot(item_name="Wonderglue", quantity=1, rarity="Common", item_type="junk")
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)
    result = await rewards_service._transfer_loot_to_storage(async_session, exploration)
    assert [item["item_type"] for item in result["transferred"]] == ["junk"]
    junk_names = {
        junk.name
        for junk in (await async_session.execute(select(Junk).where(Junk.storage_id == result["storage_id"]))).scalars()
    }
    assert junk_names == {"Wonderglue"}


async def test_transfer_missing_weapon_data_holds_item_as_overflow(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    storage = await make_vault_storage()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.add_loot(item_name="NonExistentWeapon12345", quantity=1, rarity="Legendary", item_type="weapon")
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)
    result = await rewards_service._transfer_loot_to_storage(async_session, exploration)
    assert result["transferred"] == []
    assert [item["item_name"] for item in result["overflow"]] == ["NonExistentWeapon12345"]
    weapons = await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))
    assert weapons.scalars().all() == []  # no defaulted Weapon record was created


async def test_transfer_invalid_rarity_defaults_to_common(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    storage = await make_vault_storage()
    await async_session.flush()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.add_loot(item_name="Test Item", quantity=1, rarity="InvalidRarity", item_type="junk")
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)
    result = await rewards_service._transfer_loot_to_storage(async_session, exploration)
    assert len(result["transferred"]) == 1
    assert result["transferred"][0]["item_name"] == "Test Item"
    junk_records = (await async_session.execute(select(Junk).where(Junk.storage_id == storage.id))).scalars().all()
    assert len(junk_records) == 1
    assert junk_records[0].rarity == RarityEnum.COMMON


async def test_catalog_miss_weapon_stays_ordinary_loot_and_run_completes(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    await make_vault_storage()
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("NonExistentWeapon12345", "Legendary", 19, 31, 500)
    )
    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == [".32 pistol"]
    held = (await async_session.execute(select(Weapon).where(Weapon.exploration_id == exploration.id))).scalars().all()
    assert held == []
    assert all(entry.get("equipped") is not True for entry in exploration.loot_collected)
    await _finish(async_session, exploration)
    rewards = await exploration_coordinator.finalize_return(async_session, exploration.id)
    assert rewards.caps == 5
    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == [".32 pistol"]


async def test_medicine_loot_adds_single_log_entry(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    dweller.health = 100
    dweller.max_health = 100
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.flush()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    item = ItemSchema(name="Stimpak", rarity="Common", value=20)
    loot_event = LootEventSchema(description="Found a Stimpak", loot=LootSchema(item=item, item_type="stimpak", caps=0))
    await _process_loot_event(async_session, exploration, loot_event)
    assert exploration.stimpaks == 1
    assert len(exploration.events) == 1
    assert exploration.events[0]["type"] == "loot"
    assert exploration.loot_collected[-1]["item_type"] == "stimpak"


async def test_auto_equip_keeps_strongest_found_outfit(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    # A lower-rarity later find never replaces the strongest equipped outfit.
    storage = await make_vault_storage()
    await _equip_outfit(
        async_session,
        dweller,
        name="Mechanic jumpsuit",
        rarity=RarityEnum.COMMON,
        value=10,
        outfit_type=OutfitTypeEnum.COMMON,
    )
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    ranger = OutfitSchema(name="NCR Ranger outfit", rarity="Rare", value=100, outfit_type="rare_outfit")
    await _process_loot_event(
        async_session,
        exploration,
        LootEventSchema(
            description="Found a NCR Ranger outfit", loot=LootSchema(item=ranger, item_type="outfit", caps=5)
        ),
    )
    rags = OutfitSchema(name="Tattered rags", rarity="Common", value=5, outfit_type="common_outfit")
    await _process_loot_event(
        async_session,
        exploration,
        LootEventSchema(description="Found some Tattered rags", loot=LootSchema(item=rags, item_type="outfit", caps=0)),
    )
    equipped = (await async_session.execute(select(Outfit).where(Outfit.dweller_id == dweller.id))).scalars().all()
    assert [o.name for o in equipped] == ["NCR Ranger outfit"]
    held = (await async_session.execute(select(Outfit).where(Outfit.exploration_id == exploration.id))).scalars().all()
    assert [o.name for o in held] == ["Mechanic jumpsuit"]
    assert all(o.dweller_id is None and o.storage_id is None for o in held)
    assert exploration.loot_collected[0]["item_name"] == "NCR Ranger outfit"
    assert exploration.loot_collected[0]["equipped"] is True
    assert exploration.loot_collected[1].get("equipped") is not True
    await _finish(async_session, exploration)
    await exploration_coordinator.finalize_return(async_session, exploration.id)
    equipped = (await async_session.execute(select(Outfit).where(Outfit.dweller_id == dweller.id))).scalars().all()
    assert [o.name for o in equipped] == ["NCR Ranger outfit"]
    stored = (await async_session.execute(select(Outfit).where(Outfit.storage_id == storage.id))).scalars().all()
    assert [o.name for o in stored] == ["Mechanic jumpsuit"]


async def test_process_event_publishes_followup_events(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    await make_vault_storage()
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)
    dweller.health = 20
    dweller.max_health = 100
    dweller.radiation = 0
    dweller.stimpack = 1
    async_session.add(dweller)
    await async_session.flush()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4, stimpaks=1)
    with (
        patch(
            "app.services.exploration.event_service.event_generator.generate_event",
            return_value=_weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500),
        ),
        patch("app.services.exploration.event_service.sse_manager.publish", new_callable=AsyncMock) as publish_mock,
    ):
        await event_service.process_event(async_session, exploration)
    # Only the exploration-channel publishes are journey events; the equip bell's
    # real-time delivery lands on the "notifications" channel via the same manager.
    published_types = [call.args[2]["type"] for call in publish_mock.await_args_list if call.args[1] == "exploration"]
    assert published_types == ["loot", "equip", "item_use"]
    assert exploration.stimpaks == 0
    assert dweller.health == 60


@pytest.mark.parametrize(("radiation", "radaways_left", "radiation_left"), [(25, 0, 0), (24, 1, 24)])
async def test_auto_radaway_gate_is_quarter_max_health_radiation(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, radiation: int, radaways_left: int, radiation_left: int
) -> None:
    dweller.health = 100
    dweller.max_health = 100
    dweller.radiation = radiation
    dweller.radaway = 1
    async_session.add(dweller)
    await async_session.flush()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4, radaways=1)
    await _process_loot_event(async_session, exploration, JUNK_LOOT)
    assert exploration.radaways == radaways_left
    assert dweller.radiation == radiation_left
    assert dweller.health == 100


@pytest.mark.parametrize(
    ("health", "radiation", "stimpaks_left", "health_after", "uses_item"),
    [(45, 30, 0, 70, True), (40, 60, 1, 40, False)],
)
async def test_auto_stimpak_gate_uses_full_max_health(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    health: int,
    radiation: int,
    stimpaks_left: int,
    health_after: int,
    uses_item: bool,
) -> None:
    # The Stimpak gate compares against FULL max health, so radiation never hides a wound.
    dweller.stimpack = 1
    dweller.health = health
    dweller.max_health = 100
    dweller.radiation = radiation
    async_session.add(dweller)
    await async_session.flush()
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4, stimpaks=1)
    await _process_loot_event(async_session, exploration, JUNK_LOOT)
    assert exploration.stimpaks == stimpaks_left
    assert dweller.health == health_after
    item_use = [e for e in exploration.events if e["type"] == "item_use"]
    assert bool(item_use) is uses_item


async def _create_world_event(
    async_session: AsyncSession, *, status: WorldEventStatus = WorldEventStatus.ACTIVE
) -> WorldEvent:
    now = utcnow()
    event = WorldEvent(
        kind="migration",
        title="Migration surge",
        description="Creatures are on the move.",
        target_amount=100,
        personal_min=0,
        reward=[],
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
        status=status,
    )
    async_session.add(event)
    await async_session.commit()
    await async_session.refresh(event)
    return event


async def _event_totals(async_session: AsyncSession, event_id, vault_id) -> tuple[int, int]:
    """(shared event progress, this vault's contribution)."""
    event = await async_session.get(WorldEvent, event_id)
    rows = (
        (
            await async_session.execute(
                select(WorldEventParticipation).where(
                    WorldEventParticipation.world_event_id == event_id,
                    WorldEventParticipation.vault_id == vault_id,
                )
            )
        )
        .scalars()
        .all()
    )
    return event.progress_amount, sum(row.contribution for row in rows)


async def _returning_run(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> Exploration:
    """A free-roam run that has explored its full duration and is due home."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _finish(async_session, exploration)
    return exploration


@pytest.mark.parametrize(("clear_tier", "credited"), [(None, 1), (2, 3)])
async def test_finalize_return_credits_active_world_event_exactly_once(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
    clear_tier: int | None,
    credited: int,
) -> None:
    # The already-finished guard, not the world-event code, makes a second call a no-op.
    await make_vault_storage()
    event = await _create_world_event(async_session)
    exploration = await _returning_run(async_session, vault, dweller)
    if clear_tier is not None:
        exploration.clear_tier = clear_tier
        async_session.add(exploration)
        await async_session.commit()
    rewards = await exploration_coordinator.finalize_return(async_session, exploration.id)
    assert rewards.exploration_id == exploration.id
    totals = await _event_totals(async_session, event.id, vault.id)
    assert totals == (credited, credited)
    with pytest.raises(ValidationException):
        await exploration_coordinator.finalize_return(async_session, exploration.id)
    assert await _event_totals(async_session, event.id, vault.id) == totals


async def test_finalize_return_survives_world_event_failure(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await make_vault_storage()
    event = await _create_world_event(async_session)
    exploration = await _returning_run(async_session, vault, dweller)

    async def _boom(*args, **kwargs):
        raise RuntimeError("world event store down")

    monkeypatch.setattr(world_event_service, "record_contribution", _boom)
    # Read the id before the call: the failed world-event contribution rolls the run back and
    # expires the instance, and an expired attribute read outside the greenlet raises
    # MissingGreenlet (the coordinator caches the same ids for this reason).
    exploration_id = exploration.id
    rewards = await exploration_coordinator.finalize_return(async_session, exploration_id)
    assert rewards.exploration_id == exploration_id
    assert await _event_totals(async_session, event.id, vault.id) == (0, 0)
