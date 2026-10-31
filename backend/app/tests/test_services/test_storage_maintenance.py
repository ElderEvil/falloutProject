"""Hourly trials exercise real CRUD, clocks and catalog swaps."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession as RawSession

from app import crud
from app.core.enums import DwellerStatusEnum, RarityEnum, RoomTypeEnum, SPECIALEnum, WeaponTypeEnum
from app.core.game_config import game_config
from app.models.game_state import GameState
from app.models.notification import Notification, NotificationType
from app.models.storage import Storage
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services import storage_maintenance_service as maintenance
from app.services.catalog_service import load_weapons
from app.services.game_tick.storage_tick import process_storage_maintenance
from app.tests.factory.dwellers import create_random_common_dweller
from app.tests.factory.rooms import create_fake_room
from app.utils.item_factory import build_weapon


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    monkeypatch.setattr(game_config.storage, "maintenance_enabled", True)


async def setup_inventory(db, vault, *, name="Gauss pistol", due=True, online=True):
    storage = Storage(vault_id=vault.id, max_space=100)
    state = GameState(vault_id=vault.id, last_activity_time=datetime.utcnow() - timedelta(hours=0 if online else 24))
    entry = next(e for e in load_weapons() if e["name"].casefold() == name.casefold())
    weapon = build_weapon(entry, entry["rarity"], storage.id)
    weapon.last_maintenance_trial_at = datetime.utcnow() - timedelta(days=7) if due else None
    db.add_all([storage, state, weapon])
    await db.commit()
    return storage, state, weapon


def test_real_catalog_ladders():
    ladders = maintenance._ladders()
    assert len(ladders) == 51
    assert sum(len(ladder) > 1 for ladder in ladders.values()) == 31
    assert sum(any(e.name.lower().startswith("rusty ") for e in ladder) for ladder in ladders.values()) == 18
    for ladder in ladders.values():
        damage = [e.damage_min + e.damage_max for e in ladder]
        assert damage == sorted(set(damage))
    assert maintenance.ladder_for("Rusty Pistol") is None
    assert maintenance.ladder_for("Baseball bat") is None
    assert maintenance.ladder_for("AP lever-action rifle") == maintenance.ladder_for("Lever-action rifle")


@pytest.mark.parametrize(
    ("total", "direction", "chance"),
    [
        (0, -1, 0.02),
        (10, -1, 0.01),
        (18, -1, 0.002),
        (19.6, 0, 0),
        (20, 0, 0),
        (20.4, 0, 0),
        (30, 1, 0.01),
        (50, 1, 0.02),
    ],
)
def test_odds(total, direction, chance):
    actual_direction, actual_chance = maintenance.trial_odds(total)
    assert actual_direction == direction
    assert actual_chance == pytest.approx(chance)


@pytest.mark.parametrize("online", [True, False])
async def test_gap_consumes_one_hour_and_never_banks_rolls(async_session, vault, online):
    _, _, weapon = await setup_inventory(async_session, vault, online=online)
    original_id = weapon.id
    original_storage = weapon.storage_id
    target = maintenance.adjacent(weapon.name, -1)
    rng = Mock(return_value=0.0)
    stats = await process_storage_maintenance(async_session, vault.id, rng)
    assert stats == {"checked": 1, "changed": int(online)}
    assert rng.call_count == int(online)
    if online:
        assert weapon.name == target.name
        assert weapon.damage_min == target.damage_min
        assert weapon.stat == target.stat
        assert weapon.rarity == target.rarity
        assert weapon.value == target.value
    assert weapon.id == original_id
    assert weapon.storage_id == original_storage
    assert await process_storage_maintenance(async_session, vault.id, rng) == {"checked": 0, "changed": 0}
    assert rng.call_count == int(online)


async def test_grace_disabled_paused_and_failed_roll(async_session, vault, monkeypatch):
    _, state, weapon = await setup_inventory(async_session, vault, due=False)
    rng = Mock(return_value=1.0)
    monkeypatch.setattr(game_config.storage, "maintenance_enabled", False)
    await process_storage_maintenance(async_session, vault.id, rng)
    assert weapon.last_maintenance_trial_at is None
    monkeypatch.setattr(game_config.storage, "maintenance_enabled", True)
    await process_storage_maintenance(async_session, vault.id, rng)
    rng.assert_not_called()
    weapon.last_maintenance_trial_at = datetime.utcnow() - timedelta(hours=2)
    state.is_paused = True
    await async_session.commit()
    cursor = weapon.last_maintenance_trial_at
    await process_storage_maintenance(async_session, vault.id, rng)
    assert weapon.last_maintenance_trial_at == cursor
    state.is_paused = False
    await async_session.commit()
    await process_storage_maintenance(async_session, vault.id, rng)
    rng.assert_called_once()
    assert weapon.name == "Gauss pistol"
    assert weapon.last_maintenance_trial_at > cursor


async def test_offline_pass_advances_clocks_without_loading_workers(async_session, vault):
    _, _, weapon = await setup_inventory(async_session, vault, online=False)
    cursor = weapon.last_maintenance_trial_at
    statements = []

    def capture(connection, statement_cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    engine = async_session.bind.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        rng = Mock()
        assert await process_storage_maintenance(async_session, vault.id, rng) == {"checked": 1, "changed": 0}
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    rng.assert_not_called()
    await async_session.refresh(weapon)
    assert weapon.last_maintenance_trial_at > cursor
    assert weapon.name == "Gauss pistol"
    assert not any("from dweller" in sql for sql in statements)


def test_ladder_entries_normalize_catalog_enums():
    ladder = maintenance.ladder_for("Gauss pistol")
    assert ladder is not None
    assert all(isinstance(entry.rarity, RarityEnum) for entry in ladder)
    assert all(isinstance(entry.weapon_type, WeaponTypeEnum) for entry in ladder)


async def test_worker_query_eager_bonuses_and_exclusions(async_session, vault):
    from app.options.identity_modifiers import effective_stat
    from app.services.catalog_service import load_outfits
    from app.utils.item_factory import build_outfit, build_pet

    data = create_fake_room() | {
        "name": "Storage Room",
        "category": RoomTypeEnum.CAPACITY,
        "ability": SPECIALEnum.ENDURANCE,
        "vault_id": vault.id,
    }
    room = await crud.room.create(async_session, obj_in=RoomCreate(**data))
    worker = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            **(
                create_random_common_dweller()
                | {"vault_id": vault.id, "room_id": room.id, "status": DwellerStatusEnum.WORKING}
            )
        ),
    )
    worker.room_id = room.id
    worker.status = DwellerStatusEnum.WORKING
    outfit_entry = next(e for e in load_outfits() if e.get("endurance", 0) > 0)
    outfit = build_outfit(outfit_entry, outfit_entry["rarity"])
    outfit.dweller_id = worker.id
    pet = build_pet({"name": "St. Bernard"}, "common")
    pet.dweller_id = worker.id
    async_session.add_all([outfit, pet])
    await async_session.commit()
    workers = await crud.dweller.list_storage_workers(async_session, vault.id)
    assert len(workers) == 1
    assert effective_stat(workers[0], "endurance") >= worker.endurance + outfit_entry["endurance"] + 2
    worker.status = DwellerStatusEnum.EXPLORING
    await async_session.commit()
    assert await crud.dweller.list_storage_workers(async_session, vault.id) == []
    worker.status = DwellerStatusEnum.WORKING
    room.ability = SPECIALEnum.CHARISMA
    await async_session.commit()
    assert await crud.dweller.list_storage_workers(async_session, vault.id) == []


async def test_persistent_cooldown_and_storage_return_clock(async_session, vault):
    storage, _, weapon = await setup_inventory(async_session, vault)
    await process_storage_maintenance(async_session, vault.id, lambda: 0)
    result = await async_session.execute(select(Notification).where(Notification.vault_id == vault.id))
    notifications = result.scalars().all()
    assert len(notifications) == 1
    assert notifications[0].notification_type == NotificationType.STORAGE_ITEM_DEGRADED
    weapon.name = "Gauss pistol"
    weapon.last_maintenance_trial_at = datetime.utcnow() - timedelta(hours=2)
    await async_session.commit()
    await process_storage_maintenance(async_session, vault.id, lambda: 0)
    result = await async_session.execute(select(Notification).where(Notification.vault_id == vault.id))
    assert len(result.scalars().all()) == 1
    weapon.storage_id = None
    await async_session.commit()
    weapon.last_maintenance_trial_at = datetime.utcnow() - timedelta(days=7)
    weapon.storage_id = storage.id
    await async_session.commit()
    assert datetime.utcnow() - weapon.last_maintenance_trial_at < timedelta(seconds=5)
    rng = Mock()
    await process_storage_maintenance(async_session, vault.id, rng)
    rng.assert_not_called()


async def test_due_query_works_with_raw_sqlalchemy_session(async_session, vault):
    storage, _, weapon = await setup_inventory(async_session, vault)
    connection = await async_session.connection()
    async with RawSession(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False) as raw:
        due = await crud.weapon.list_due_for_trial(
            raw, storage.id, datetime.utcnow(), maintenance.eligible_weapon_names()
        )
        assert [w.id for w in due] == [weapon.id]
        assert await crud.dweller.list_storage_workers(raw, vault.id) == []


async def test_pause_resume_shifts_clock_preserving_remainder(async_session, vault):
    from app.services.game_loop_service import game_loop_service

    _, state, weapon = await setup_inventory(async_session, vault)
    now = datetime.utcnow()
    state.is_paused = True
    state.paused_at = now - timedelta(hours=4)
    state.last_tick_time = state.paused_at
    weapon.last_maintenance_trial_at = state.paused_at - timedelta(minutes=20)
    await async_session.commit()
    await game_loop_service.resume_vault(async_session, vault.id)
    assert timedelta(minutes=19) < datetime.utcnow() - weapon.last_maintenance_trial_at < timedelta(minutes=21)


@pytest.mark.parametrize(
    ("allow_upgrade", "allow_rarity", "expected"), [(False, True, False), (True, False, False), (True, True, True)]
)
def test_upgrade_guards(allow_upgrade, allow_rarity, expected, monkeypatch):
    monkeypatch.setattr(game_config.storage, "allow_upgrade", allow_upgrade)
    monkeypatch.setattr(game_config.storage, "allow_rarity_upgrade", allow_rarity)
    entry = next(e for e in load_weapons() if e["name"] == "Rusty plasma rifle")
    weapon = build_weapon(entry, entry["rarity"])
    target = maintenance.adjacent(weapon.name, 1)
    assert maintenance.roll_allowed(weapon, target, 1) is expected
    assert maintenance.roll_allowed(weapon, target, -1)


@pytest.mark.parametrize("name", ["Baseball bat", "Rusty Pistol"])
async def test_inert_and_unknown_are_not_due(async_session, vault, name):
    storage = Storage(vault_id=vault.id)
    entry = next(e for e in load_weapons() if e["name"] == "Gauss pistol")
    weapon = build_weapon(entry | {"name": name}, entry["rarity"], storage.id)
    async_session.add_all([storage, weapon])
    await async_session.commit()
    assert (
        await crud.weapon.list_due_for_trial(
            async_session, storage.id, datetime.utcnow(), maintenance.eligible_weapon_names()
        )
        == []
    )


async def test_blocked_upgrade_consumes_trial_and_notifies_once_after_allowed(async_session, vault, monkeypatch):
    _, _, weapon = await setup_inventory(async_session, vault, name="Rusty plasma rifle")
    # A staffed size-9 storage room has room for four 10-END workers (ratio 2).
    data = create_fake_room() | {
        "name": "Storage Room",
        "category": RoomTypeEnum.CAPACITY,
        "ability": SPECIALEnum.ENDURANCE,
        "vault_id": vault.id,
        "size": 9,
    }
    room = await crud.room.create(async_session, obj_in=RoomCreate(**data))
    for _ in range(4):
        worker = await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(**(create_random_common_dweller() | {"vault_id": vault.id, "endurance": 10})),
        )
        worker.room_id = room.id
        worker.status = DwellerStatusEnum.WORKING
    await async_session.commit()
    monkeypatch.setattr(game_config.storage, "allow_rarity_upgrade", False)
    rng = Mock(return_value=0.0)
    await process_storage_maintenance(async_session, vault.id, rng)
    rng.assert_not_called()
    assert weapon.name == "Rusty plasma rifle"
    monkeypatch.setattr(game_config.storage, "allow_rarity_upgrade", True)
    await process_storage_maintenance(async_session, vault.id, rng)
    rng.assert_not_called()
    weapon.last_maintenance_trial_at = datetime.utcnow() - timedelta(hours=2)
    await async_session.commit()
    await process_storage_maintenance(async_session, vault.id, rng)
    assert weapon.name == "Plasma rifle"
    rows = (await async_session.execute(select(Notification).where(Notification.vault_id == vault.id))).scalars().all()
    assert [n.notification_type for n in rows] == [NotificationType.STORAGE_ITEM_UPGRADED]
