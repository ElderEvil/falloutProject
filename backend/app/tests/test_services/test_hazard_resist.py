"""Tests for outfit hazard resistance: the fire column and the radiation override."""

from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.incident import IncidentType
from app.schemas.outfit import OutfitCreate
from app.services.combat.incident_service import incident_service
from app.services.radiation_service import outfit_radiation_resist
from app.utils.hazard_resist import outfit_fire_resist


class _StubOutfit:
    """A bare object standing in for an equipped outfit."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


def test_fire_resist_reads_the_declared_column():
    assert outfit_fire_resist(_StubOutfit(fire_resist=0.5)) == 0.5
    assert outfit_fire_resist(_StubOutfit(fire_resist=None)) == 0.0
    assert outfit_fire_resist(None) == 0.0


def test_radiation_resist_column_overrides_the_type_table():
    """A declared share wins; outfits without one keep the type-based fallback."""
    declared = _StubOutfit(name="Hazmat suit", outfit_type="rare_outfit", radiation_resist=1.0)
    assert outfit_radiation_resist(declared) == 1.0

    inherited = _StubOutfit(name="Robot armor", outfit_type="power_armor", radiation_resist=None)
    assert outfit_radiation_resist(inherited) == 0.75


async def _equip_fire_suit(async_session: AsyncSession, dweller_id, fire_resist: float = 0.5):
    """Create a fire-rated suit and equip it through the real equip path."""
    suit = await crud.outfit.create(
        async_session,
        obj_in=OutfitCreate(
            name="Firefighter suit",
            rarity="Rare",
            value=100,
            outfit_type="rare_outfit",
            fire_resist=fire_resist,
        ),
    )
    return await crud.outfit.equip(db_session=async_session, item_id=suit.id, dweller_id=dweller_id)


@pytest.mark.asyncio
async def test_fire_suit_reduces_fire_damage(async_session: AsyncSession, room_with_dwellers: dict):
    """A fire-rated outfit halves what its wearer takes; the others take it in full."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    for dweller in dwellers:
        dweller.health = 100
        dweller.max_health = 100
        async_session.add(dweller)
    await _equip_fire_suit(async_session, dwellers[0].id)
    incident = await crud.incident_crud.create(
        async_session, vault_id=room.vault_id, room_id=room.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    await async_session.commit()

    with patch("app.services.combat.incident_math.fire_damage", return_value=20.0):
        await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(dwellers[0])
    await async_session.refresh(dwellers[1])
    assert dwellers[0].health == 95
    assert dwellers[1].health == 90


@pytest.mark.asyncio
async def test_equip_refreshes_the_wearers_cached_outfit(async_session: AsyncSession, room_with_dwellers: dict):
    """Equipping must invalidate the dweller's cached relationship.

    Equip writes only the item's FK, so a dweller instance already held by the
    session kept serving its old value (None on a first equip) and every
    outfit-derived stat silently read as absent.
    """
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    assert dweller.__dict__.get("outfit") is None

    suit = await _equip_fire_suit(async_session, dweller.id)

    loaded = list(await crud.dweller.get_healthy_adults_in_room(async_session, room.id))
    wearer = next(row for row in loaded if row.id == dweller.id)
    assert wearer.__dict__.get("outfit") is not None
    assert wearer.__dict__["outfit"].id == suit.id


@pytest.mark.asyncio
async def test_hazmat_suit_blocks_radiation_once_equipped(async_session: AsyncSession, room_with_dwellers: dict):
    """The declared radiation column reaches an incident through the equipped outfit."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    suit = await crud.outfit.create(
        async_session,
        obj_in=OutfitCreate(
            name="Hazmat suit",
            rarity="Rare",
            value=100,
            outfit_type="rare_outfit",
            radiation_resist=1.0,
        ),
    )
    await crud.outfit.equip(db_session=async_session, item_id=suit.id, dweller_id=dweller.id)

    loaded = list(await crud.dweller.get_healthy_adults_in_room(async_session, room.id))
    wearer = next(row for row in loaded if row.id == dweller.id)
    assert outfit_radiation_resist(wearer.__dict__.get("outfit")) == 1.0


@pytest.mark.asyncio
async def test_both_hazard_outfit_protects_against_fire_and_radiation(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """The firefighter suit with a rad helmet is the only kit rated for both hazards."""
    roles = {row["name"]: row for row in _legendary_catalog()}
    entry = roles["Firefighter suit, rad helmet"]
    assert entry["fire_resist"] > 0
    assert entry["radiation_resist"] == 1.0

    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    dweller.health = 100
    dweller.max_health = 100
    suit = await crud.outfit.create(
        async_session,
        obj_in=OutfitCreate(
            name=entry["name"],
            rarity=entry["rarity"],
            value=entry["value"],
            outfit_type=entry["outfit_type"],
            fire_resist=entry["fire_resist"],
            radiation_resist=entry["radiation_resist"],
        ),
    )
    await crud.outfit.equip(db_session=async_session, item_id=suit.id, dweller_id=dweller.id)
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    await async_session.commit()

    loaded = list(await crud.dweller.get_healthy_adults_in_room(async_session, room.id))
    wearer = next(row for row in loaded if row.id == dweller.id)
    assert outfit_fire_resist(wearer.__dict__.get("outfit")) == entry["fire_resist"]
    assert outfit_radiation_resist(wearer.__dict__.get("outfit")) == 1.0

    with patch("app.services.combat.incident_math.fire_damage", return_value=20.0):
        await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(dweller)
    per_dweller = int(20.0) // len(loaded)
    assert dweller.health == 100 - int(per_dweller * (1 - entry["fire_resist"]))


def _legendary_catalog() -> list[dict]:
    from app.services.exploration.data_loader import load_outfits

    return [row for row in load_outfits() if row.get("rarity") == "Legendary"]


@pytest.mark.asyncio
async def test_fire_suit_does_not_help_against_intruders(async_session: AsyncSession, room_with_dwellers: dict):
    """Fire protection is fire-only; a fight is a fight."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    for dweller in dwellers:
        dweller.health = 100
        dweller.max_health = 100
        async_session.add(dweller)
    await _equip_fire_suit(async_session, dwellers[0].id)
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.RADROACH_INFESTATION,
        difficulty=2,
    )
    await async_session.commit()

    with (
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=20.0),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=0.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(dwellers[0])
    assert dwellers[0].health == 90
