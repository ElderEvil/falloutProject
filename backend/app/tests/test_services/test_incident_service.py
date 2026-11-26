from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import (
    AgeGroupEnum,
    DwellerStatusEnum,
    IncidentFamily,
    IncidentObjective,
    IncidentStatus,
    IncidentType,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.core.game_config import game_config
from app.models.game_state import GameState
from app.models.incident_event import IncidentEvent
from app.models.quest import Quest
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.incident import IncidentRoundResult
from app.schemas.quest import QuestCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.combat import incident_math
from app.services.combat.incident_service import incident_service
from app.services.dweller_service import dweller_service
from app.services.team_service import team_service
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException, ValidationException
from app.utils.time import utcnow

DMG_DWELLERS = "app.services.combat.incident_math.damage_to_dwellers"
DMG_RAIDERS = "app.services.combat.incident_math.damage_to_raiders"
PROGRESS = "app.services.combat.incident_math.containment_progress"
NOTIFY_WS = "app.services.notification_service.manager"
NOTIFY_SSE = "app.services.notification_service.sse_manager"


@pytest_asyncio.fixture(name="room")
async def room_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    return await crud.room.create(async_session, RoomCreate(**create_fake_room(), vault_id=vault.id))


def create_test_room() -> dict:
    """A room that is NOT an elevator, arena, or response station (so an incident can spawn)."""
    room_data = create_fake_room()
    # get_occupied_rooms (the spawner's candidate set) excludes elevators by name
    # and arenas/response stations by category, so a wave-continuation spawn needs
    # both rooms eligible.
    while room_data["name"] == "Elevator" or room_data["category"] in (RoomTypeEnum.ARENA, RoomTypeEnum.RESPONSE):
        room_data = create_fake_room()
    return room_data


def response_station_room(vault_id, *, coordinate_x: int, coordinate_y: int, size: int = 3) -> RoomCreate:
    return RoomCreate(
        name="Response Station",
        category=RoomTypeEnum.RESPONSE,
        ability="Endurance",
        population_required=None,
        base_cost=600,
        incremental_cost=None,
        t2_upgrade_cost=None,
        t3_upgrade_cost=None,
        size_min=3,
        size_max=9,
        size=size,
        tier=1,
        vault_id=vault_id,
        coordinate_x=coordinate_x,
        coordinate_y=coordinate_y,
    )


async def _dweller(session, vault_id, data, **extra):
    return await crud.dweller.create(session, obj_in=DwellerCreate(**{**data, **extra}, vault_id=vault_id))


async def _room(session, vault_id, x, y, **extra):
    return await crud.room.create(
        session, RoomCreate(**create_test_room(), vault_id=vault_id, coordinate_x=x, coordinate_y=y, **extra)
    )


async def _production_room(session, vault_id, name, x, y, ability=SPECIALEnum.STRENGTH):
    return await crud.room.create(
        session,
        RoomCreate(
            name=name,
            category=RoomTypeEnum.PRODUCTION,
            ability=ability,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=3,
            size_max=6,
            coordinate_x=x,
            coordinate_y=y,
            vault_id=vault_id,
        ),
    )


async def _incident(session, room, incident_type, difficulty=2, **extra):
    return await crud.incident_crud.create(
        session, vault_id=room.vault_id, room_id=room.id, incident_type=incident_type, difficulty=difficulty, **extra
    )


async def _commit(session, *objs):
    for obj in objs:
        session.add(obj)
    await session.commit()


async def _active_count(session, vault_id):
    return len(await crud.incident_crud.get_active_by_vault(session, vault_id))


async def _spawn(session, vault_id, incident_type=IncidentType.FIRE):
    incident = await incident_service.spawn_incident(session, vault_id, incident_type)
    assert incident is not None
    return incident


async def _occupant(session, vault_id, room_id, data):
    """A dweller standing in the room, so it is a spawn (or spread) candidate."""
    dweller = await _dweller(session, vault_id, data)
    dweller.room_id = room_id
    session.add(dweller)
    await session.commit()
    return dweller


async def _arena_room(session, vault_id):
    return await crud.room.create(
        session,
        RoomCreate(
            name="Arena",
            category=RoomTypeEnum.ARENA,
            ability="Strength",
            population_required=20,
            base_cost=800,
            incremental_cost=200,
            t2_upgrade_cost=3000,
            t3_upgrade_cost=9000,
            size_min=6,
            size_max=6,
            size=6,
            tier=1,
            vault_id=vault_id,
            coordinate_x=0,
            coordinate_y=1,
        ),
    )


@contextmanager
def _damage(dwellers: float, raiders: float = 0.0):
    with patch(DMG_DWELLERS, return_value=dwellers), patch(DMG_RAIDERS, return_value=raiders):
        yield


async def _assign_quest_to_vault(session, vault):
    quest = await crud.quest_crud.create(
        session,
        obj_in=QuestCreate(
            title="Coexist Quest",
            short_description="Send a team",
            long_description="A quest that needs a team roster.",
            requirements="1 dweller",
            rewards="100 caps",
            duration_minutes=60,
        ),
    )
    await crud.quest_crud.assign_to_vault(session, quest.id, vault.id, is_visible=True)
    return quest


@pytest.mark.asyncio
async def test_spawn_incident_no_rooms(async_session, vault):
    assert await incident_service.spawn_incident(async_session, vault.id) is None


@pytest.mark.asyncio
async def test_runtime_spawn_rolls_from_the_balance_weights(async_session, room_with_dwellers):
    room = room_with_dwellers["room"]
    with patch("app.services.combat.incident_spawning.random.choices", return_value=[IncidentType.FIRE]) as chooser:
        incident = await incident_service.spawn_incident(async_session, room.vault_id)
    assert incident is not None
    assert incident.type == IncidentType.FIRE
    vault = await crud.vault.get(async_session, room.vault_id)
    population = await crud.dweller.count_living_in_vault(async_session, room.vault_id)
    expected = game_config.incident.get_spawn_weights(population, vault.vault_mode)
    assert chooser.call_args.kwargs["weights"] == list(expected.values())


@pytest.mark.asyncio
async def test_runtime_spawn_continues_the_active_wave(async_session, vault, dweller_data):
    for index in range(2):
        room = await _room(async_session, vault.id, index + 1, 1)
        dweller = await _dweller(async_session, vault.id, dweller_data)
        await dweller_service.move_to_room(async_session, dweller.id, room.id)
    await async_session.commit()
    first = await _spawn(async_session, vault.id, IncidentType.MOLE_RAT_ATTACK)
    with patch("app.services.combat.incident_spawning.random.choices", side_effect=AssertionError("rolled mid-wave")):
        second = await incident_service.spawn_incident(async_session, vault.id)
    assert second is not None
    assert second.type == first.type == IncidentType.MOLE_RAT_ATTACK


@pytest.mark.asyncio
@pytest.mark.parametrize("excluded_kind", ["arena", "response_station"])
async def test_incident_never_spawns_in_an_excluded_room(async_session, vault, dweller_data, excluded_kind):
    if excluded_kind == "arena":
        excluded = await _arena_room(async_session, vault.id)
    else:
        excluded = await crud.room.create(
            async_session, response_station_room(vault.id, coordinate_x=1, coordinate_y=1)
        )
    await _occupant(async_session, vault.id, excluded.id, dweller_data)
    incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.RADROACH_INFESTATION)
    assert incident is None


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_kind", ["arena", "response_station"])
async def test_incident_does_not_spread_into_an_excluded_room(async_session, vault, blocked_kind):
    source = await _room(async_session, vault.id, 6, 1)
    if blocked_kind == "arena":
        blocked = await _room(async_session, vault.id, 6, 2)
        blocked.category = RoomTypeEnum.ARENA
        blocked.name = "Arena"
        await _commit(async_session, blocked)
    else:
        blocked = await crud.room.create(async_session, response_station_room(vault.id, coordinate_x=6, coordinate_y=2))
    incident = await _incident(async_session, source, IncidentType.RADROACH_INFESTATION)
    adjacent = await crud.room.get_adjacent_rooms(
        async_session, vault.id, exclude_room_id=source.id, coord_x=6, coord_y=1
    )
    assert blocked.id not in {room.id for room in adjacent}
    await incident_service._spread_incident(async_session, incident)
    assert blocked.id not in await crud.incident_crud.get_rooms_with_active_incidents(async_session, vault.id)


@pytest.mark.asyncio
async def test_incident_read_returns_the_latest_journal_entries(async_session, room_with_dwellers):
    room = room_with_dwellers["room"]
    incident = await _incident(async_session, room, IncidentType.RAIDER_ATTACK, 3)
    started = utcnow()
    for index in range(45):
        async_session.add(
            IncidentEvent(
                incident_id=incident.id,
                kind="round",
                message=f"Round {index}",
                created_at=started + timedelta(seconds=index),
            )
        )
    await async_session.commit()
    read = await incident_service.get_incident_read(async_session, incident, room.name)
    assert [event.message for event in read.events] == [f"Round {index}" for index in range(5, 45)]


@pytest.mark.asyncio
@pytest.mark.parametrize("hazard", [IncidentType.FIRE, IncidentType.RAIDER_ATTACK])
async def test_incident_read_pins_objective_progress(async_session, room_with_dwellers, hazard):
    room = room_with_dwellers["room"]
    incident = await _incident(async_session, room, hazard, 3)
    if hazard == IncidentType.FIRE:
        incident.combat_progress = 0.5
        await _commit(async_session, incident)
        read = await incident_service.get_incident_read(async_session, incident, room.name)
        assert (read.progress.current, read.progress.target, read.progress.label) == (50, 100, "Fire contained")
        assert (read.family, read.objective) == (IncidentFamily.HAZARD, IncidentObjective.CONTAIN)
        assert read.response.label == "Send responders"
        assert (read.risk.kind, read.risk.rooms_affected) == ("spread", 1)
    else:
        incident.enemies_defeated = 2
        await _commit(async_session, incident)
        read = await incident_service.get_incident_read(async_session, incident, room.name)
        assert (read.progress.current, read.progress.target) == (2, 6)
        assert read.progress.label == "Intruders neutralized"
        assert (read.family, read.objective) == (IncidentFamily.INTRUSION, IncidentObjective.DEFEAT)


@pytest.mark.asyncio
async def test_get_incident_for_vault_contract(async_session, room_with_dwellers):
    room = room_with_dwellers["room"]
    incident = await _incident(async_session, room, IncidentType.FIRE, 1)
    fetched = await incident_service.get_incident_for_vault(async_session, incident.id, room.vault_id)
    assert fetched.id == incident.id
    with pytest.raises(AccessDeniedException, match="does not belong"):
        await incident_service.get_incident_for_vault(async_session, incident.id, uuid4())
    with pytest.raises(ResourceNotFoundException):
        await incident_service.get_incident_for_vault(async_session, uuid4(), room.vault_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(("damage", "expected_health"), [(5.0, [98, 97]), (1.0, [99, 100])])
async def test_process_incident_distributes_all_integer_damage(
    async_session, room_with_dwellers, damage, expected_health
):
    room, dwellers = room_with_dwellers["room"], room_with_dwellers["dwellers"]
    for dweller in dwellers:
        dweller.health = dweller.max_health = 100
        await _commit(async_session, dweller)
    incident = await _spawn(async_session, room.vault_id, IncidentType.RADROACH_INFESTATION)
    with patch(DMG_DWELLERS, return_value=damage), patch(DMG_RAIDERS, return_value=0.0):
        result = await incident_service.process_incident(async_session, incident, 2)
    for dweller in dwellers:
        await async_session.refresh(dweller)
    await async_session.refresh(incident)
    assert sorted(dweller.health for dweller in dwellers) == sorted(expected_health)
    assert result.dwellers_damaged == min(int(damage), len(dwellers))
    assert incident.damage_dealt == int(damage)


@pytest.mark.asyncio
async def test_radscorpion_deals_health_and_radiation_damage(async_session, room_with_dwellers):
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    dweller.health = dweller.max_health = 100
    dweller.radiation = 0
    await _commit(async_session, dweller)
    incident = await _spawn(async_session, room.vault_id, IncidentType.RADSCORPION_ATTACK)
    with patch(DMG_DWELLERS, return_value=20.0), patch(DMG_RAIDERS, return_value=0.0):
        result = await incident_service.process_incident(async_session, incident, 2)
    await async_session.refresh(dweller)
    assert result.dwellers_damaged == 2
    assert dweller.health == 90
    assert dweller.radiation == 5
    assert dweller.radiation < 10


@pytest.mark.asyncio
async def test_process_incident_does_not_damage_child(async_session, room_with_dwellers, dweller_data):
    # Children in an incident room do not join combat or receive combat damage.
    room = room_with_dwellers["room"]
    child = await _dweller(
        async_session, room.vault_id, dweller_data, age_group=AgeGroupEnum.CHILD, health=100, max_health=100
    )
    await async_session.commit()
    incident = await _spawn(async_session, room.vault_id, IncidentType.FIRE)
    await incident_service.process_incident(async_session, incident, 60)
    await async_session.refresh(child)
    assert child.health == 100


@pytest.mark.asyncio
async def test_round_failure_leaves_no_partial_state(async_session, room_with_dwellers):
    # A crash inside the round must not persist damage or deaths (single-commit round).
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    dweller.health = 5
    dweller.max_health = 100
    await _commit(async_session, dweller)
    incident = await _spawn(async_session, room.vault_id, IncidentType.RADROACH_INFESTATION)
    with (
        _damage(20.0),
        patch("app.services.combat.incident_publishing.record_events", side_effect=SQLAlchemyError("event boom")),
        patch(NOTIFY_WS) as mock_ws,
        patch(NOTIFY_SSE) as mock_sse,
        pytest.raises(SQLAlchemyError, match="event boom"),
    ):
        await incident_service.process_incident(async_session, incident, 2)
    await async_session.rollback()
    await async_session.refresh(dweller)
    assert not dweller.is_dead
    assert dweller.health == 5
    mock_ws.send_personal_message.assert_not_called()
    mock_sse.publish.assert_not_called()


@pytest.mark.asyncio
async def test_fatal_round_delivers_death_notification_after_commit(async_session, room_with_dwellers):
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    dweller.visual_attributes = {"race": "synth", "state_of_being": "gen_1"}
    dweller.health = 5
    dweller.max_health = 100
    await _commit(async_session, dweller)
    incident = await _spawn(async_session, room.vault_id, IncidentType.RADROACH_INFESTATION)
    with _damage(20.0), patch(NOTIFY_WS) as mock_ws, patch(NOTIFY_SSE) as mock_sse:
        await incident_service.process_incident(async_session, incident, 2)
    await async_session.refresh(dweller)
    assert dweller.is_dead
    assert mock_ws.send_personal_message.call_count >= 1
    assert mock_sse.publish.call_count >= 1
    events = (
        await async_session.execute(select(IncidentEvent).where(IncidentEvent.incident_id == incident.id))
    ).scalars()
    hit = next(event.data["action"] for event in events if event.data and event.data.get("target") == "dweller")
    assert hit["targets"][0]["body"] == "synth"


@pytest.mark.asyncio
async def test_generate_loot(async_session):
    # A hazard pays in experience: no caps, no loot, however severe.
    loot_low = incident_math.generate_loot(difficulty=1, incident_type=IncidentType.FIRE)
    assert loot_low["caps"] == 0
    assert loot_low["items"] == []
    # An intrusion pays caps scaled by difficulty.
    loot_high = incident_math.generate_loot(difficulty=10, incident_type=IncidentType.RAIDER_ATTACK)
    assert 250 <= loot_high["caps"] <= 525


@pytest.mark.asyncio
async def test_assign_responders_moves_persists_and_appends_the_roster(async_session, room_with_dwellers, dweller_data):
    room = room_with_dwellers["room"]
    first, second = [await _dweller(async_session, room.vault_id, dweller_data) for _ in range(2)]
    incident = await _spawn(async_session, room.vault_id)
    assigned = await incident_service.assign_responders(async_session, incident, [first.id])
    await async_session.refresh(first)
    assert assigned == [first.id]
    assert first.room_id == room.id
    team = await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id)
    assert team is not None
    assert team.quest_id is None
    assert team.incident_id == incident.id
    assert [member.dweller_id for member in team.members] == [first.id]
    assert all(member.slot_number is None for member in team.members)
    assert all(member.status == "assigned" for member in team.members)
    members = await crud.team_crud.get_incident_team(async_session, incident.id, room.vault_id)
    assert [member.dweller_id for member in members] == [first.id]

    # Re-sending the first responder alongside a new one must append, not replace or duplicate.
    await incident_service.assign_responders(async_session, incident, [first.id, second.id])
    team = await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id)
    assert team is not None
    assert sorted(member.dweller_id for member in team.members) == sorted([first.id, second.id])


@pytest.mark.asyncio
async def test_assign_responders_skips_committed_and_errors_when_all_committed(
    async_session, room_with_dwellers, dweller_data
):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    committed, free = [await _dweller(async_session, vault.id, dweller_data) for _ in range(2)]
    first = await _incident(async_session, room, IncidentType.FIRE)
    await incident_service.assign_responders(async_session, first, [committed.id])
    second = await _incident(async_session, room, IncidentType.FIRE)
    # The committed responder is skipped; the free one is assigned.
    assert await incident_service.assign_responders(async_session, second, [committed.id, free.id]) == [free.id]
    team = await crud.team_crud.get_incident_team_row(async_session, second.id, vault.id)
    assert team is not None
    assert [member.dweller_id for member in team.members] == [free.id]
    events = await crud.incident_crud.get_recent_events(async_session, second.id)
    assert next(event for event in events if event.kind == "responders_assigned").data == {
        "skipped": [committed.first_name]
    }
    # When every chosen responder is committed elsewhere, assignment raises a 400 naming the conflict.
    with pytest.raises(ValidationException) as excinfo:
        await incident_service.assign_responders(async_session, second, [committed.id])
    assert "committed" in str(excinfo.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(("count", "rejected"), [(6, False), (7, True)])
async def test_assign_responders_enforces_the_six_responder_cap(
    async_session, room_with_dwellers, dweller_data, count, rejected
):
    room = room_with_dwellers["room"]
    responders = [await _dweller(async_session, room.vault_id, dweller_data) for _ in range(count)]
    incident = await _spawn(async_session, room.vault_id)
    if rejected:
        with pytest.raises(ValidationException, match="at most 6"):
            await incident_service.assign_responders(async_session, incident, [r.id for r in responders])
        assert await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id) is None
        return
    assigned = await incident_service.assign_responders(async_session, incident, [r.id for r in responders])
    assert len(assigned) == 6
    team = await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id)
    assert team is not None
    assert len(team.members) == 6


@pytest.mark.asyncio
async def test_assign_responders_rejects_roster_overflow(async_session, room_with_dwellers, dweller_data):
    room = room_with_dwellers["room"]
    first_five = [await _dweller(async_session, room.vault_id, dweller_data) for _ in range(5)]
    two_more = [await _dweller(async_session, room.vault_id, dweller_data) for _ in range(2)]
    incident = await _spawn(async_session, room.vault_id)
    await incident_service.assign_responders(async_session, incident, [r.id for r in first_five])
    with pytest.raises(ValidationException, match="at most 6"):
        await incident_service.assign_responders(async_session, incident, [r.id for r in two_more])
    # The existing roster is untouched.
    team = await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id)
    assert team is not None
    assert len(team.members) == 5


@pytest.mark.asyncio
async def test_assign_responders_revalidates_status_under_lock(async_session, room_with_dwellers, dweller_data):
    # assign_responders reloads the incident FOR UPDATE; the live row wins over a stale caller object.
    room = room_with_dwellers["room"]
    responder = await _dweller(async_session, room.vault_id, dweller_data)
    incident = await _spawn(async_session, room.vault_id)
    incident.status = IncidentStatus.RESOLVED
    await _commit(async_session, incident)
    incident.status = IncidentStatus.ACTIVE  # stale caller-side view
    with pytest.raises(ValidationException, match="no longer active"):
        await incident_service.assign_responders(async_session, incident, [responder.id])


@pytest.mark.asyncio
async def test_deleting_incident_cascades_its_team(async_session, room_with_dwellers, dweller_data):
    room = room_with_dwellers["room"]
    responder = await _dweller(async_session, room.vault_id, dweller_data)
    incident = await _spawn(async_session, room.vault_id)
    await incident_service.assign_responders(async_session, incident, [responder.id])
    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id) is not None
    await crud.incident_crud.remove(async_session, incident.id)
    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id) is None


@pytest.mark.asyncio
async def test_quest_and_incident_teams_coexist(async_session, room_with_dwellers, dweller_data):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    quest = await _assign_quest_to_vault(async_session, vault)
    quest_dweller, responder = [await _dweller(async_session, vault.id, dweller_data) for _ in range(2)]
    await team_service.assign_quest_team(async_session, quest.id, vault.id, [quest_dweller.id])
    incident = await _spawn(async_session, vault.id)
    await incident_service.assign_responders(async_session, incident, [responder.id])
    quest_team = await crud.team_crud.get_quest_team_row(async_session, quest.id, vault.id)
    incident_team = await crud.team_crud.get_incident_team_row(async_session, incident.id, vault.id)
    assert quest_team is not None
    assert incident_team is not None
    assert quest_team.id != incident_team.id
    assert quest_team.incident_id is None
    assert incident_team.quest_id is None


@pytest.mark.asyncio
async def test_assign_responders_rejections_write_no_team(async_session, room_with_dwellers, dweller_data):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    incident = await _spawn(async_session, vault.id)
    # A wounded dweller is rejected.
    wounded = await _dweller(async_session, vault.id, dweller_data)
    wounded.health = 0
    await _commit(async_session, wounded)
    with pytest.raises(ValidationException, match="healthy"):
        await incident_service.assign_responders(async_session, incident, [wounded.id])
    # Duplicate ids are rejected.
    healthy = await _dweller(async_session, vault.id, dweller_data)
    with pytest.raises(ValidationException, match="only once"):
        await incident_service.assign_responders(async_session, incident, [healthy.id, healthy.id])
    # An empty selection is rejected.
    with pytest.raises(ValidationException, match="at least one"):
        await incident_service.assign_responders(async_session, incident, [])
    # A dweller from another vault is rejected.
    other_user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    other_vault = await crud.vault.create(
        async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=other_user.id)
    )
    foreign = await _dweller(async_session, other_vault.id, dweller_data)
    with pytest.raises(ValidationException, match="do not belong"):
        await incident_service.assign_responders(async_session, incident, [foreign.id])
    # An inactive incident is rejected.
    incident.status = IncidentStatus.RESOLVED
    await _commit(async_session, incident)
    with pytest.raises(ValidationException, match="no longer active"):
        await incident_service.assign_responders(async_session, incident, [healthy.id])
    # No team row was written by any rejected assignment.
    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, vault.id) is None


@pytest.mark.asyncio
async def test_only_one_incident_type_per_vault(async_session, vault, dweller_data):
    rooms = [
        await _production_room(async_session, vault.id, name, index + 1, 1)
        for index, name in enumerate(("Power Generator", "Water Treatment", "Diner"))
    ]
    for room in rooms:
        dweller = await _dweller(async_session, vault.id, dweller_data)
        await dweller_service.move_to_room(async_session, dweller.id, room.id)
    await async_session.commit()
    fire_incident = await _spawn(async_session, vault.id, IncidentType.FIRE)
    assert fire_incident.type == IncidentType.FIRE
    # A different type must not spawn while the wave is active.
    assert await incident_service.spawn_incident(async_session, vault.id, IncidentType.RAIDER_ATTACK) is None
    # Another FIRE may spawn in a different room.
    fire_incident2 = await _spawn(async_session, vault.id, IncidentType.FIRE)
    assert fire_incident2.type == IncidentType.FIRE
    assert fire_incident2.id != fire_incident.id


@pytest.mark.asyncio
async def test_spread_skips_elevator(async_session, vault, dweller_data):
    incident_room = await _production_room(async_session, vault.id, "Reactor", 1, 1)
    elevator_in = RoomCreate(
        name="Elevator",
        category="Misc.",
        ability=None,
        t2_upgrade_cost=None,
        t3_upgrade_cost=None,
        base_cost=100,
        size_min=1,
        size_max=1,
        tier=1,
        vault_id=vault.id,
        coordinate_x=2,
        coordinate_y=1,
    )
    elevator = await crud.room.create(async_session, elevator_in)
    normal_room = await _production_room(async_session, vault.id, "Diner", 1, 2)
    await _dweller(async_session, vault.id, dweller_data)
    await async_session.commit()
    incident = await _incident(async_session, incident_room, IncidentType.FIRE, 5)
    await incident_service._spread_incident(async_session, incident)
    active_incidents = await crud.incident_crud.get_active_by_vault(async_session, vault.id)
    for inc in active_incidents:
        assert inc.room_id != elevator.id
    if len(active_incidents) > 1:
        spread_incident = next(inc for inc in active_incidents if inc.id != incident.id)
        assert spread_incident.room_id == normal_room.id


@pytest.mark.asyncio
async def test_spread_respects_active_incident_cap(async_session, vault):
    current_room = await _production_room(async_session, vault.id, "Power Generator", 1, 1)
    await _production_room(async_session, vault.id, "Diner", 2, 1, ability=SPECIALEnum.AGILITY)
    active_incident = await _incident(async_session, current_room, IncidentType.FIRE, 5)
    for index in range(game_config.incident.max_active_incidents - 1):
        room = await _production_room(async_session, vault.id, f"Room {index}", index + 4, 4)
        await _incident(async_session, room, IncidentType.FIRE, 1)
    cap = game_config.incident.max_active_incidents
    assert await _active_count(async_session, vault.id) == cap
    assert await incident_service._spread_incident(async_session, active_incident) is False
    assert await _active_count(async_session, vault.id) == cap


class TestProcessVaultIncidents:
    @pytest.mark.asyncio
    async def test_spawns_new_incident_without_processing_it(self, async_session, vault):
        mock_incident = MagicMock()
        mock_incident.type = "raider_attack"
        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=True),
            patch.object(incident_service, "spawn_incident", new_callable=AsyncMock, return_value=mock_incident),
            patch.object(incident_service, "process_incident", new_callable=AsyncMock) as mock_process,
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[])
            mock_crud.get_pending_responder_returns = AsyncMock(return_value=[])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert result["spawned"] == 1
        assert result["active_count"] == 0
        mock_process.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", ["offline", "paused", "persisted_pause"])
    async def test_inactive_vault_does_not_process_existing_incidents(self, async_session, vault, mode):
        game_state = None
        if mode == "offline":
            game_state = GameState(vault_id=vault.id, last_activity_time=utcnow() - timedelta(minutes=11))
        elif mode == "paused":
            game_state = GameState(vault_id=vault.id, is_paused=True)
        else:
            # The fast-tick actor path passes no game_state; persisted pause must still hold.
            async_session.add(GameState(vault_id=vault.id, is_paused=True))
            await async_session.commit()
        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock) as mock_spawn,
            patch.object(incident_service, "process_incident", new_callable=AsyncMock) as mock_process,
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[MagicMock()])
            mock_crud.get_pending_responder_returns = AsyncMock(return_value=[])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2, game_state)
        assert result["active_count"] == 1
        mock_spawn.assert_not_called()
        mock_process.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("round_result", "processed"), [("resolved", 1), ("skipped", 0)])
    async def test_processes_active_round_results(self, async_session, vault, round_result, processed):
        mock_incident = MagicMock()
        mock_incident.status = MagicMock()
        mock_incident.status.value = "resolved"
        mock_incident.id = "inc-1"
        outcome = (
            IncidentRoundResult(caps_earned=50) if round_result == "resolved" else IncidentRoundResult(skipped=True)
        )
        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
            patch.object(incident_service, "process_incident", new_callable=AsyncMock, return_value=outcome),
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
            patch.object(async_session, "refresh", new_callable=AsyncMock),
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[mock_incident])
            mock_crud.get_pending_responder_returns = AsyncMock(return_value=[])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert result["active_count"] == 1
        assert result["processed"] == processed
        if processed:
            assert result["resolved"] == 1
            assert result["caps_earned"] == 50

    @pytest.mark.asyncio
    async def test_error_in_one_does_not_stop(self, async_session, vault):
        inc1, inc2 = MagicMock(), MagicMock()
        inc1.id = "inc-1"
        inc2.id = "inc-2"
        inc2.status = MagicMock()
        inc2.status.value = "active"
        call_count = [0]

        async def process_side_effect(db_session, incident, seconds_passed):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("Simulated error")
            return IncidentRoundResult()

        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
            patch.object(incident_service, "process_incident", new_callable=AsyncMock, side_effect=process_side_effect),
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
            patch.object(async_session, "refresh", new_callable=AsyncMock),
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[inc1, inc2])
            mock_crud.get_pending_responder_returns = AsyncMock(return_value=[])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert result["active_count"] == 2
        # The first incident raised, but processing must continue to the second.
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_outer_exception_set_error(self, async_session, vault):
        with patch.object(
            incident_service,
            "should_spawn_incident",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("DB down"),
        ):
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert "error" in result


@pytest.mark.asyncio
async def test_disabled_vault_neither_spawns_nor_processes(async_session, vault):
    vault.incidents_disabled = True
    await async_session.commit()
    assert await incident_service.should_spawn_incident(async_session, vault.id, 3600) is False
    with (
        patch.object(incident_service, "spawn_incident", new_callable=AsyncMock) as mock_spawn,
        patch.object(incident_service, "process_incident", new_callable=AsyncMock) as mock_process,
    ):
        result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
    assert result["active_count"] == 0
    mock_spawn.assert_not_awaited()
    mock_process.assert_not_awaited()


class TestTickCommitBoundaries:
    """Pins the transaction boundaries of one incident tick; consolidation must prove them equivalent."""

    @pytest.mark.asyncio
    async def test_quiet_round_commits_exactly_once(self, async_session, room_with_dwellers):
        vault = room_with_dwellers["vault"]
        incident = await _spawn(async_session, vault.id)
        with (
            patch.object(async_session, "commit", wraps=async_session.commit) as commit_spy,
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
            _damage(0.0),
            patch(PROGRESS, return_value=0.0),
        ):
            stats = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert stats["processed"] == 1
        assert stats["caps_earned"] == 0
        assert commit_spy.await_count == 1

    @pytest.mark.asyncio
    async def test_spawn_commits_activation_before_notification(self, async_session, room_with_dwellers):
        vault = room_with_dwellers["vault"]
        with (
            patch.object(async_session, "commit", wraps=async_session.commit) as commit_spy,
            patch(NOTIFY_WS),
            patch(NOTIFY_SSE),
        ):
            incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
        assert incident is not None
        assert commit_spy.await_count == 2

    @pytest.mark.asyncio
    async def test_victory_commits_round_notification_then_deposit(self, async_session, room_with_dwellers):
        vault = room_with_dwellers["vault"]
        for dweller in room_with_dwellers["dwellers"]:
            dweller.level = game_config.leveling.max_level  # keep level-up commits out of this count
            async_session.add(dweller)
        await async_session.commit()
        incident = await _spawn(async_session, vault.id, IncidentType.RADROACH_INFESTATION)
        with (
            patch.object(async_session, "commit", wraps=async_session.commit) as commit_spy,
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
            _damage(0.0, 1000.0),
            patch(NOTIFY_WS),
            patch(NOTIFY_SSE),
        ):
            stats = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert stats["resolved"] == 1
        assert stats["caps_earned"] > 0
        assert commit_spy.await_count == 4


@pytest.mark.asyncio
async def test_failed_incident_rolls_back_before_the_next_one(async_session, vault):
    # SQLite does not poison a session on a failed statement the way PostgreSQL does,
    # so this pins the recovery call itself rather than its downstream symptom.
    async def poison(*_args, **_kwargs):
        await async_session.execute(text("SELECT 1 FROM table_that_does_not_exist"))

    with (
        patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
        patch.object(incident_service, "process_incident", new=poison),
        patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
        patch.object(async_session, "rollback", new=AsyncMock(wraps=async_session.rollback)) as rollback_spy,
    ):
        mock_crud.get_active_by_vault = AsyncMock(return_value=[MagicMock()])
        mock_crud.get_pending_responder_returns = AsyncMock(return_value=[])
        result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
    assert result["active_count"] == 1
    rollback_spy.assert_awaited()


@pytest.mark.parametrize("enabled", [False, True])
async def test_spawn_honors_pause_on_incident_preference(async_session, room_with_dwellers, enabled):
    from app.crud import game_state_crud
    from app.crud.user_profile import profile_crud

    room = room_with_dwellers["room"]
    vault = await crud.vault.get(async_session, room.vault_id)
    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    if profile is None:
        profile = await profile_crud.create_for_user(async_session, vault.user_id)
    profile.preferences = {"pause_on_incident": enabled}
    await async_session.commit()
    incident = await _spawn(async_session, vault.id)
    state = await game_state_crud.get_by_vault_id(async_session, vault.id)
    assert bool(state and state.is_paused) is enabled
    if enabled:
        stats = await incident_service.process_vault_incidents(async_session, vault.id, 60)
        assert stats["processed"] == 0
        await async_session.refresh(incident)
        assert incident.combat_progress == 0


async def test_auto_pause_does_not_commit_before_incident_insert(async_session, room_with_dwellers):
    # Creating the first game state must not release the spawn lock before inserting its incident.
    from sqlalchemy import event

    from app.crud.user_profile import profile_crud
    from app.models.incident import Incident

    vault = await crud.vault.get(async_session, room_with_dwellers["room"].vault_id)
    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    if profile is None:
        profile = await profile_crud.create_for_user(async_session, vault.user_id)
    profile.preferences = {"pause_on_incident": True}
    await async_session.commit()
    commits = []

    def before_commit(session):
        commits.append(
            session.execute(select(Incident).where(Incident.vault_id == vault.id)).scalar_one_or_none() is not None
        )

    event.listen(async_session.sync_session, "before_commit", before_commit)
    try:
        incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    finally:
        event.remove(async_session.sync_session, "before_commit", before_commit)
    assert incident is not None
    assert commits[0], "The first commit must insert the incident, keeping the spawn lock through all checks."


async def test_incident_cannot_draft_residents_defending_another_room(async_session, room_with_dwellers):
    room = room_with_dwellers["room"]
    resident = room_with_dwellers["dwellers"][0]
    other_room = await _room(async_session, room.vault_id, 10, 2)
    await _incident(async_session, room, IncidentType.RAIDER_ATTACK, 4)
    other = await _incident(async_session, other_room, IncidentType.RAIDER_ATTACK, 4)
    with pytest.raises(ValidationException, match="committed"):
        await incident_service.assign_responders(async_session, other, [resident.id])
    await async_session.refresh(resident)
    assert resident.room_id == room.id
    assert await crud.team_crud.get_incident_team(async_session, other.id, room.vault_id) == []


async def test_current_residents_do_not_consume_helper_slots(async_session, room_with_dwellers, dweller_data):
    room = room_with_dwellers["room"]
    resident = room_with_dwellers["dwellers"][0]
    helper = await _dweller(async_session, room.vault_id, dweller_data)
    incident = await _incident(async_session, room, IncidentType.RAIDER_ATTACK, 4)
    assigned = await incident_service.assign_responders(async_session, incident, [resident.id, helper.id])
    assert assigned == [helper.id]
    members = await crud.team_crud.get_incident_team(async_session, incident.id, room.vault_id)
    assert [member.dweller_id for member in members] == [helper.id]
    assert resident.room_id == helper.room_id == room.id
    events = await crud.incident_crud.get_recent_events(async_session, incident.id)
    assigned_event = next(event for event in events if event.kind == "responders_assigned")
    assert assigned_event.data == {"skipped": [resident.first_name]}


async def test_residents_and_six_helpers_all_fight_without_replacing_each_other(
    async_session, room_with_dwellers, dweller_data
):
    room = room_with_dwellers["room"]
    residents = room_with_dwellers["dwellers"]
    helpers = [await _dweller(async_session, room.vault_id, dweller_data) for _ in range(6)]
    for dweller in [*residents, *helpers]:
        dweller.health = dweller.max_health = 1000
        dweller.radiation = 0
        await _commit(async_session, dweller)
    incident = await _incident(async_session, room, IncidentType.RAIDER_ATTACK, 100)
    await incident_service.assign_responders(async_session, incident, [helper.id for helper in helpers])
    result = await incident_service.process_incident(async_session, incident, 2)
    assert not result.no_defenders
    for dweller in [*residents, *helpers]:
        await async_session.refresh(dweller)
        assert 0 < dweller.health < 1000
        assert dweller.room_id == room.id
    members = await crud.team_crud.get_incident_team(async_session, incident.id, room.vault_id)
    assert {member.dweller_id for member in members} == {helper.id for helper in helpers}


async def test_incident_does_not_pull_a_fighter_out_of_arena(async_session, room_with_dwellers, dweller_data):
    room = room_with_dwellers["room"]
    helper = await _dweller(async_session, room.vault_id, dweller_data)
    helper.status = DwellerStatusEnum.FIGHTING
    await _commit(async_session, helper)
    incident = await _incident(async_session, room, IncidentType.RAIDER_ATTACK, 4)
    with pytest.raises(ValidationException, match="healthy adult"):
        await incident_service.assign_responders(async_session, incident, [helper.id])
    assert helper.status == DwellerStatusEnum.FIGHTING
    assert await crud.team_crud.get_incident_team(async_session, incident.id, room.vault_id) == []
