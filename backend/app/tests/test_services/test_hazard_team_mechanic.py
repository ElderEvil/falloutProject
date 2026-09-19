"""Hazard-team mechanic: response bonus, damage resist, and auto-equip."""

from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.core.game_config import game_config
from app.models.incident import IncidentType
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.schemas.dweller import DwellerCreate
from app.services.combat.incident_round import apply_damage
from app.services.combat.incident_service import incident_service
from app.services.hazard_team_service import (
    QUALIFYING_INCIDENTS,
    TEAM_RESPONSE_BONUS,
    TEAM_SIZE,
    hazard_team_service,
)
from app.tests.test_services._hazard_team_helpers import fight, full_health, make_member, outfit_data, raise_incident


@pytest.mark.asyncio
async def test_active_member_takes_less_damage(async_session: AsyncSession, room_with_dwellers: dict):
    """An active matching member takes the hazard-resist share off their damage."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    await full_health(async_session, dwellers)
    incident = await raise_incident(async_session, room, IncidentType.FIRE)
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
    await full_health(async_session, dwellers)
    incident = await raise_incident(async_session, room, IncidentType.RADSCORPION_ATTACK)
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
        await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, status)

    active_ids = await crud.team_crud.get_active_hazard_member_ids(
        async_session, room.vault_id, HazardTeam.FIRE, [dweller.id for dweller in dwellers]
    )

    assert len(active_ids) == TEAM_SIZE
    assert dwellers[TEAM_SIZE].id not in active_ids


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("incident_type", "member_team", "expected_power"),
    [
        (IncidentType.FIRE, HazardTeam.FIRE, int(100 * (1 + TEAM_RESPONSE_BONUS))),
        (IncidentType.RAIDER_ATTACK, HazardTeam.FIRE, 100),
        (IncidentType.FIRE, HazardTeam.RADIATION, 100),
    ],
)
async def test_active_member_response_bonus(
    async_session: AsyncSession,
    room_with_dwellers: dict,
    incident_type: IncidentType,
    member_team: HazardTeam,
    expected_power: int,
):
    """Only active members of the matching team add response power to the round."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    await make_member(async_session, room.vault_id, dwellers[0].id, member_team, ACTIVE_STATUS)
    incident = await raise_incident(async_session, room, incident_type)

    is_fire = incident_type == IncidentType.FIRE
    power_fn = "fire_suppression" if is_fire else "damage_to_raiders"
    damage_fn = "fire_damage" if is_fire else "damage_to_dwellers"
    with (
        patch("app.services.combat.incident_math.dweller_combat_power", return_value=100.0),
        patch(f"app.services.combat.incident_math.{power_fn}", return_value=0.0) as mock_power,
        patch(f"app.services.combat.incident_math.{damage_fn}", return_value=0.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    assert mock_power.call_args.args[0] == expected_power


@pytest.mark.asyncio
async def test_active_gainer_with_spare_outfit_gets_equipped(async_session: AsyncSession, room_with_dwellers: dict):
    """A newly-active member wears the spare matching outfit from storage."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=room.vault_id)
    await crud.outfit.create(async_session, outfit_data("Firefighter suit", storage_id=storage.id))

    await hazard_team_service.equip_hazard_outfits(async_session, room.vault_id, [dweller], HazardTeam.FIRE)

    equipped = await crud.outfit.get_equipped(async_session, dweller.id)
    assert equipped is not None
    assert equipped.name == "Firefighter suit"


@pytest.mark.asyncio
async def test_no_spare_outfit_leaves_unchanged(async_session: AsyncSession, room_with_dwellers: dict):
    """No spare matching outfit means the dweller keeps whatever they had."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    await hazard_team_service.equip_hazard_outfits(async_session, room.vault_id, [dweller], HazardTeam.FIRE)

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
        await fight(async_session, room, IncidentType.FIRE, dwellers)
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=room.vault_id)
    for _ in range(TEAM_SIZE):
        await crud.outfit.create(async_session, outfit_data("Firefighter suit", storage_id=storage.id))

    incident = await raise_incident(async_session, room, IncidentType.FIRE)
    result = await hazard_team_service.record_participation(async_session, incident, dwellers)
    await async_session.commit()

    assert len(result.active_gainers) == TEAM_SIZE
    await hazard_team_service.equip_hazard_outfits(async_session, room.vault_id, result.active_gainers, HazardTeam.FIRE)

    roster = await crud.team_crud.get_hazard_team(async_session, room.vault_id, HazardTeam.FIRE)
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
    worn = await crud.outfit.create(async_session, outfit_data("Firefighter suit", dweller_id=dweller.id))
    spare = await crud.outfit.create(async_session, outfit_data("Firefighter suit", storage_id=storage.id))

    await hazard_team_service.equip_hazard_outfits(async_session, room.vault_id, [dweller], HazardTeam.FIRE)

    equipped = await crud.outfit.get_equipped(async_session, dweller.id)
    assert equipped.id == worn.id
    spare_after = await crud.outfit.get(async_session, spare.id)
    assert spare_after.dweller_id is None


@pytest.mark.asyncio
async def test_equip_failure_does_not_abort_batch(
    async_session: AsyncSession, room_with_dwellers: dict, monkeypatch: pytest.MonkeyPatch
):
    """One failed auto-equip is contained; the remaining members still get their outfit."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=room.vault_id)
    for _ in dwellers:
        await crud.outfit.create(async_session, outfit_data("Firefighter suit", storage_id=storage.id))

    original_equip = crud.outfit.equip
    calls = {"count": 0}

    async def flaky_equip(*, db_session, item_id, dweller_id):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("equip boom")
        return await original_equip(db_session=db_session, item_id=item_id, dweller_id=dweller_id)

    monkeypatch.setattr(crud.outfit, "equip", flaky_equip)

    dweller_ids = [dweller.id for dweller in dwellers]
    await hazard_team_service.equip_hazard_outfits(async_session, room.vault_id, dwellers, HazardTeam.FIRE)

    assert calls["count"] == len(dwellers)
    equipped = [await crud.outfit.get_equipped(async_session, dweller_id) for dweller_id in dweller_ids]
    assert equipped[0] is None
    assert all(item is not None for item in equipped[1:])


@pytest.mark.asyncio
async def test_failed_notification_flush_does_not_poison_the_round(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """A deferred notification that errors rolls back to its savepoint, so the round still commits."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    async def failing_send(*args, **kwargs):
        await async_session.execute(text("SELECT 1 FROM table_that_does_not_exist"))

    with patch("app.services.notification_service.NotificationService.create_and_send", new=failing_send):
        for _ in range(QUALIFYING_INCIDENTS):
            await fight(async_session, room, IncidentType.FIRE, [dweller])

    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place is not None
    assert place.status == ACTIVE_STATUS


@pytest.mark.asyncio
async def test_fallen_member_is_benched_not_left_slotless_active(async_session: AsyncSession, room_with_dwellers: dict):
    """A fallen member frees their slot and drops to the bench, so a revival cannot re-add a place."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    await make_member(async_session, room.vault_id, dwellers[0].id, HazardTeam.FIRE, ACTIVE_STATUS)
    roster = await crud.team_crud.get_hazard_team(async_session, room.vault_id, HazardTeam.FIRE)
    roster[0].slot_number = 1
    async_session.add(roster[0])
    await async_session.commit()

    fallen = await crud.dweller.get(async_session, dwellers[0].id)
    fallen.is_dead = True
    async_session.add(fallen)
    await async_session.commit()

    await crud.team_crud.free_dead_hazard_slots(async_session, room.vault_id, HazardTeam.FIRE)

    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dwellers[0].id)
    assert place is not None
    assert place.slot_number is None
    assert place.status == RESERVE_STATUS
    assert await crud.team_crud.count_active_hazard(async_session, room.vault_id, HazardTeam.FIRE) == 0


@pytest.mark.asyncio
async def test_faction_and_team_reductions_truncate_once(
    async_session: AsyncSession, room_with_dwellers: dict, monkeypatch: pytest.MonkeyPatch
):
    """Two reductions on one channel combine as complements, then truncate once.

    Applied per source, 3 fire damage with 0.15 faction response and 0.20 team resist
    truncates twice: int(int(3 * 0.85) * 0.8) = 1. The resolver combines first:
    int(3 * 0.85 * 0.8) = 2. Pinned through the real combat path, not just the
    resolver unit, so a change to how apply_damage composes cannot slip past it.
    """
    monkeypatch.setattr(game_config.features, "faction_mechanics", True)
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    dweller.health = 100
    dweller.max_health = 100
    dweller.visual_attributes = {"faction": "minutemen"}
    async_session.add(dweller)
    await async_session.commit()

    incident = await raise_incident(async_session, room, IncidentType.FIRE)
    _, _, taken = await apply_damage(
        async_session, incident, [dweller], 3.0, active_member_ids=frozenset({dweller.id})
    )

    assert int(int(3 * (1 - 0.15)) * (1 - 0.20)) == 1  # what per-source truncation produced
    assert taken == 2
    assert dweller.health == 98
