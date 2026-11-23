from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import IncidentType
from app.schemas.outfit import OutfitCreate
from app.services.catalog_service import load_outfits
from app.services.combat.incident_service import incident_service
from app.tests.test_services._hazard_team_helpers import full_health
from app.utils.hazard_resist import outfit_fire_resist, outfit_radiation_resist


class _StubOutfit:
    def __init__(self, **fields):
        self.__dict__.update(fields)


def test_fire_resist_reads_the_declared_column():
    assert outfit_fire_resist(_StubOutfit(fire_resist=0.5)) == 0.5
    assert outfit_fire_resist(_StubOutfit(fire_resist=None)) == 0.0
    assert outfit_fire_resist(None) == 0.0


def test_radiation_resist_column_overrides_the_type_table():
    declared = _StubOutfit(name="Hazmat suit", outfit_type="rare_outfit", radiation_resist=1.0)
    assert outfit_radiation_resist(declared) == 1.0

    inherited = _StubOutfit(name="Robot armor", outfit_type="power_armor", radiation_resist=None)
    assert outfit_radiation_resist(inherited) == 0.75


async def _equip_suit(async_session, dweller_id, name="Firefighter suit", **fields):
    suit = await crud.outfit.create(
        async_session,
        obj_in=OutfitCreate(name=name, rarity="Rare", value=100, outfit_type="rare_outfit", **fields),
    )
    return await crud.outfit.equip(db_session=async_session, item_id=suit.id, dweller_id=dweller_id)


async def _fire_incident(async_session, room, incident_type=IncidentType.FIRE):
    incident = await crud.incident_crud.create(
        async_session, vault_id=room.vault_id, room_id=room.id, incident_type=incident_type, difficulty=2
    )
    await async_session.commit()
    return incident


async def _wear(wearer_id, room, async_session):
    loaded = list(await crud.dweller.get_healthy_adults_in_room(async_session, room.id))
    return next(row for row in loaded if row.id == wearer_id), loaded


@pytest.mark.parametrize(
    ("incident_type", "containment", "expected"),
    [(IncidentType.FIRE, True, {0: 95, 1: 90}), (IncidentType.RADROACH_INFESTATION, False, {0: 90})],
)
async def test_fire_suit_only_reduces_fire_damage(
    async_session, room_with_dwellers, incident_type, containment, expected
):
    room, dwellers = room_with_dwellers["room"], room_with_dwellers["dwellers"]
    await full_health(async_session, dwellers)
    await _equip_suit(async_session, dwellers[0].id, fire_resist=0.5)
    incident = await _fire_incident(async_session, room, incident_type)

    if containment:
        with patch("app.services.combat.incident_math.containment_damage", return_value=20.0):
            await incident_service.process_incident(async_session, incident, 2)
    else:
        with (
            patch("app.services.combat.incident_math.damage_to_dwellers", return_value=20.0),
            patch("app.services.combat.incident_math.damage_to_raiders", return_value=0.0),
        ):
            await incident_service.process_incident(async_session, incident, 2)

    for index, health in expected.items():
        await async_session.refresh(dwellers[index])
        assert dwellers[index].health == health


async def test_equip_refreshes_the_wearers_cached_outfit(async_session, room_with_dwellers):
    # Equip writes only the item's FK, so a session-held dweller kept serving a stale None.
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    assert dweller.__dict__.get("outfit") is None

    suit = await _equip_suit(async_session, dweller.id, fire_resist=0.5)

    wearer = (await _wear(dweller.id, room, async_session))[0]
    assert wearer.__dict__.get("outfit") is not None
    assert wearer.__dict__["outfit"].id == suit.id


async def test_hazmat_suit_blocks_radiation_once_equipped(async_session, room_with_dwellers):
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    await _equip_suit(async_session, dweller.id, name="Hazmat suit", radiation_resist=1.0)

    wearer = (await _wear(dweller.id, room, async_session))[0]
    assert outfit_radiation_resist(wearer.__dict__.get("outfit")) == 1.0


async def test_both_hazard_outfit_protects_against_fire_and_radiation(async_session, room_with_dwellers):
    entry = {row["name"]: row for row in load_outfits() if row.get("rarity") == "Legendary"}[
        "Firefighter suit, rad helmet"
    ]
    assert entry["fire_resist"] > 0
    assert entry["radiation_resist"] == 1.0

    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    await full_health(async_session, [dweller])
    keys = ("name", "rarity", "value", "outfit_type", "fire_resist", "radiation_resist")
    suit = await crud.outfit.create(async_session, obj_in=OutfitCreate(**{key: entry[key] for key in keys}))
    await crud.outfit.equip(db_session=async_session, item_id=suit.id, dweller_id=dweller.id)
    incident = await _fire_incident(async_session, room)

    wearer, loaded = await _wear(dweller.id, room, async_session)
    assert outfit_fire_resist(wearer.__dict__.get("outfit")) == entry["fire_resist"]
    assert outfit_radiation_resist(wearer.__dict__.get("outfit")) == 1.0

    with patch("app.services.combat.incident_math.containment_damage", return_value=20.0):
        await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(dweller)
    per_dweller = int(20.0) // len(loaded)
    assert dweller.health == 100 - int(per_dweller * (1 - entry["fire_resist"]))
