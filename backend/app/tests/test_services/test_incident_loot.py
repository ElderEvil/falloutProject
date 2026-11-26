import random

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import IncidentStatus, IncidentType
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud.storage import storage as storage_crud
from app.models.junk import Junk
from app.models.storage import Storage
from app.models.weapon import Weapon
from app.services.combat import incident_math, incident_round
from app.services.combat.incident_service import incident_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException
from app.utils.static_data import game_data_store

VICTORY_TYPES = (IncidentType.FERAL_GHOUL_ATTACK, IncidentType.RAIDER_ATTACK, IncidentType.DEATHCLAW_ATTACK)


async def _storage(session: AsyncSession, vault_id, max_space: int) -> Storage:
    storage = await storage_crud.get_by_vault(session, vault_id)
    if storage is None:
        storage = Storage(vault_id=vault_id, max_space=max_space)
        session.add(storage)
    else:
        storage.max_space = max_space
        storage.used_space = 0
    await session.commit()
    return storage


async def _incident(session: AsyncSession, room, incident_type: IncidentType, difficulty: int, duration: int = 60):
    return await crud.incident_crud.create(
        session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=incident_type,
        difficulty=difficulty,
        duration=duration,
    )


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_every_incident_type_has_a_reward_tier(incident_type: IncidentType):
    # A new incident type must not silently fall back to no reward at all.
    assert incident_math.get_reward_tier(incident_type).caps_multiplier >= 0


def test_caps_escalate_with_severity(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(random, "randint", lambda low, high: high)
    caps = [
        incident_math.generate_loot(difficulty=5, incident_type=incident_type)["caps"]
        for incident_type in (
            IncidentType.FIRE,
            IncidentType.RADROACH_INFESTATION,
            IncidentType.MOLE_RAT_ATTACK,
            IncidentType.RAIDER_ATTACK,
            IncidentType.DEATHCLAW_ATTACK,
        )
    ]
    assert caps == sorted(caps)
    assert caps[0] == 0


# (type, difficulty, caps pay, first item type, first item rarity)
LOOT_CASES = [
    (IncidentType.FIRE, 10, False, None, None),
    (IncidentType.RADROACH_INFESTATION, 10, True, None, None),
    (IncidentType.MOLE_RAT_ATTACK, 10, True, None, None),
    (IncidentType.RADSCORPION_ATTACK, 10, True, None, None),
    (IncidentType.FERAL_GHOUL_ATTACK, 5, True, "junk", "common"),
    (IncidentType.RAIDER_ATTACK, 3, True, "weapon", "common"),
    (IncidentType.RAIDER_ATTACK, 8, True, "weapon", "rare"),
    (IncidentType.DEATHCLAW_ATTACK, 5, True, "junk", "rare"),
    (IncidentType.DEATHCLAW_ATTACK, 9, True, "junk", "legendary"),
]


@pytest.mark.parametrize(("incident_type", "difficulty", "pays_caps", "item_type", "rarity"), LOOT_CASES)
def test_loot_tiers_scale_with_type_and_severity(incident_type, difficulty, pays_caps, item_type, rarity):
    loot = incident_math.generate_loot(difficulty=difficulty, incident_type=incident_type)
    assert (loot["caps"] > 0) is pays_caps
    if item_type is None:
        # A hazard pays in experience alone; a bare infestation drops caps but no gear.
        assert loot["items"] == []
    else:
        assert (loot["items"][0]["item_type"], loot["items"][0]["rarity"]) == (item_type, rarity)


@pytest.mark.parametrize("incident_type", VICTORY_TYPES)
def test_loot_is_drawn_from_the_shipped_catalog(incident_type: IncidentType):
    # Loot names must exist in the catalogs, or granting mints phantom items.
    for _ in range(25):
        for item in incident_math.generate_loot(difficulty=9, incident_type=incident_type)["items"]:
            pool = game_data_store.junk_items if item["item_type"] == "junk" else game_data_store.weapons
            assert item["name"] in {entry.name for entry in pool}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("incident_type", "model"), [(IncidentType.RAIDER_ATTACK, Weapon), (IncidentType.DEATHCLAW_ATTACK, Junk)]
)
async def test_victory_hands_its_loot_to_the_vault(
    async_session: AsyncSession, room_with_dwellers: dict, incident_type: IncidentType, model
):
    # A promised item must reach storage — the whole tier table is theatre otherwise.
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    await _storage(async_session, vault.id, 100)
    incident = await _incident(async_session, room, incident_type, 9)
    caps = await incident_round.resolve_victory(async_session, incident, room_with_dwellers["dwellers"])
    await async_session.commit()

    loot_items = incident.loot["items"]
    assert loot_items, f"a {incident_type} victory must drop gear"
    expected = loot_items[0]["name"]
    stored = (await async_session.exec(select(model).where(model.name == expected))).all()
    assert stored, f"{expected} was promised to the player but never reached storage"
    assert caps == incident.loot["caps"]


@pytest.mark.asyncio
async def test_victory_records_the_experience_its_responders_gained(
    async_session: AsyncSession, room_with_dwellers: dict
):
    # The XP the panel reports must equal what the responders actually received.
    room, vault, dwellers = room_with_dwellers["room"], room_with_dwellers["vault"], room_with_dwellers["dwellers"]
    await _storage(async_session, vault.id, 100)
    before = {dweller.id: dweller.experience for dweller in dwellers}
    incident = await _incident(async_session, room, IncidentType.RAIDER_ATTACK, 4)
    await incident_round.resolve_victory(async_session, incident, dwellers)
    await async_session.commit()

    gained = sum(dweller.experience - before[dweller.id] for dweller in dwellers)
    assert gained > 0
    assert incident.loot["experience"] == gained


@pytest.mark.asyncio
async def test_full_storage_does_not_block_an_incident_victory(async_session: AsyncSession, room_with_dwellers: dict):
    # A full vault must not leave a won incident stuck retrying forever.
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    async_session.add(Storage(vault_id=vault.id, max_space=0))
    await async_session.commit()

    incident = await _incident(async_session, room, IncidentType.RAIDER_ATTACK, 1)
    async_session.add(incident)
    await async_session.commit()
    await async_session.refresh(incident)

    await incident_service.process_incident(async_session, incident, 60)

    await async_session.refresh(incident)
    assert incident.status == IncidentStatus.RESOLVED, "the victory must commit even when nothing fits"
    assert incident.loot["items"] == [], "an item that could not be stored is not reported as recovered"
    assert incident.unclaimed_loot, "the item waits for a take/sell decision instead of being lost"
    events = await crud.incident_crud.get_recent_events(async_session, incident.id)
    assert any("held for your decision" in event.message for event in events), "the player is told the item is waiting"


async def _resolve_victory_into_a_full_vault(async_session: AsyncSession, room, vault):
    storage = await _storage(async_session, vault.id, 0)
    incident = await _incident(async_session, room, IncidentType.RAIDER_ATTACK, 1)
    await incident_service.process_incident(async_session, incident, 60)
    await async_session.refresh(incident)
    return incident, storage


@pytest.mark.asyncio
async def test_held_incident_overflow_conflicts_until_space_frees_up(
    async_session: AsyncSession, room_with_dwellers: dict
):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    incident, storage = await _resolve_victory_into_a_full_vault(async_session, room, vault)
    held_name = incident.unclaimed_loot[0]["name"]

    with pytest.raises(ResourceConflictException):
        await incident_service.take_unclaimed_item(async_session, incident.id, vault.id, 0)
    await async_session.refresh(incident)
    assert len(incident.unclaimed_loot) == 1
    with pytest.raises(ResourceNotFoundException):
        await incident_service.take_unclaimed_item(async_session, incident.id, vault.id, 5)

    storage.max_space = 1
    async_session.add(storage)
    await async_session.flush()
    assert await incident_service.take_unclaimed_item(async_session, incident.id, vault.id, 0) == []
    stored = (await async_session.exec(select(Weapon).where(Weapon.storage_id == storage.id))).all()
    assert [weapon.name for weapon in stored] == [held_name]


@pytest.mark.asyncio
async def test_selling_held_incident_overflow_pays_caps_without_space(
    async_session: AsyncSession, room_with_dwellers: dict
):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    incident, _ = await _resolve_victory_into_a_full_vault(async_session, room, vault)
    await async_session.refresh(vault)
    caps_before = vault.bottle_caps
    observed = []

    async def caps_event(_kind, event_vault_id, data):
        if event_vault_id == vault.id and data.get("resource_type") == "caps":
            observed.append((async_session.in_transaction(), data["amount"]))

    event_bus.subscribe(GameEvent.RESOURCE_COLLECTED, caps_event)
    try:
        caps, remaining = await incident_service.sell_unclaimed_item(async_session, incident.id, vault.id, 0)
    finally:
        event_bus.unsubscribe(GameEvent.RESOURCE_COLLECTED, caps_event)

    assert observed == [(False, caps)]
    assert caps > 0
    assert remaining == []
    await async_session.refresh(vault)
    assert vault.bottle_caps == caps_before + caps


@pytest.mark.asyncio
async def test_taking_stacked_junk_prices_each_row_at_the_unit_value(
    async_session: AsyncSession, room_with_dwellers: dict
):
    # A stack of N junk rows must not carry N times the unit value each.
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    storage = await _storage(async_session, vault.id, 2)
    incident = await _incident(async_session, room, IncidentType.FERAL_GHOUL_ATTACK, 3)
    incident.unclaimed_loot = [{"item_type": "junk", "rarity": "common", "name": "Scrap Metal", "quantity": 2}]
    async_session.add(incident)
    await async_session.commit()

    await incident_service.take_unclaimed_item(async_session, incident.id, vault.id, 0)

    stored = (await async_session.exec(select(Junk).where(Junk.storage_id == storage.id))).all()
    assert len(stored) == 2
    unit_value = game_config.exploration.junk_value_common
    assert [junk.value for junk in stored] == [unit_value, unit_value]


@pytest.mark.asyncio
async def test_taking_held_loot_with_no_catalog_row_is_rejected_and_kept(
    async_session: AsyncSession, room_with_dwellers: dict
):
    # A weapon the catalog does not know must never mint a defaulted row, and must stay held.
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    storage = await _storage(async_session, vault.id, 1)
    incident = await _incident(async_session, room, IncidentType.RAIDER_ATTACK, 3)
    incident.unclaimed_loot = [{"item_type": "weapon", "rarity": "common", "name": "Nonexistent Relic", "quantity": 1}]
    async_session.add(incident)
    await async_session.commit()

    with pytest.raises(ValidationException):
        await incident_service.take_unclaimed_item(async_session, incident.id, vault.id, 0)

    await async_session.refresh(incident)
    assert len(incident.unclaimed_loot) == 1
    stored = (await async_session.exec(select(Weapon).where(Weapon.storage_id == storage.id))).all()
    assert stored == []
