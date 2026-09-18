"""Hazard-team mechanic: response bonus, damage resist, and auto-equip."""

from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import GenderEnum, HazardTeam, OutfitTypeEnum, RarityEnum
from app.models.hazard_team import ACTIVE_STATUS, RESERVE_STATUS, HazardTeamMember
from app.models.incident import IncidentType
from app.schemas.dweller import DwellerCreate
from app.services.combat.incident_round import apply_damage
from app.services.combat.incident_service import incident_service
from app.services.contamination_team_service import (
    QUALIFYING_INCIDENTS,
    TEAM_HAZARD_RESIST,
    TEAM_RESPONSE_BONUS,
    TEAM_SIZE,
    contamination_team_service,
)


async def _raise_incident(session: AsyncSession, room, incident_type: IncidentType):
    return await crud.incident_crud.create(
        session, vault_id=room.vault_id, room_id=room.id, incident_type=incident_type, difficulty=2
    )


async def _fight(session: AsyncSession, room, incident_type: IncidentType, dwellers: list):
    incident = await _raise_incident(session, room, incident_type)
    await contamination_team_service.record_participation(session, incident, dwellers)
    await session.commit()
    return incident


async def _make_member(session: AsyncSession, vault_id, dweller_id, team: HazardTeam, status: str):
    await crud.hazard_team_crud.add(
        session,
        HazardTeamMember(vault_id=vault_id, dweller_id=dweller_id, team=team, status=status),
    )
    await session.commit()


def _outfit_data(name: str, *, storage_id=None, dweller_id=None) -> dict:
    data = {
        "name": name,
        "rarity": RarityEnum.COMMON,
        "value": 10,
        "outfit_type": OutfitTypeEnum.COMMON,
        "gender": GenderEnum.MALE,
    }
    if storage_id:
        data["storage_id"] = storage_id
    if dweller_id:
        data["dweller_id"] = dweller_id
    return data


async def _full_health(session: AsyncSession, dwellers: list) -> None:
    for dweller in dwellers:
        dweller.health = 100
        dweller.max_health = 100
        dweller.radiation = 0
        session.add(dweller)
    await session.commit()


@pytest.mark.asyncio
async def test_active_member_takes_less_damage(async_session: AsyncSession, room_with_dwellers: dict):
    """An active matching member takes the hazard-resist share off their damage."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    await _full_health(async_session, dwellers)
    incident = await _raise_incident(async_session, room, IncidentType.FIRE)
    active_id = dwellers[0].id

    damaged, deaths, taken = await apply_damage(
        async_session, incident, dwellers, 100.0, active_member_ids=frozenset({active_id})
    )

    assert taken == 90
    assert dwellers[0].health == 60
    assert dwellers[1].health == 50


@pytest.mark.asyncio
async def test_active_member_takes_less_radiation(async_session: AsyncSession, room_with_dwellers: dict):
    """A radiation-team member absorbs less RAD from a radscorpion attack."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    await _full_health(async_session, dwellers)
    incident = await _raise_incident(async_session, room, IncidentType.RADSCORPION_ATTACK)
    active_id = dwellers[0].id

    await apply_damage(async_session, incident, dwellers, 100.0, active_member_ids=frozenset({active_id}))

    assert dwellers[0].radiation == 16
    assert dwellers[1].radiation == 25


@pytest.mark.asyncio
async def test_get_active_member_ids_excludes_bench(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """Bench/reserve members never count as active responders."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(
                async_session,
                obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
            )
        )
    for index, dweller in enumerate(dwellers):
        status = ACTIVE_STATUS if index < TEAM_SIZE else RESERVE_STATUS
        await _make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, status)

    active_ids = await crud.hazard_team_crud.get_active_member_ids(
        async_session, room.vault_id, HazardTeam.FIRE, [dweller.id for dweller in dwellers]
    )

    assert len(active_ids) == TEAM_SIZE
    assert dwellers[TEAM_SIZE].id not in active_ids


@pytest.mark.asyncio
async def test_containment_power_boosted_by_active_members(async_session: AsyncSession, room_with_dwellers: dict):
    """Each active matching member adds response power to the containment math."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    await _make_member(async_session, room.vault_id, dwellers[0].id, HazardTeam.FIRE, ACTIVE_STATUS)
    incident = await _raise_incident(async_session, room, IncidentType.FIRE)

    with (
        patch("app.services.combat.incident_math.dweller_combat_power", return_value=100.0),
        patch("app.services.combat.incident_math.fire_suppression", return_value=0.0) as mock_suppression,
        patch("app.services.combat.incident_math.fire_damage", return_value=0.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    assert mock_suppression.call_args.args[0] == int(100 * (1 + TEAM_RESPONSE_BONUS))


@pytest.mark.asyncio
async def test_non_hazard_incident_gets_no_bonus(async_session: AsyncSession, room_with_dwellers: dict):
    """A fire-team member earns nothing against an intruder attack."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    await _make_member(async_session, room.vault_id, dwellers[0].id, HazardTeam.FIRE, ACTIVE_STATUS)
    incident = await _raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)

    with (
        patch("app.services.combat.incident_math.dweller_combat_power", return_value=100.0),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=0.0) as mock_damage,
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=0.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    assert mock_damage.call_args.args[0] == 100


@pytest.mark.asyncio
async def test_wrong_team_member_in_same_incident_gets_no_bonus(async_session: AsyncSession, room_with_dwellers: dict):
    """A radiation-team member fighting a fire gets no fire-team bonus."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    await _make_member(async_session, room.vault_id, dwellers[0].id, HazardTeam.RADIATION, ACTIVE_STATUS)
    incident = await _raise_incident(async_session, room, IncidentType.FIRE)

    with (
        patch("app.services.combat.incident_math.dweller_combat_power", return_value=100.0),
        patch("app.services.combat.incident_math.fire_suppression", return_value=0.0) as mock_suppression,
        patch("app.services.combat.incident_math.fire_damage", return_value=0.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    assert mock_suppression.call_args.args[0] == 100


@pytest.mark.asyncio
async def test_active_gainer_with_spare_outfit_gets_equipped(async_session: AsyncSession, room_with_dwellers: dict):
    """A newly-active member wears the spare matching outfit from storage."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=room.vault_id)
    await crud.outfit.create(async_session, _outfit_data("Firefighter suit", storage_id=storage.id))

    await contamination_team_service.equip_hazard_outfits(async_session, room.vault_id, [dweller], HazardTeam.FIRE)

    equipped = await crud.outfit.get_equipped(async_session, dweller.id)
    assert equipped is not None
    assert equipped.name == "Firefighter suit"


@pytest.mark.asyncio
async def test_no_spare_outfit_leaves_unchanged(async_session: AsyncSession, room_with_dwellers: dict):
    """No spare matching outfit means the dweller keeps whatever they had."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    await contamination_team_service.equip_hazard_outfits(async_session, room.vault_id, [dweller], HazardTeam.FIRE)

    assert await crud.outfit.get_equipped(async_session, dweller.id) is None


@pytest.mark.asyncio
async def test_bench_member_not_equipped(async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict):
    """Only active gainers are equipped; a bench qualifier keeps no outfit."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(
                async_session,
                obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
            )
        )
    for _ in range(QUALIFYING_INCIDENTS - 1):
        await _fight(async_session, room, IncidentType.FIRE, dwellers)
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=room.vault_id)
    for _ in range(TEAM_SIZE):
        await crud.outfit.create(async_session, _outfit_data("Firefighter suit", storage_id=storage.id))

    incident = await _raise_incident(async_session, room, IncidentType.FIRE)
    result = await contamination_team_service.record_participation(async_session, incident, dwellers)
    await async_session.commit()

    assert len(result.active_gainers) == TEAM_SIZE
    await contamination_team_service.equip_hazard_outfits(
        async_session, room.vault_id, result.active_gainers, HazardTeam.FIRE
    )

    roster = await crud.hazard_team_crud.get_team(async_session, room.vault_id, HazardTeam.FIRE)
    bench = next(place for place in roster if place.status == RESERVE_STATUS)
    assert await crud.outfit.get_equipped(async_session, bench.dweller_id) is None
    for dweller in result.active_gainers:
        equipped = await crud.outfit.get_equipped(async_session, dweller.id)
        assert equipped is not None
        assert equipped.name == "Firefighter suit"


@pytest.mark.asyncio
async def test_already_wearing_target_unchanged(async_session: AsyncSession, room_with_dwellers: dict):
    """A dweller already wearing the target keeps it and the spare stays put."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=room.vault_id)
    worn = await crud.outfit.create(async_session, _outfit_data("Firefighter suit", dweller_id=dweller.id))
    spare = await crud.outfit.create(async_session, _outfit_data("Firefighter suit", storage_id=storage.id))

    await contamination_team_service.equip_hazard_outfits(async_session, room.vault_id, [dweller], HazardTeam.FIRE)

    equipped = await crud.outfit.get_equipped(async_session, dweller.id)
    assert equipped.id == worn.id
    spare_after = await crud.outfit.get(async_session, spare.id)
    assert spare_after.dweller_id is None
