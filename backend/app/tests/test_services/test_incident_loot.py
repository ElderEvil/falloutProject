"""Type-tiered incident rewards, and the loot the vault actually receives."""

import random

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.storage import storage as storage_crud
from app.models.incident import IncidentType
from app.models.junk import Junk
from app.models.storage import Storage
from app.models.weapon import Weapon
from app.services.combat import incident_math, incident_round
from app.utils.static_data import game_data_store

VICTORY_TYPES = (
    IncidentType.FERAL_GHOUL_ATTACK,
    IncidentType.RAIDER_ATTACK,
    IncidentType.DEATHCLAW_ATTACK,
)


@pytest.mark.parametrize("incident_type", list(IncidentType))
def test_every_incident_type_has_a_reward_tier(incident_type: IncidentType):
    """A new incident type must not silently fall back to no reward at all."""
    assert incident_math.get_reward_tier(incident_type).caps_multiplier >= 0


def test_caps_escalate_with_severity(monkeypatch: pytest.MonkeyPatch):
    """Under an identical roll, the roll decides only difficulty — the tier decides the rest."""
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


def test_fire_pays_in_experience_alone():
    loot = incident_math.generate_loot(difficulty=10, incident_type=IncidentType.FIRE)

    assert loot["caps"] == 0
    assert loot["items"] == []


@pytest.mark.parametrize(
    "incident_type",
    [
        IncidentType.RADROACH_INFESTATION,
        IncidentType.MOLE_RAT_ATTACK,
        IncidentType.RADSCORPION_ATTACK,
    ],
)
def test_bare_infestations_drop_caps_without_loot(incident_type: IncidentType):
    loot = incident_math.generate_loot(difficulty=10, incident_type=incident_type)

    assert loot["caps"] > 0
    assert loot["items"] == []


def test_ghouls_leave_scrap_behind():
    loot = incident_math.generate_loot(difficulty=5, incident_type=IncidentType.FERAL_GHOUL_ATTACK)

    assert loot["items"][0]["item_type"] == "junk"


def test_raider_gear_improves_with_difficulty():
    assert incident_math.generate_loot(3, IncidentType.RAIDER_ATTACK)["items"][0]["rarity"] == "common"
    assert incident_math.generate_loot(8, IncidentType.RAIDER_ATTACK)["items"][0]["rarity"] == "rare"


def test_deathclaw_salvage_improves_with_difficulty():
    assert incident_math.generate_loot(5, IncidentType.DEATHCLAW_ATTACK)["items"][0]["rarity"] == "rare"
    assert incident_math.generate_loot(9, IncidentType.DEATHCLAW_ATTACK)["items"][0]["rarity"] == "legendary"


@pytest.mark.parametrize("incident_type", VICTORY_TYPES)
def test_loot_is_drawn_from_the_shipped_catalog(incident_type: IncidentType):
    """Loot names must exist in the catalogs, or granting mints phantom items."""
    for _ in range(25):
        for item in incident_math.generate_loot(difficulty=9, incident_type=incident_type)["items"]:
            pool = game_data_store.junk_items if item["item_type"] == "junk" else game_data_store.weapons
            assert item["name"] in {entry.name for entry in pool}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("incident_type", "model"),
    [(IncidentType.RAIDER_ATTACK, Weapon), (IncidentType.DEATHCLAW_ATTACK, Junk)],
)
async def test_victory_hands_its_loot_to_the_vault(
    async_session: AsyncSession, room_with_dwellers: dict, incident_type: IncidentType, model
):
    """A promised item must reach storage — the whole tier table is theatre otherwise."""
    room = room_with_dwellers["room"]
    vault = room_with_dwellers["vault"]
    if await storage_crud.get_by_vault(async_session, vault.id) is None:
        async_session.add(Storage(vault_id=vault.id, max_space=100))
        await async_session.commit()

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=incident_type,
        difficulty=9,
        duration=60,
    )

    caps = await incident_round.resolve_victory(async_session, incident, room_with_dwellers["dwellers"])
    await async_session.commit()

    loot_items = incident.loot["items"]
    assert loot_items, f"a {incident_type} victory must drop gear"
    expected = loot_items[0]["name"]
    stored = (await async_session.exec(select(model).where(model.name == expected))).all()

    assert stored, f"{expected} was promised to the player but never reached storage"
    assert caps == incident.loot["caps"]
