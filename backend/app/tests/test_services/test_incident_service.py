"""Tests for incident service logic."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.game_state import GameState
from app.models.incident import IncidentFamily, IncidentObjective, IncidentStatus, IncidentType
from app.models.incident_event import IncidentEvent
from app.models.quest import Quest
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.incident import IncidentRoundResult
from app.schemas.quest import QuestCreate
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


@pytest_asyncio.fixture(name="room")
async def room_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    """Create a test room."""
    from app.schemas.room import RoomCreate

    room_data = create_fake_room()
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    return await crud.room.create(db_session=async_session, obj_in=room_in)


def create_test_room() -> dict:
    """Create a test room that is NOT an elevator or arena (ensures incident can spawn)."""
    room_data = create_fake_room()
    # get_occupied_rooms (the spawner's candidate set) excludes elevators by name
    # and arenas by category, so a wave-continuation spawn needs both rooms eligible.
    while room_data["name"] == "Elevator" or room_data["category"] == RoomTypeEnum.ARENA:
        room_data = create_fake_room()
    return room_data


@pytest.mark.asyncio
async def test_spawn_incident_no_rooms(async_session: AsyncSession, vault: Vault):
    """Test that no incident spawns when there are no occupied rooms."""
    incident = await incident_service.spawn_incident(async_session, vault.id)
    assert incident is None


@pytest.mark.asyncio
async def test_runtime_spawn_rolls_from_the_balance_weights(async_session: AsyncSession, room_with_dwellers: dict):
    """A no-type spawn picks a weighted type instead of always radscorpions."""
    room = room_with_dwellers["room"]

    with patch("app.services.combat.incident_spawning.random.choices", return_value=[IncidentType.FIRE]) as chooser:
        incident = await incident_service.spawn_incident(async_session, room.vault_id)

    assert incident is not None
    assert incident.type == IncidentType.FIRE
    assert chooser.call_args.kwargs["weights"] == list(game_config.incident.get_spawn_weights().values())


@pytest.mark.asyncio
async def test_runtime_spawn_continues_the_active_wave(async_session: AsyncSession, vault: Vault, dweller_data: dict):
    """A vault already fighting a hazard spawns more of it without rolling again."""
    from app.schemas.room import RoomCreate

    for index in range(2):
        room = await crud.room.create(
            async_session,
            RoomCreate(**create_test_room(), vault_id=vault.id, coordinate_x=index + 1, coordinate_y=1),
        )
        dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
        await dweller_service.move_to_room(async_session, dweller.id, room.id)
    await async_session.commit()

    first = await incident_service.spawn_incident(async_session, vault.id, IncidentType.MOLE_RAT_ATTACK)
    assert first is not None

    with patch(
        "app.services.combat.incident_spawning.random.choices",
        side_effect=AssertionError("rolled a new type mid-wave"),
    ):
        second = await incident_service.spawn_incident(async_session, vault.id)

    assert second is not None
    assert second.type == IncidentType.MOLE_RAT_ATTACK


@pytest.mark.asyncio
async def test_spawn_storm_stops_at_the_active_incident_cap(
    async_session: AsyncSession,
    room_with_dwellers: dict,
    dweller_data: dict,
):
    """Recreate the Aug 2026 radroach storm's growth: once the active-incident cap
    is full, further spawn attempts are refused, so rapidly-lost incidents cannot
    pile up unboundedly (each would otherwise fire a COMBAT_DEFEAT notification)."""
    vault = room_with_dwellers["vault"]

    # Population gate: bring the vault to the incident minimum (fixture gives 2).
    for _ in range(game_config.incident.min_vault_population - len(room_with_dwellers["dwellers"])):
        dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
        async_session.add(dweller)
    await async_session.commit()

    # Fill the active-incident cap with fresh radroach incidents past the cooldown.
    for _ in range(game_config.incident.max_active_incidents):
        incident = await crud.incident_crud.create(
            async_session,
            vault_id=vault.id,
            room_id=room_with_dwellers["room"].id,
            incident_type=IncidentType.RADROACH_INFESTATION,
            difficulty=1,
        )
        incident.start_time = datetime.utcnow() - timedelta(seconds=game_config.incident.spawn_cooldown_seconds + 1)
        async_session.add(incident)
    await async_session.commit()

    active = await crud.incident_crud.get_active_by_vault(async_session, vault.id)
    assert len(active) == game_config.incident.max_active_incidents

    # Storm: rapid spawn attempts must all be refused while the cap is full.
    for _ in range(20):
        assert await incident_service.should_spawn_incident(async_session, vault.id, 3600) is False

    after = await crud.incident_crud.get_active_by_vault(async_session, vault.id)
    assert len(after) == game_config.incident.max_active_incidents


@pytest.mark.asyncio
async def test_incident_never_spawns_in_an_arena(async_session: AsyncSession, vault: Vault):
    """An arena hosts matches; an incident there has no correct UI to open."""
    from app.schemas.room import RoomCreate

    arena = await crud.room.create(
        db_session=async_session,
        obj_in=RoomCreate(
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
            vault_id=vault.id,
            coordinate_x=0,
            coordinate_y=1,
        ),
    )
    dweller_in = DwellerCreate(
        first_name="Gladiator",
        last_name="Dweller",
        gender="male",
        rarity="common",
        vault_id=vault.id,
        room_id=arena.id,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
    )
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    dweller.room_id = arena.id
    async_session.add(dweller)
    await async_session.commit()

    incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.RADROACH_INFESTATION)

    assert incident is None


@pytest.mark.asyncio
async def test_incident_does_not_spread_into_an_arena(async_session: AsyncSession, vault: Vault):
    """A spread must not carry an incident into an arena either."""
    from app.schemas.room import RoomCreate

    source = await crud.room.create(
        db_session=async_session,
        obj_in=RoomCreate(**create_test_room(), vault_id=vault.id, coordinate_x=6, coordinate_y=1),
    )
    arena = await crud.room.create(
        db_session=async_session,
        obj_in=RoomCreate(**create_test_room(), vault_id=vault.id, coordinate_x=6, coordinate_y=2),
    )
    arena.category = RoomTypeEnum.ARENA
    arena.name = "Arena"
    async_session.add(arena)
    await async_session.commit()

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=source.id,
        incident_type=IncidentType.RADROACH_INFESTATION,
        difficulty=2,
    )

    adjacent = await crud.room.get_adjacent_rooms(
        async_session, vault.id, exclude_room_id=source.id, coord_x=6, coord_y=1
    )

    assert arena.id not in {room.id for room in adjacent}


@pytest.mark.asyncio
async def test_incident_read_returns_the_latest_journal_entries(async_session: AsyncSession, room_with_dwellers: dict):
    """The compact UI journal must not get stuck on a long incident's opening rounds."""
    room = room_with_dwellers["room"]
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.RAIDER_ATTACK,
        difficulty=3,
    )
    started = datetime.utcnow()
    for index in range(25):
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

    assert [event.message for event in read.events] == [f"Round {index}" for index in range(5, 25)]


@pytest.mark.asyncio
async def test_incident_read_pins_fire_containment_progress(async_session: AsyncSession, room_with_dwellers: dict):
    """FIRE progress reports containment percentage against a fixed target of 100."""
    room = room_with_dwellers["room"]
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=3,
    )
    incident.combat_progress = 0.5
    async_session.add(incident)
    await async_session.commit()

    read = await incident_service.get_incident_read(async_session, incident, room.name)

    assert read.progress.current == 50
    assert read.progress.target == 100
    assert read.progress.label == "Fire contained"
    assert read.family == IncidentFamily.HAZARD
    assert read.objective == IncidentObjective.CONTAIN
    assert read.response.label == "Send responders"
    assert read.risk.kind == "spread"
    assert read.risk.rooms_affected == 1


@pytest.mark.asyncio
async def test_incident_read_pins_combat_kill_progress(async_session: AsyncSession, room_with_dwellers: dict):
    """Combat progress reports enemies defeated against difficulty * 2 raiders."""
    room = room_with_dwellers["room"]
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.RAIDER_ATTACK,
        difficulty=3,
    )
    incident.enemies_defeated = 2
    async_session.add(incident)
    await async_session.commit()

    read = await incident_service.get_incident_read(async_session, incident, room.name)

    assert read.progress.current == 2
    assert read.progress.target == 6
    assert read.progress.label == "Intruders neutralized"
    assert read.family == IncidentFamily.INTRUSION
    assert read.objective == IncidentObjective.DEFEAT


@pytest.mark.asyncio
async def test_get_incident_for_vault_returns_owned_incident(async_session: AsyncSession, room_with_dwellers: dict):
    """An incident belonging to the requesting vault is returned as-is."""
    room = room_with_dwellers["room"]
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=1,
    )

    fetched = await incident_service.get_incident_for_vault(async_session, incident.id, room.vault_id)

    assert fetched.id == incident.id


@pytest.mark.asyncio
async def test_get_incident_for_vault_rejects_other_vault(async_session: AsyncSession, room_with_dwellers: dict):
    """An incident from another vault is denied."""
    room = room_with_dwellers["room"]
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=1,
    )

    with pytest.raises(AccessDeniedException, match="does not belong"):
        await incident_service.get_incident_for_vault(async_session, incident.id, uuid4())


@pytest.mark.asyncio
async def test_get_incident_for_vault_missing_raises_not_found(async_session: AsyncSession, vault: Vault):
    """An unknown incident id raises not-found."""
    with pytest.raises(ResourceNotFoundException):
        await incident_service.get_incident_for_vault(async_session, uuid4(), vault.id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("damage", "expected_health"),
    [
        (5.0, [98, 97]),
        (1.0, [99, 100]),
    ],
)
async def test_process_incident_distributes_all_integer_damage(
    async_session: AsyncSession,
    room_with_dwellers: dict,
    damage: float,
    expected_health: list[int],
):
    """Each integer point of a damage tick is assigned to a dweller."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    for dweller in dwellers:
        dweller.health = 100
        dweller.max_health = 100
        async_session.add(dweller)
    await async_session.commit()

    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.RADROACH_INFESTATION)
    assert incident is not None

    with (
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=damage),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=0.0),
    ):
        result = await incident_service.process_incident(async_session, incident, 2)

    for dweller in dwellers:
        await async_session.refresh(dweller)
    await async_session.refresh(incident)

    assert sorted(dweller.health for dweller in dwellers) == sorted(expected_health)
    assert result.dwellers_damaged == min(int(damage), len(dwellers))
    assert incident.damage_dealt == int(damage)


@pytest.mark.asyncio
async def test_radscorpion_deals_health_and_radiation_damage(async_session: AsyncSession, room_with_dwellers: dict):
    """Radscorpions damage HP and add radiation during the same combat round."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    dweller.health = 100
    dweller.max_health = 100
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.commit()

    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.RADSCORPION_ATTACK)
    assert incident is not None

    with (
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=20.0),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=0.0),
    ):
        result = await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(dweller)
    assert result.dwellers_damaged == 2
    assert dweller.health == 90
    assert dweller.radiation == 5
    assert dweller.radiation < 10


@pytest.mark.asyncio
async def test_process_incident_does_not_damage_child(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """Children in an incident room do not join combat or receive combat damage."""
    room = room_with_dwellers["room"]
    child_data = {
        **dweller_data,
        "is_adult": False,
        "age_group": AgeGroupEnum.CHILD,
        "health": 100,
        "max_health": 100,
    }
    child = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**child_data, vault_id=room.vault_id, room_id=room.id),
    )
    await async_session.commit()

    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None
    await incident_service.process_incident(async_session, incident, 60)

    await async_session.refresh(child)
    assert child.health == 100


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_round_failure_leaves_no_partial_state(async_session: AsyncSession, room_with_dwellers: dict):
    """A crash inside the round must not persist damage or deaths (single-commit round).

    Rollback after a mid-round failure shows the dweller exactly as before the
    round: the killing blow and the death marker were pending, not committed.
    """
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    dweller.health = 5
    dweller.max_health = 100
    async_session.add(dweller)
    await async_session.commit()

    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.RADROACH_INFESTATION)
    assert incident is not None

    with (
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=20.0),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=0.0),
        patch("app.services.combat.incident_publishing.record_event", side_effect=SQLAlchemyError("event boom")),
        patch("app.services.notification_service.manager") as mock_ws,
        patch("app.services.notification_service.sse_manager") as mock_sse,
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
async def test_fatal_round_delivers_death_notification_after_commit(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """A killing blow notifies the owner only after the round commit lands."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    dweller.health = 5
    dweller.max_health = 100
    async_session.add(dweller)
    await async_session.commit()

    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.RADROACH_INFESTATION)
    assert incident is not None

    with (
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=20.0),
        patch("app.services.combat.incident_math.damage_to_raiders", return_value=0.0),
        patch("app.services.notification_service.manager") as mock_ws,
        patch("app.services.notification_service.sse_manager") as mock_sse,
    ):
        await incident_service.process_incident(async_session, incident, 2)

    await async_session.refresh(dweller)
    assert dweller.is_dead
    assert mock_ws.send_personal_message.call_count >= 1
    assert mock_sse.publish.call_count >= 1


@pytest.mark.asyncio
async def test_generate_loot(async_session: AsyncSession, vault: Vault):
    """Test loot generation for different difficulties."""
    # A hazard pays in experience: no caps, no loot, however severe.
    loot_low = incident_math.generate_loot(difficulty=1, incident_type=IncidentType.FIRE)
    assert loot_low["caps"] == 0
    assert loot_low["items"] == []

    # An intrusion pays caps scaled by difficulty.
    loot_high = incident_math.generate_loot(difficulty=10, incident_type=IncidentType.RAIDER_ATTACK)
    assert loot_high["caps"] >= 250
    assert loot_high["caps"] <= 525


@pytest.mark.asyncio
async def test_assign_responders_moves_healthy_adult(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A healthy adult can join an active incident room before the next round."""
    room = room_with_dwellers["room"]
    responder = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id),
    )
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None
    assigned = await incident_service.assign_responders(async_session, incident, [responder.id])

    await async_session.refresh(responder)
    assert assigned == [responder.id]
    assert responder.room_id == room.id


async def _assign_quest_to_vault(async_session: AsyncSession, vault: Vault) -> Quest:
    """Assign a fresh quest to the vault so a quest team can be created."""
    quest = await crud.quest_crud.create(
        async_session,
        obj_in=QuestCreate(
            title="Coexist Quest",
            short_description="Send a team",
            long_description="A quest that needs a team roster.",
            requirements="1 dweller",
            rewards="100 caps",
            duration_minutes=60,
        ),
    )
    await crud.quest_crud.assign_to_vault(async_session, quest.id, vault.id, is_visible=True)
    return quest


@pytest.mark.asyncio
async def test_assign_responders_persists_incident_team(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """Assigning responders records the incident's designated team roster."""
    room = room_with_dwellers["room"]
    responder = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id),
    )
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None

    await incident_service.assign_responders(async_session, incident, [responder.id])

    team = await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id)
    assert team is not None
    assert team.quest_id is None
    assert team.incident_id == incident.id
    assert [member.dweller_id for member in team.members] == [responder.id]
    assert all(member.slot_number is None for member in team.members)
    assert all(member.status == "assigned" for member in team.members)


@pytest.mark.asyncio
async def test_assign_responders_appends_to_roster(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A second assignment keeps prior members, adds new ones, and ignores duplicates."""
    room = room_with_dwellers["room"]
    responder1 = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
    responder2 = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None

    await incident_service.assign_responders(async_session, incident, [responder1.id])
    # Re-sending responder1 alongside a new responder2 must append, not replace or duplicate.
    await incident_service.assign_responders(async_session, incident, [responder1.id, responder2.id])

    team = await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id)
    assert team is not None
    assert sorted(member.dweller_id for member in team.members) == sorted([responder1.id, responder2.id])


@pytest.mark.asyncio
async def test_assign_responders_accepts_six_responders(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A full six-responder roster is accepted."""
    room = room_with_dwellers["room"]
    responders = [
        await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
        for _ in range(6)
    ]
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None

    assigned = await incident_service.assign_responders(
        async_session, incident, [responder.id for responder in responders]
    )

    assert len(assigned) == 6
    team = await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id)
    assert team is not None
    assert len(team.members) == 6


@pytest.mark.asyncio
async def test_assign_responders_rejects_seventh_responder(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A seventh responder is rejected and writes no team."""
    room = room_with_dwellers["room"]
    responders = [
        await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
        for _ in range(7)
    ]
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None

    with pytest.raises(ValidationException, match="at most 6"):
        await incident_service.assign_responders(async_session, incident, [responder.id for responder in responders])

    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id) is None


@pytest.mark.asyncio
async def test_assign_responders_rejects_roster_overflow(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """Adding two responders to an existing five-responder roster is rejected."""
    room = room_with_dwellers["room"]
    first_five = [
        await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
        for _ in range(5)
    ]
    two_more = [
        await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
        for _ in range(2)
    ]
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None

    await incident_service.assign_responders(async_session, incident, [responder.id for responder in first_five])

    with pytest.raises(ValidationException, match="at most 6"):
        await incident_service.assign_responders(async_session, incident, [responder.id for responder in two_more])

    # The existing roster is untouched.
    team = await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id)
    assert team is not None
    assert len(team.members) == 5


@pytest.mark.asyncio
async def test_assign_responders_reloads_incident_for_update(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict, monkeypatch: pytest.MonkeyPatch
):
    """The roster read and cap check run under a FOR UPDATE re-load of the incident row."""
    room = room_with_dwellers["room"]
    responder = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None

    from app.crud.incident import incident_crud

    locked_ids: list = []
    original = incident_crud.get_for_update

    async def spy(db_session, incident_id):
        locked_ids.append(incident_id)
        return await original(db_session, incident_id)

    monkeypatch.setattr(incident_crud, "get_for_update", spy)

    await incident_service.assign_responders(async_session, incident, [responder.id])

    assert locked_ids == [incident.id]


@pytest.mark.asyncio
async def test_assign_responders_revalidates_status_under_lock(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A caller's stale incident object cannot bypass the locked row's status."""
    room = room_with_dwellers["room"]
    responder = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None

    # The caller holds an ACTIVE object, but the row is already resolved.
    incident.status = IncidentStatus.RESOLVED
    async_session.add(incident)
    await async_session.commit()
    incident.status = IncidentStatus.ACTIVE  # stale caller-side view

    with pytest.raises(ValidationException, match="no longer active"):
        await incident_service.assign_responders(async_session, incident, [responder.id])


@pytest.mark.asyncio
async def test_deleting_incident_cascades_its_team(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """Deleting an incident removes its team row and members via the ORM cascade."""
    room = room_with_dwellers["room"]
    responder = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None
    await incident_service.assign_responders(async_session, incident, [responder.id])

    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id) is not None

    await crud.incident_crud.remove(async_session, incident.id)

    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id) is None


@pytest.mark.asyncio
async def test_incident_team_retrievable_via_crud(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """The persisted incident team is retrievable through team_crud.get_incident_team."""
    room = room_with_dwellers["room"]
    responder = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id))
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    assert incident is not None
    await incident_service.assign_responders(async_session, incident, [responder.id])

    members = await crud.team_crud.get_incident_team(async_session, incident.id, room.vault_id)
    assert [member.dweller_id for member in members] == [responder.id]


@pytest.mark.asyncio
async def test_quest_and_incident_teams_coexist(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A quest team and an incident team coexist as separate team rows."""
    room = room_with_dwellers["room"]
    vault = room_with_dwellers["vault"]
    quest = await _assign_quest_to_vault(async_session, vault)
    quest_dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    responder = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))

    await team_service.assign_quest_team(async_session, quest.id, vault.id, [quest_dweller.id])
    incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident is not None
    await incident_service.assign_responders(async_session, incident, [responder.id])

    quest_team = await crud.team_crud.get_quest_team_row(async_session, quest.id, vault.id)
    incident_team = await crud.team_crud.get_incident_team_row(async_session, incident.id, vault.id)
    assert quest_team is not None
    assert incident_team is not None
    assert quest_team.id != incident_team.id
    assert quest_team.incident_id is None
    assert incident_team.quest_id is None


@pytest.mark.asyncio
async def test_assign_responders_rejections_write_no_team(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """Unhealthy, duplicate, foreign-vault, and inactive-incident rejections write no team."""
    room = room_with_dwellers["room"]
    vault = room_with_dwellers["vault"]
    incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident is not None

    # A wounded dweller is rejected.
    wounded = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    wounded.health = 0
    async_session.add(wounded)
    await async_session.commit()
    with pytest.raises(ValidationException, match="healthy"):
        await incident_service.assign_responders(async_session, incident, [wounded.id])

    # Duplicate ids are rejected.
    healthy = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
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
    foreign = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=other_vault.id))
    with pytest.raises(ValidationException, match="do not belong"):
        await incident_service.assign_responders(async_session, incident, [foreign.id])

    # An inactive incident is rejected.
    incident.status = IncidentStatus.RESOLVED
    async_session.add(incident)
    await async_session.commit()
    with pytest.raises(ValidationException, match="no longer active"):
        await incident_service.assign_responders(async_session, incident, [healthy.id])

    # No team row was written by any rejected assignment.
    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, vault.id) is None


@pytest.mark.asyncio
async def test_only_one_incident_type_per_vault(async_session: AsyncSession, vault: Vault, dweller_data: dict):
    """Test that only one incident type can be active in a vault at once."""
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    # Create three separate rooms with dwellers (need 3+ rooms for multiple incidents)
    room1_data = create_fake_room()
    room1_data["category"] = "Production"
    room1_in = RoomCreate(**room1_data, vault_id=vault.id, coordinate_x=1, coordinate_y=1)
    room1 = await crud.room.create(db_session=async_session, obj_in=room1_in)

    room2_data = create_fake_room()
    room2_data["category"] = "Production"
    room2_in = RoomCreate(**room2_data, vault_id=vault.id, coordinate_x=2, coordinate_y=1)
    room2 = await crud.room.create(db_session=async_session, obj_in=room2_in)

    room3_data = create_fake_room()
    room3_data["category"] = "Production"
    room3_in = RoomCreate(**room3_data, vault_id=vault.id, coordinate_x=3, coordinate_y=1)
    room3 = await crud.room.create(db_session=async_session, obj_in=room3_in)

    # Add dwellers to all rooms
    dweller1_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller1 = await crud.dweller.create(db_session=async_session, obj_in=dweller1_in)
    await dweller_service.move_to_room(async_session, dweller1.id, room1.id)

    dweller2_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller2 = await crud.dweller.create(db_session=async_session, obj_in=dweller2_in)
    await dweller_service.move_to_room(async_session, dweller2.id, room2.id)

    dweller3_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller3 = await crud.dweller.create(db_session=async_session, obj_in=dweller3_in)
    await dweller_service.move_to_room(async_session, dweller3.id, room3.id)

    await async_session.commit()

    # Refresh rooms to get updated dwellers
    await async_session.refresh(room1)
    await async_session.refresh(room2)
    await async_session.refresh(room3)

    # Spawn FIRE incident (spawns in a random occupied room, not at vault door)
    fire_incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert fire_incident is not None
    assert fire_incident.type == IncidentType.FIRE

    # Try to spawn RAIDER_ATTACK in vault (should fail - different type)
    raider_incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.RAIDER_ATTACK)
    assert raider_incident is None  # Should not spawn different type

    # Try to spawn another FIRE (should succeed - same type, different room)
    fire_incident2 = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert fire_incident2 is not None
    assert fire_incident2.type == IncidentType.FIRE
    assert fire_incident2.id != fire_incident.id  # Different incident


@pytest.mark.asyncio
async def test_spread_skips_elevator(async_session: AsyncSession, vault: Vault, dweller_data: dict):
    """Test that incidents don't spread to elevator rooms."""
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    # Create incident room
    incident_room_data = create_fake_room()
    incident_room_data["category"] = "Production"  # Ensure it's a production room
    incident_room_in = RoomCreate(**incident_room_data, vault_id=vault.id, coordinate_x=1, coordinate_y=1)
    incident_room = await crud.room.create(db_session=async_session, obj_in=incident_room_in)

    # Create elevator adjacent to incident room
    elevator_data = {
        "name": "Elevator",
        "category": "Misc.",
        "ability": None,
        "t2_upgrade_cost": None,
        "t3_upgrade_cost": None,
        "base_cost": 100,
        "size_min": 1,
        "size_max": 1,
        "tier": 1,
        "coordinate_x": 2,
        "coordinate_y": 1,
    }
    elevator_in = RoomCreate(**elevator_data, vault_id=vault.id)
    elevator = await crud.room.create(db_session=async_session, obj_in=elevator_in)

    # Create normal room also adjacent
    normal_room_data = create_fake_room()
    normal_room_data["category"] = "Production"  # Ensure it's a production room
    normal_room_in = RoomCreate(**normal_room_data, vault_id=vault.id, coordinate_x=1, coordinate_y=2)
    normal_room = await crud.room.create(db_session=async_session, obj_in=normal_room_in)

    # Add dweller to incident room
    dweller = DwellerCreate(**dweller_data, vault_id=vault.id, room_id=incident_room.id)
    await crud.dweller.create(db_session=async_session, obj_in=dweller)

    await async_session.commit()

    # Create incident manually
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=incident_room.id,
        incident_type=IncidentType.FIRE,
        difficulty=5,
    )

    # Trigger spread
    await incident_service._spread_incident(async_session, incident)

    # Get all active incidents
    active_incidents = await crud.incident_crud.get_active_by_vault(async_session, vault.id)

    # Check that no incident spread to elevator
    for inc in active_incidents:
        assert inc.room_id != elevator.id

    # If spread occurred, it should be to normal_room
    if len(active_incidents) > 1:
        spread_incident = next(inc for inc in active_incidents if inc.id != incident.id)
        assert spread_incident.room_id == normal_room.id


@pytest.mark.asyncio
async def test_spread_respects_active_incident_cap(async_session: AsyncSession, vault: Vault):
    from app.schemas.room import RoomCreate

    current_room = await crud.room.create(
        async_session,
        RoomCreate(
            name="Power Generator",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=3,
            size_max=6,
            coordinate_x=1,
            coordinate_y=1,
            vault_id=vault.id,
        ),
    )
    target_room = await crud.room.create(
        async_session,
        RoomCreate(
            name="Diner",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.AGILITY,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=3,
            size_max=6,
            coordinate_x=2,
            coordinate_y=1,
            vault_id=vault.id,
        ),
    )
    active_incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=current_room.id,
        incident_type=IncidentType.FIRE,
        difficulty=5,
    )

    for index in range(game_config.incident.max_active_incidents - 1):
        room = await crud.room.create(
            async_session,
            RoomCreate(
                name=f"Room {index}",
                category=RoomTypeEnum.PRODUCTION,
                ability=SPECIALEnum.STRENGTH,
                base_cost=100,
                incremental_cost=50,
                t2_upgrade_cost=500,
                t3_upgrade_cost=1500,
                size_min=3,
                size_max=6,
                coordinate_x=index + 4,
                coordinate_y=4,
                vault_id=vault.id,
            ),
        )
        await crud.incident_crud.create(
            async_session,
            vault_id=vault.id,
            room_id=room.id,
            incident_type=IncidentType.FIRE,
            difficulty=1,
        )

    assert (
        len(await crud.incident_crud.get_active_by_vault(async_session, vault.id))
        == game_config.incident.max_active_incidents
    )
    assert await incident_service._spread_incident(async_session, active_incident) is False
    assert (
        len(await crud.incident_crud.get_active_by_vault(async_session, vault.id))
        == game_config.incident.max_active_incidents
    )


class TestProcessVaultIncidents:
    """Tests for per-vault incident processing on the fast tick."""

    @pytest.mark.asyncio
    async def test_spawns_new_incident(self, async_session: AsyncSession, vault: Vault):
        mock_incident = MagicMock()
        mock_incident.type = "raider_attack"
        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=True),
            patch.object(incident_service, "spawn_incident", new_callable=AsyncMock, return_value=mock_incident),
            patch.object(incident_service, "process_incident", new_callable=AsyncMock) as mock_process,
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert result["spawned"] == 1
        assert result["active_count"] == 0
        mock_process.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_offline_vault_does_not_process_existing_incidents(self, async_session: AsyncSession, vault: Vault):
        game_state = GameState(vault_id=vault.id, last_activity_time=datetime.utcnow() - timedelta(minutes=11))
        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock) as mock_spawn,
            patch.object(incident_service, "process_incident", new_callable=AsyncMock) as mock_process,
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[MagicMock()])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2, game_state)

        assert result["active_count"] == 1
        mock_spawn.assert_not_called()
        mock_process.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_paused_vault_does_not_process_existing_incidents(self, async_session: AsyncSession, vault: Vault):
        game_state = GameState(vault_id=vault.id, is_paused=True)
        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock) as mock_spawn,
            patch.object(incident_service, "process_incident", new_callable=AsyncMock) as mock_process,
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[MagicMock()])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2, game_state)

        assert result["active_count"] == 1
        mock_spawn.assert_not_awaited()
        mock_process.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_persisted_pause_skips_processing_without_passed_game_state(
        self, async_session: AsyncSession, vault: Vault
    ):
        """The fast-tick actor path passes no game_state; it must still honor persisted pause state."""
        async_session.add(GameState(vault_id=vault.id, is_paused=True))
        await async_session.commit()

        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock) as mock_spawn,
            patch.object(incident_service, "process_incident", new_callable=AsyncMock) as mock_process,
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[MagicMock()])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)

        assert result["active_count"] == 1
        mock_spawn.assert_not_awaited()
        mock_process.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_processes_active(self, async_session: AsyncSession, vault: Vault):
        mock_incident = MagicMock()
        mock_incident.status = MagicMock()
        mock_incident.status.value = "resolved"
        mock_incident.id = "inc-1"
        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
            patch.object(
                incident_service,
                "process_incident",
                new_callable=AsyncMock,
                return_value=IncidentRoundResult(caps_earned=50),
            ),
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
            patch("app.crud.vault.vault") as mock_vault_crud,
            patch.object(async_session, "refresh", new_callable=AsyncMock),
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[mock_incident])
            mock_vault_crud.get = AsyncMock(return_value=vault)
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert result["active_count"] == 1
        assert result["processed"] == 1
        assert result["resolved"] == 1
        assert result["caps_earned"] == 50

    @pytest.mark.asyncio
    async def test_skips_skipped_result(self, async_session: AsyncSession, vault: Vault):
        mock_incident = MagicMock()
        mock_incident.id = "inc-1"
        with (
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
            patch.object(
                incident_service,
                "process_incident",
                new_callable=AsyncMock,
                return_value=IncidentRoundResult(skipped=True),
            ),
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
            patch.object(async_session, "refresh", new_callable=AsyncMock),
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[mock_incident])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert result["active_count"] == 1
        assert result["processed"] == 0

    @pytest.mark.asyncio
    async def test_error_in_one_does_not_stop(self, async_session: AsyncSession, vault: Vault):
        inc1 = MagicMock()
        inc1.id = "inc-1"
        inc2 = MagicMock()
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
            patch.object(
                incident_service,
                "process_incident",
                new_callable=AsyncMock,
                side_effect=process_side_effect,
            ),
            patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
            patch.object(async_session, "refresh", new_callable=AsyncMock),
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[inc1, inc2])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert result["active_count"] == 2
        # The first incident raised, but processing must continue to the second.
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_outer_exception_set_error(self, async_session: AsyncSession, vault: Vault):
        from sqlalchemy.exc import SQLAlchemyError

        with patch.object(
            incident_service,
            "should_spawn_incident",
            new_callable=AsyncMock,
            side_effect=SQLAlchemyError("DB down"),
        ):
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2)
        assert "error" in result


@pytest.mark.asyncio
async def test_disabled_vault_does_not_spawn_or_process(async_session: AsyncSession, vault: Vault):
    vault.incidents_disabled = True
    await async_session.commit()

    with (
        patch.object(incident_service, "spawn_incident", new_callable=AsyncMock) as mock_spawn,
        patch.object(incident_service, "process_incident", new_callable=AsyncMock) as mock_process,
    ):
        result = await incident_service.process_vault_incidents(async_session, vault.id, 2)

    assert result["active_count"] == 0
    mock_spawn.assert_not_awaited()
    mock_process.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_vault_should_spawn_returns_false(async_session: AsyncSession, vault: Vault):
    vault.incidents_disabled = True
    await async_session.commit()
    assert await incident_service.should_spawn_incident(async_session, vault.id, 3600) is False


class TestTickCommitBoundaries:
    """Characterization: pins the transaction boundaries of one incident tick.

    The tick commits at multiple boundaries today: the spawn path commits the
    incident row, its lifecycle event, and the owner notification separately;
    each combat round commits once (deferred death notifications drain right
    after it); a victorious round's caps payout commits the deposit and the
    profile statistic separately. Consolidating to a single commit per tick
    must prove these boundaries equivalent first — these tests fail loudly if
    the boundaries move silently.
    """

    @pytest.mark.asyncio
    async def test_quiet_round_commits_exactly_once(self, async_session: AsyncSession, room_with_dwellers: dict):
        """A round with no spawn, no victory, and no caps commits exactly once."""
        vault = room_with_dwellers["vault"]
        incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
        assert incident is not None

        with (
            patch.object(async_session, "commit", wraps=async_session.commit) as commit_spy,
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
            patch("app.services.combat.incident_math.damage_to_dwellers", return_value=0.0),
            patch("app.services.combat.incident_math.damage_to_raiders", return_value=0.0),
            patch("app.services.combat.incident_math.fire_suppression", return_value=0.0),
        ):
            stats = await incident_service.process_vault_incidents(async_session, vault.id, 2)

        assert stats["processed"] == 1
        assert stats["caps_earned"] == 0
        assert commit_spy.await_count == 1

    @pytest.mark.asyncio
    async def test_spawn_commits_row_event_and_notification_separately(
        self, async_session: AsyncSession, room_with_dwellers: dict
    ):
        """Spawning commits the incident row, the lifecycle event, and the owner notification."""
        vault = room_with_dwellers["vault"]
        with (
            patch.object(async_session, "commit", wraps=async_session.commit) as commit_spy,
            patch("app.services.notification_service.manager"),
            patch("app.services.notification_service.sse_manager"),
        ):
            incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)

        assert incident is not None
        assert commit_spy.await_count == 3

    @pytest.mark.asyncio
    async def test_victory_commits_round_notification_then_deposit(
        self, async_session: AsyncSession, room_with_dwellers: dict
    ):
        """A victorious round commits the round, the victory notification, then the caps payout."""
        vault = room_with_dwellers["vault"]
        for dweller in room_with_dwellers["dwellers"]:
            dweller.level = game_config.leveling.max_level  # keep level-up commits out of this count
            async_session.add(dweller)
        await async_session.commit()

        incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.RADROACH_INFESTATION)
        assert incident is not None

        with (
            patch.object(async_session, "commit", wraps=async_session.commit) as commit_spy,
            patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
            patch("app.services.combat.incident_math.damage_to_dwellers", return_value=0.0),
            patch("app.services.combat.incident_math.damage_to_raiders", return_value=1000.0),
            patch("app.services.notification_service.manager"),
            patch("app.services.notification_service.sse_manager"),
        ):
            stats = await incident_service.process_vault_incidents(async_session, vault.id, 2)

        assert stats["resolved"] == 1
        assert stats["caps_earned"] > 0
        assert commit_spy.await_count == 4


@pytest.mark.asyncio
async def test_failed_incident_rolls_back_before_the_next_one(async_session: AsyncSession, vault: Vault) -> None:
    """A failed round must recover the session, or every later incident in the tick fails.

    SQLite does not poison a session on a failed statement the way PostgreSQL does,
    so this pins the recovery call itself rather than its downstream symptom.
    """
    vault_id = vault.id

    async def poison(*_args, **_kwargs):
        await async_session.execute(text("SELECT 1 FROM table_that_does_not_exist"))

    with (
        patch("app.services.combat.incident_tick.incident_crud") as mock_crud,
        patch.object(incident_service, "process_incident", new=poison),
        patch.object(incident_service, "should_spawn_incident", new_callable=AsyncMock, return_value=False),
        patch.object(async_session, "rollback", new=AsyncMock(wraps=async_session.rollback)) as rollback_spy,
    ):
        mock_crud.get_active_by_vault = AsyncMock(return_value=[MagicMock()])
        result = await incident_service.process_vault_incidents(async_session, vault_id, 2)

    assert result["active_count"] == 1
    rollback_spy.assert_awaited()
