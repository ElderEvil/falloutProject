"""Tests for game control API endpoints."""

# TODO: Fix session isolation issues in incident API tests
# See test_services/test_incident_service.py for details

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.vault import VaultNumber
from app.services.vault_service import vault_service
from app.tests.factory.rooms import create_fake_room

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_pause_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test pausing a vault's game loop."""
    # Create a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=999),
        user_id=user.id,
    )

    # Pause the vault
    response = await async_client.post(
        f"/game/vaults/{vault.id}/pause",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_paused"] is True
    assert data["paused_at"] is not None


@pytest.mark.asyncio
async def test_resume_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test resuming a paused vault's game loop."""
    # Create and pause a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=998),
        user_id=user.id,
    )

    # Pause first
    await async_client.post(
        f"/game/vaults/{vault.id}/pause",
        headers=normal_user_token_headers,
    )

    # Resume the vault
    response = await async_client.post(
        f"/game/vaults/{vault.id}/resume",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_paused"] is False
    assert data["resumed_at"] is not None


@pytest.mark.asyncio
async def test_get_game_state(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test getting vault game state."""
    # Create a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=997),
        user_id=user.id,
    )

    # Get game state
    response = await async_client.get(
        f"/game/vaults/{vault.id}/game-state",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "vault_id" in data
    assert "is_active" in data
    assert "is_paused" in data
    assert "total_game_time" in data
    assert "last_tick_time" in data
    assert "offline_time" in data


@pytest.mark.asyncio
async def test_manual_tick(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test manually triggering a game tick."""
    # Create a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=996),
        user_id=user.id,
    )

    # Store initial resources directly from the vault object
    initial_power = vault.power  # noqa: F841
    initial_food = vault.food
    initial_water = vault.water

    # Trigger manual tick
    response = await async_client.post(
        f"/game/vaults/{vault.id}/tick",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "vault_id" in data
    assert "seconds_passed" in data
    assert "updates" in data

    # Refresh vault to get updated resources
    await async_session.refresh(vault)

    # Power should decrease (consumption > production for infrastructure)
    # Food and water should increase (dwellers producing)
    assert vault.food > initial_food or vault.water > initial_water


@pytest.mark.asyncio
@pytest.mark.skip(reason="Session isolation issue - fixture data not visible to spawn_incident query")
async def test_get_incidents(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test getting list of incidents for a vault."""
    # Create a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=995),
        user_id=user.id,
    )

    # Get incidents (should be empty for new vault)
    response = await async_client.get(
        f"/game/vaults/{vault.id}/incidents",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "incidents" in data
    assert data["incident_count"] == 0
    # New vault should have no incidents
    assert len(data["incidents"]) == 0


@pytest.mark.asyncio
async def test_vault_initialization_creates_game_state(
    async_client: AsyncClient,
    async_session: AsyncSession,  # noqa: ARG001
    normal_user_token_headers: dict[str, str],
):
    """Test that initializing a vault creates proper game state."""
    # Create a vault via initiate endpoint
    response = await async_client.post(
        "/vaults/initiate",
        headers=normal_user_token_headers,
        json={"number": 994},
    )
    assert response.status_code == 201
    vault_data = response.json()
    vault_id = vault_data["id"]

    # Verify vault has production rooms and resources
    assert vault_data["power_max"] > 0
    assert vault_data["food_max"] > 0
    assert vault_data["water_max"] > 0
    assert vault_data["power"] > 0
    assert vault_data["food"] > 0
    assert vault_data["water"] > 0

    # Verify game state exists
    game_state_response = await async_client.get(
        f"/game/vaults/{vault_id}/game-state",
        headers=normal_user_token_headers,
    )
    assert game_state_response.status_code == 200
    game_state = game_state_response.json()
    assert game_state["is_active"] is True
    assert game_state["is_paused"] is False
    assert game_state["total_game_time"] == 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="Session isolation issue - fixture data not visible to spawn_incident query")
async def test_spawn_incident_debug(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test spawning an incident via debug endpoint."""
    # Create a vault with a room and dwellers
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=993),
        user_id=user.id,
    )

    # Get a room from the initialized vault
    from app.schemas.room import RoomCreate

    room_data = create_fake_room()
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(db_session=async_session, obj_in=room_in)

    # Create a dweller in the room
    from app.schemas.dweller import DwellerCreate

    dweller_in = DwellerCreate(
        first_name="Test",
        last_name="Dweller",
        gender="male",
        rarity="common",
        vault_id=vault.id,
        room_id=room.id,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
    )
    await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

    # Spawn incident
    response = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/spawn",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "incident_id" in data
    assert "type" in data
    assert "difficulty" in data
    assert "room_id" in data
    assert data["room_id"]  # Verify a room_id exists (random selection from occupied rooms)


@pytest.mark.asyncio
@pytest.mark.skip(reason="Session isolation issue - fixture data not visible to spawn_incident query")
async def test_spawn_incident_specific_type(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test spawning a specific incident type."""
    # Create a vault with a room and dwellers
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=992),
        user_id=user.id,
    )

    # Create room with dweller
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    room_data = create_fake_room()
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(db_session=async_session, obj_in=room_in)

    dweller_in = DwellerCreate(
        first_name="Test",
        last_name="Dweller",
        gender="female",
        rarity="common",
        vault_id=vault.id,
        room_id=room.id,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
    )
    await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

    # Spawn fire incident
    response = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/spawn",
        headers=normal_user_token_headers,
        params={"incident_type": "fire"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "fire"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Session isolation issue - fixture data not visible to spawn_incident query")
async def test_get_incident_details(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test getting detailed incident information."""
    from app.models.incident import IncidentType

    # Create a vault with incident
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=991),
        user_id=user.id,
    )

    # Create room with dweller
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    room_data = create_fake_room()
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(db_session=async_session, obj_in=room_in)

    dweller_in = DwellerCreate(
        first_name="Fighter",
        last_name="Dweller",
        gender="male",
        rarity="rare",
        vault_id=vault.id,
        room_id=room.id,
        strength=8,
        perception=7,
        endurance=8,
        charisma=5,
        intelligence=5,
        agility=6,
        luck=5,
    )
    await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

    # Create incident directly
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.RAIDER_ATTACK,
        difficulty=5,
    )

    # Get incident details
    response = await async_client.get(
        f"/game/vaults/{vault.id}/incidents/{incident.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(incident.id)
    assert data["type"] == "raider_attack"
    assert data["difficulty"] == 5
    assert data["status"] == "active"
    assert "damage_dealt" in data
    assert "enemies_defeated" in data


@pytest.mark.asyncio
@pytest.mark.skip(reason="Session isolation issue - fixture data not visible to spawn_incident query")
async def test_resolve_incident_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test resolving an incident successfully."""
    from app.models.incident import IncidentType

    # Create a vault with incident
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=990),
        user_id=user.id,
    )
    initial_caps = vault.bottle_caps

    # Create room with dweller
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    room_data = create_fake_room()
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(db_session=async_session, obj_in=room_in)

    dweller_in = DwellerCreate(
        first_name="Hero",
        last_name="Dweller",
        gender="female",
        rarity="legendary",
        vault_id=vault.id,
        room_id=room.id,
        strength=10,
        perception=10,
        endurance=10,
        charisma=10,
        intelligence=10,
        agility=10,
        luck=10,
    )
    await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

    # Create incident
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.RADROACH_INFESTATION,
        difficulty=3,
    )

    # Resolve incident
    response = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/{incident.id}/resolve",
        headers=normal_user_token_headers,
        params={"success": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert "caps_earned" in data
    assert data["caps_earned"] > 0
    assert "items_earned" in data

    # Verify vault caps increased
    await async_session.refresh(vault)
    assert vault.bottle_caps > initial_caps


@pytest.mark.asyncio
@pytest.mark.skip(reason="Session isolation issue - fixture data not visible to spawn_incident query")
async def test_resolve_incident_failure(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test abandoning an incident."""
    from app.models.incident import IncidentType

    # Create a vault with incident
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=989),
        user_id=user.id,
    )

    # Create room with dweller
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    room_data = create_fake_room()
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(db_session=async_session, obj_in=room_in)

    dweller_in = DwellerCreate(
        first_name="Weak",
        last_name="Dweller",
        gender="male",
        rarity="common",
        vault_id=vault.id,
        room_id=room.id,
        strength=1,
        perception=1,
        endurance=1,
        charisma=1,
        intelligence=1,
        agility=1,
        luck=1,
    )
    await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

    # Create incident
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.DEATHCLAW_ATTACK,
        difficulty=10,
    )

    # Abandon incident
    response = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/{incident.id}/resolve",
        headers=normal_user_token_headers,
        params={"success": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["caps_earned"] == 0
    assert data["message"] == "Incident failed"
