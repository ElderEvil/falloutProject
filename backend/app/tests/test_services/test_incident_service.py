"""Tests for incident service logic."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.game_state import GameState
from app.models.incident import IncidentFamily, IncidentObjective, IncidentStatus, IncidentType
from app.models.incident_event import IncidentEvent
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.incident import IncidentRoundResult
from app.services.combat import incident_math
from app.services.combat.incident_service import incident_service
from app.services.dweller_service import dweller_service
from app.tests.factory.rooms import create_fake_room
from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException


@pytest_asyncio.fixture(name="room")
async def room_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    """Create a test room."""
    from app.schemas.room import RoomCreate

    room_data = create_fake_room()
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    return await crud.room.create(db_session=async_session, obj_in=room_in)


def create_test_room() -> dict:
    """Create a test room that is NOT an elevator (ensures incident can spawn)."""
    room_data = create_fake_room()
    # Ensure room is not named "Elevator" to allow incident spawning
    while room_data["name"] == "Elevator":
        room_data = create_fake_room()
    return room_data


@pytest.mark.asyncio
async def test_spawn_incident_no_rooms(async_session: AsyncSession, vault: Vault):
    """Test that no incident spawns when there are no occupied rooms."""
    incident = await incident_service.spawn_incident(async_session, vault.id)
    assert incident is None


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
    # Test low difficulty (internal threat - caps only)
    loot_low = incident_math.generate_loot(difficulty=1, incident_type=IncidentType.FIRE)
    assert "caps" in loot_low
    assert loot_low["caps"] >= 25
    assert loot_low["caps"] <= 75

    # Test high difficulty (external threat - caps + items)
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
            patch("app.services.combat.incident_service.incident_crud") as mock_crud,
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
            patch("app.services.combat.incident_service.incident_crud") as mock_crud,
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
            patch("app.services.combat.incident_service.incident_crud") as mock_crud,
        ):
            mock_crud.get_active_by_vault = AsyncMock(return_value=[MagicMock()])
            result = await incident_service.process_vault_incidents(async_session, vault.id, 2, game_state)

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
            patch("app.services.combat.incident_service.incident_crud") as mock_crud,
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
            patch("app.services.combat.incident_service.incident_crud") as mock_crud,
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
            patch("app.services.combat.incident_service.incident_crud") as mock_crud,
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
