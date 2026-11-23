from unittest.mock import patch

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam, IncidentObjective, IncidentType
from app.core.game_config import game_config
from app.models.incident import get_incident_definition
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.schemas.dweller import DwellerCreate
from app.services.combat.incident_math import split_proportional
from app.services.combat.incident_round import apply_damage
from app.services.combat.incident_service import incident_service
from app.services.hazard_team_service import QUALIFYING_INCIDENTS, TEAM_RESPONSE_BONUS, TEAM_SIZE, hazard_team_service
from app.tests.test_services._hazard_team_helpers import fight, full_health, make_member, outfit_data, raise_incident
from app.utils.combat import combat_power


async def _full_team(async_session, room_with_dwellers, dweller_data):
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(
                async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id)
            )
        )
    return dwellers


async def _active(async_session, room, dweller, team=HazardTeam.FIRE):
    await make_member(async_session, room.vault_id, dweller.id, team, ACTIVE_STATUS)


async def _equipped(async_session, dweller):
    return await crud.outfit.get_equipped(async_session, dweller.id)


@pytest.mark.parametrize(
    ("incident_type", "attribute", "expected"),
    [(IncidentType.FIRE, "health", (60, 50)), (IncidentType.RADSCORPION_ATTACK, "radiation", (16, 25))],
)
async def test_active_member_takes_less_damage(async_session, room_with_dwellers, incident_type, attribute, expected):
    room, dwellers = room_with_dwellers["room"], room_with_dwellers["dwellers"]
    await full_health(async_session, dwellers)
    incident = await raise_incident(async_session, room, incident_type)

    _, _, taken = await apply_damage(
        async_session, incident, dwellers, 100.0, active_member_ids=frozenset({dwellers[0].id})
    )

    if attribute == "health":
        assert taken == 90
    assert (getattr(dwellers[0], attribute), getattr(dwellers[1], attribute)) == expected


async def test_faction_and_team_reductions_truncate_once(async_session, room_with_dwellers, monkeypatch):
    # Per-source truncation yields int(int(3 * 0.85) * 0.8) = 1; combining first yields 2.
    monkeypatch.setattr(game_config.features, "faction_mechanics", True)
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    dweller.health = 100
    dweller.max_health = 100
    dweller.visual_attributes = {"faction": "minutemen"}
    async_session.add(dweller)
    await async_session.commit()

    incident = await raise_incident(async_session, room, IncidentType.FIRE)
    _, _, taken = await apply_damage(async_session, incident, [dweller], 3.0, active_member_ids=frozenset({dweller.id}))

    assert int(int(3 * (1 - 0.15)) * (1 - 0.20)) == 1
    assert taken == 2
    assert dweller.health == 98


@pytest.mark.parametrize(
    ("incident_type", "member_team", "expected_power"),
    [
        (IncidentType.FIRE, HazardTeam.FIRE, int(100 * (1 + TEAM_RESPONSE_BONUS))),
        (IncidentType.RAIDER_ATTACK, HazardTeam.FIRE, 100),
        (IncidentType.FIRE, HazardTeam.RADIATION, 100),
    ],
)
async def test_active_member_response_bonus(
    async_session, room_with_dwellers, incident_type, member_team, expected_power
):
    room, dwellers = room_with_dwellers["room"], room_with_dwellers["dwellers"]
    await _active(async_session, room, dwellers[0], member_team)
    incident = await raise_incident(async_session, room, incident_type)

    containment = get_incident_definition(incident_type).objective == IncidentObjective.CONTAIN
    power_fn = "containment_progress" if containment else "damage_to_raiders"
    damage_fn = "containment_damage" if containment else "damage_to_dwellers"
    with (
        patch("app.services.combat.incident_math.dweller_combat_power", return_value=100.0),
        patch(f"app.services.combat.incident_math.{power_fn}", return_value=0.0) as mock_power,
        patch(f"app.services.combat.incident_math.{damage_fn}", return_value=0.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    assert mock_power.call_args.args[0] == expected_power


async def test_attack_shares_match_the_total_power_model(async_session, room_with_dwellers):
    # The bonus scales the round total once; attributing it again per attacker would
    # make the journal lines disagree with that total.
    room, dwellers = room_with_dwellers["room"], room_with_dwellers["dwellers"]
    await _active(async_session, room, dwellers[0], HazardTeam.RADIATION)
    incident = await raise_incident(async_session, room, IncidentType.RADSCORPION_ATTACK)

    with (
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=0.0),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=20.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    events = await crud.incident_crud.get_recent_events(async_session, incident.id)
    threat_hits = [event for event in events if event.data and "damage_to_threat" in event.data]

    assert [event.data["damage_to_threat"] for event in reversed(threat_hits)] == split_proportional(
        20, [combat_power(dweller) for dweller in dwellers]
    )


@pytest.mark.parametrize("mode", ["spare", "none", "worn"])
async def test_equip_hazard_outfit_targets_spares_only(async_session, room_with_dwellers, mode):
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=room.vault_id)
    worn = spare_id = None
    if mode == "spare":
        await crud.outfit.create(async_session, outfit_data("Firefighter suit", storage_id=storage.id))
    if mode == "worn":
        worn = await crud.outfit.create(async_session, outfit_data("Firefighter suit", dweller_id=dweller.id))
        spare = await crud.outfit.create(async_session, outfit_data("Firefighter suit", storage_id=storage.id))
        spare_id = spare.id

    await hazard_team_service.equip_hazard_outfits(async_session, room.vault_id, [dweller], HazardTeam.FIRE)

    equipped = await _equipped(async_session, dweller)
    if mode == "none":
        assert equipped is None
        return
    assert equipped is not None
    assert equipped.name == "Firefighter suit"
    if mode == "worn":
        assert equipped.id == worn.id
        spare_after = await crud.outfit.get(async_session, spare_id)
        assert spare_after.dweller_id is None


async def test_bench_member_not_equipped(async_session, room_with_dwellers, dweller_data):
    room = room_with_dwellers["room"]
    dwellers = await _full_team(async_session, room_with_dwellers, dweller_data)
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
    assert await _equipped(async_session, bench) is None
    active_ids = await crud.team_crud.get_active_hazard_member_ids(
        async_session, room.vault_id, HazardTeam.FIRE, [dweller.id for dweller in dwellers]
    )
    assert len(active_ids) == TEAM_SIZE
    assert dwellers[TEAM_SIZE].id not in active_ids
    for dweller in result.active_gainers:
        equipped = await _equipped(async_session, dweller)
        assert equipped is not None
        assert equipped.name == "Firefighter suit"


async def test_equip_failure_does_not_abort_batch(async_session, room_with_dwellers, monkeypatch):
    room, dwellers = room_with_dwellers["room"], room_with_dwellers["dwellers"]
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


async def test_failed_notification_flush_does_not_poison_the_round(async_session, room_with_dwellers):
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]

    async def failing_send(*args, **kwargs):
        await async_session.execute(text("SELECT 1 FROM table_that_does_not_exist"))

    with patch("app.services.notification_service.NotificationService.create_and_send", new=failing_send):
        for _ in range(QUALIFYING_INCIDENTS):
            await fight(async_session, room, IncidentType.FIRE, [dweller])

    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place is not None
    assert place.status == ACTIVE_STATUS


async def test_fallen_member_is_benched_not_left_slotless_active(async_session, room_with_dwellers):
    room, dwellers = room_with_dwellers["room"], room_with_dwellers["dwellers"]
    await _active(async_session, room, dwellers[0])
    roster = await crud.team_crud.get_hazard_team(async_session, room.vault_id, HazardTeam.FIRE)
    roster[0].slot_number = 1
    fallen = await crud.dweller.get(async_session, dwellers[0].id)
    fallen.is_dead = True
    async_session.add_all([roster[0], fallen])
    await async_session.commit()

    await crud.team_crud.free_dead_hazard_slots(async_session, room.vault_id, HazardTeam.FIRE)

    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dwellers[0].id)
    assert place is not None
    assert place.slot_number is None
    assert place.status == RESERVE_STATUS
    assert await crud.team_crud.count_active_hazard(async_session, room.vault_id, HazardTeam.FIRE) == 0
