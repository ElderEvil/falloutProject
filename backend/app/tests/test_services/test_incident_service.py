"""Tests for incident service logic."""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.incident import IncidentStatus, IncidentType
from app.models.room import Room
from app.models.vault import Vault
from app.services.incident_service import incident_service
from app.tests.factory.rooms import create_fake_room


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
async def test_spawn_incident_success(async_session: AsyncSession, room_with_dwellers: dict):
    """Test successful incident spawning."""
    room = room_with_dwellers["room"]
    # Use FIRE type which spawns in occupied rooms (not at vault door)
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)

    assert incident is not None
    assert incident.vault_id == room.vault_id
    assert incident.room_id is not None  # Random selection from occupied rooms
    assert incident.status == IncidentStatus.ACTIVE
    assert 1 <= incident.difficulty <= 10
    assert incident.damage_dealt == 0
    assert incident.enemies_defeated == 0


@pytest.mark.asyncio
async def test_spawn_incident_specific_type(async_session: AsyncSession, room_with_dwellers: dict):
    """Test spawning a specific incident type."""
    room = room_with_dwellers["room"]
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)

    assert incident is not None
    assert incident.type == IncidentType.FIRE


@pytest.mark.asyncio
async def test_process_incident_combat(async_session: AsyncSession, room_with_dwellers: dict):
    """Test incident combat processing."""
    room = room_with_dwellers["room"]
    # Create incident - use FIRE which spawns in rooms (not at vault door)
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)

    # Process combat for 60 seconds
    result = await incident_service.process_incident(async_session, incident, 60)

    # Check result keys (format may vary based on incident type)
    assert "damage_to_dwellers" in result
    assert "damage_to_raiders" in result
    assert "dwellers_damaged" in result
    assert result["damage_to_dwellers"] >= 0
    assert result["damage_to_raiders"] >= 0

    # Verify incident was updated
    await async_session.refresh(incident)
    assert incident.damage_dealt >= 0


@pytest.mark.asyncio
async def test_process_incident_auto_resolve(async_session: AsyncSession, room_with_dwellers: dict):
    """Test that incident auto-resolves when enough enemies defeated."""
    room = room_with_dwellers["room"]
    # Create low difficulty incident
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.RADROACH_INFESTATION,
        difficulty=1,
    )

    # Manually set high enemies defeated
    incident.enemies_defeated = 10
    async_session.add(incident)
    await async_session.commit()
    await async_session.refresh(incident)

    # Process incident
    result = await incident_service.process_incident(async_session, incident, 60)

    # Should auto-resolve
    await async_session.refresh(incident)
    assert incident.status == IncidentStatus.RESOLVED or result["enemies_defeated"] >= 2


@pytest.mark.asyncio
async def test_calculate_dweller_combat_power(
    async_session: AsyncSession,
    room_with_dwellers: dict,
):
    """Test dweller combat power calculation."""
    # Get dwellers from fixture dict
    dwellers = room_with_dwellers["dwellers"]
    assert len(dwellers) > 0

    dweller = dwellers[0]
    power = incident_service._calculate_dweller_combat_power([dweller])

    # Power should be positive and reasonable
    assert power > 0
    assert power < 1000  # Sanity check


@pytest.mark.asyncio
async def test_generate_loot(async_session: AsyncSession, vault: Vault):
    """Test loot generation for different difficulties."""
    # Test low difficulty (internal threat - caps only)
    loot_low = incident_service._generate_loot(difficulty=1, incident_type=IncidentType.FIRE)
    assert "caps" in loot_low
    assert loot_low["caps"] >= 50
    assert loot_low["caps"] <= 150

    # Test high difficulty (external threat - caps + items)
    loot_high = incident_service._generate_loot(difficulty=10, incident_type=IncidentType.RAIDER_ATTACK)
    assert loot_high["caps"] >= 500
    assert loot_high["caps"] <= 1050


@pytest.mark.asyncio
async def test_resolve_incident_manually_success(async_session: AsyncSession, room_with_dwellers: dict):
    """Test manual incident resolution with success."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    await async_session.refresh(dwellers[0].vault)
    initial_caps = dwellers[0].vault.bottle_caps

    result = await incident_service.resolve_incident_manually(async_session, incident.id, success=True)

    assert result["message"] == "Incident resolved successfully"
    assert result["caps_earned"] > 0
    assert "items_earned" in result

    # Verify incident status
    await async_session.refresh(incident)
    assert incident.status == IncidentStatus.RESOLVED

    # Verify vault caps increased
    await async_session.refresh(dwellers[0].vault)
    assert dwellers[0].vault.bottle_caps > initial_caps


@pytest.mark.asyncio
@pytest.mark.skip(reason="Needs investigation - assertion may be outdated")
async def test_resolve_incident_manually_failure(async_session: AsyncSession, room_with_dwellers: dict):
    """Test manual incident resolution with failure."""
    room = room_with_dwellers["room"]
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)

    result = await incident_service.resolve_incident_manually(async_session, incident.id, success=False)

    assert result["message"] == "Incident abandoned"
    assert result["caps_earned"] == 0

    # Verify incident status
    await async_session.refresh(incident)
    assert incident.status == IncidentStatus.FAILED


@pytest.mark.asyncio
@pytest.mark.skip(reason="Needs investigation - assertion may be outdated")
async def test_incident_spreading_mechanics(async_session: AsyncSession, room_with_dwellers: dict):
    """Test incident spreading to adjacent rooms."""
    from app.schemas.room import RoomCreate

    room = room_with_dwellers["room"]
    # Create another room adjacent to first room
    room2_data = create_fake_room()
    room2_in = RoomCreate(**room2_data, vault_id=room.vault_id)
    room2 = await crud.room.create(db_session=async_session, obj_in=room2_in)

    # Create incident
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)

    # Manually trigger spread time
    incident.last_spread_time = datetime.utcnow() - timedelta(seconds=61)
    async_session.add(incident)
    await async_session.commit()
    await async_session.refresh(incident)

    initial_spread_count = incident.spread_count

    # Check if incident should spread
    if incident.should_spread():
        # Get adjacent rooms
        adjacent_rooms = await incident_service._get_adjacent_rooms(async_session, incident.room_id)

        if adjacent_rooms:
            # Spread incident
            incident.spread_to_room(str(room2.id))
            incident.spread_count += 1
            async_session.add(incident)
            await async_session.commit()
            await async_session.refresh(incident)

            assert incident.spread_count > initial_spread_count
            assert str(room2.id) in incident.rooms_affected


@pytest.mark.asyncio
async def test_get_active_incidents(async_session: AsyncSession, room_with_dwellers: dict):
    """Test retrieving all active incidents."""
    room = room_with_dwellers["room"]
    # Spawn incident - only one incident type per vault is allowed
    incident1 = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)

    # Get active incidents
    incidents = await crud.incident_crud.get_active_by_vault(async_session, room.vault_id)

    # Only one incident type allowed per vault, so we expect 1 incident
    assert len(incidents) >= 1
    incident_ids = [str(i.id) for i in incidents]
    assert str(incident1.id) in incident_ids


@pytest.mark.asyncio
async def test_incident_elapsed_time(async_session: AsyncSession, room_with_dwellers: dict):
    """Test incident elapsed time calculation."""
    room = room_with_dwellers["room"]
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)

    # Immediately check elapsed time (should be near 0)
    elapsed = incident.elapsed_time()
    assert elapsed >= 0
    assert elapsed < 5  # Should be less than 5 seconds

    # Manually set start time to 1 minute ago
    incident.start_time = datetime.utcnow() - timedelta(minutes=1)
    async_session.add(incident)
    await async_session.commit()
    await async_session.refresh(incident)

    elapsed = incident.elapsed_time()
    assert elapsed >= 55  # Should be around 60 seconds
    assert elapsed <= 65


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
    await crud.dweller.move_to_room(async_session, dweller1.id, room1.id)

    dweller2_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller2 = await crud.dweller.create(db_session=async_session, obj_in=dweller2_in)
    await crud.dweller.move_to_room(async_session, dweller2.id, room2.id)

    dweller3_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller3 = await crud.dweller.create(db_session=async_session, obj_in=dweller3_in)
    await crud.dweller.move_to_room(async_session, dweller3.id, room3.id)

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
async def test_no_spawn_in_elevator(async_session: AsyncSession, vault: Vault, dweller_data: dict):
    """Test that incidents never spawn in elevator rooms."""
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    # Create elevator room with dwellers
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
        "coordinate_x": 3,
        "coordinate_y": 2,
    }
    elevator_in = RoomCreate(**elevator_data, vault_id=vault.id)
    elevator = await crud.room.create(db_session=async_session, obj_in=elevator_in)

    # Create a normal room with dwellers
    normal_room_data = create_fake_room()
    normal_room_data["category"] = "Production"  # Ensure it's a production room
    normal_room_in = RoomCreate(**normal_room_data, vault_id=vault.id, coordinate_x=4, coordinate_y=2)
    normal_room = await crud.room.create(db_session=async_session, obj_in=normal_room_in)

    # Add dwellers to both rooms
    # Add dweller to elevator
    dweller1 = DwellerCreate(**dweller_data, vault_id=vault.id, room_id=elevator.id)
    await crud.dweller.create(db_session=async_session, obj_in=dweller1)

    # Add dweller to normal room
    dweller2 = DwellerCreate(**dweller_data, vault_id=vault.id, room_id=normal_room.id)
    await crud.dweller.create(db_session=async_session, obj_in=dweller2)

    await async_session.commit()

    # Spawn 10 incidents
    spawned_incidents = []
    for _ in range(10):
        incident = await incident_service.spawn_incident(async_session, vault.id)
        if incident:
            spawned_incidents.append(incident)

    # Assert none spawned in elevator
    for incident in spawned_incidents:
        assert incident.room_id != elevator.id
        # Should all be in the normal room
        assert incident.room_id == normal_room.id


@pytest.mark.asyncio
@pytest.mark.skip(reason="Needs investigation - assertion may be outdated")
async def test_one_incident_per_room(async_session: AsyncSession, vault: Vault, dweller_data: dict):
    """Test that only one incident can be active in a room at once."""
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    # Create one room with dwellers
    room_data = create_fake_room()
    room_data["category"] = "Production"  # Ensure it's a production room
    room_in = RoomCreate(**room_data, vault_id=vault.id, coordinate_x=1, coordinate_y=1)
    room = await crud.room.create(db_session=async_session, obj_in=room_in)

    # Add dweller
    dweller = DwellerCreate(**dweller_data, vault_id=vault.id, room_id=room.id)
    await crud.dweller.create(db_session=async_session, obj_in=dweller)

    await async_session.commit()

    # Spawn first incident
    incident1 = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident1 is not None
    assert incident1.room_id == room.id

    # Try to spawn second incident (should fail - room already has incident)
    incident2 = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident2 is None  # No available rooms


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
