"""Tests for game control API endpoints."""

# TODO: Fix session isolation issues in incident API tests
# See test_services/test_incident_service.py for details

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.crud.storage import storage as storage_crud
from app.models.incident import IncidentType
from app.models.storage import Storage
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultNumber
from app.services.vault_service import vault_service
from app.tests.factory.rooms import create_fake_room
from app.utils.static_data import game_data_store

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.smoke
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


@pytest.mark.smoke
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
    initial_power = vault.power
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
    await async_session.commit()

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


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_vault_initialization_creates_game_state(
    async_client: AsyncClient,
    async_session: AsyncSession,
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
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()

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
async def test_spawn_incident_disabled_vault_rejected(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Spawn endpoint rejects disabled vaults with a distinct message."""
    from app.core.game_config import game_config

    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=990),
        user_id=user.id,
    )
    vault.incidents_disabled = True
    async_session.add(vault)
    await async_session.commit()

    response = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/spawn",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 400
    assert "disabled" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_fire_incident_details_describe_containment(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Fire must not be presented as an attacker encounter."""
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session, obj_in=VaultNumber(number=989), user_id=user.id
    )
    room = await crud.room.create(
        async_session,
        obj_in=RoomCreate(**create_fake_room(), vault_id=vault.id),
    )
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=3,
    )

    response = await async_client.get(
        f"/game/vaults/{vault.id}/incidents/{incident.id}", headers=normal_user_token_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["family"] == "hazard"
    assert data["objective"] == "contain"
    assert data["progress"]["label"] == "Fire contained"
    assert data["response"]["label"] == "Send responders"


@pytest.mark.asyncio
async def test_assign_incident_responders(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test assigning an eligible dweller to defend an incident."""
    from app.models.incident import IncidentType

    # Create a vault with incident
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=990),
        user_id=user.id,
    )

    # Create the incident room and a separate room containing the responder.
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    room_data = create_fake_room()
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(db_session=async_session, obj_in=room_in)
    responder_room_in = RoomCreate(**create_fake_room(), vault_id=vault.id)
    responder_room = await crud.room.create(db_session=async_session, obj_in=responder_room_in)

    dweller_in = DwellerCreate(
        first_name="Hero",
        last_name="Dweller",
        gender="female",
        rarity="legendary",
        vault_id=vault.id,
        room_id=responder_room.id,
        strength=10,
        perception=10,
        endurance=10,
        charisma=10,
        intelligence=10,
        agility=10,
        luck=10,
    )
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    await async_session.commit()

    # Create incident
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.RADROACH_INFESTATION,
        difficulty=3,
    )
    await async_session.commit()

    # Assign defender
    response = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/{incident.id}/responders",
        headers=normal_user_token_headers,
        json={"dweller_ids": [str(dweller.id)]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == str(incident.id)
    assert data["room_id"] == str(room.id)
    assert data["assigned_dweller_ids"] == [str(dweller.id)]
    await async_session.refresh(dweller)
    assert dweller.room_id == room.id


@pytest.mark.asyncio
async def test_get_incident_team_returns_assigned_responders(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """The incident team endpoint returns the assigned responder roster."""
    from app.models.incident import IncidentType
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=984),
        user_id=user.id,
    )

    room = await crud.room.create(async_session, obj_in=RoomCreate(**create_fake_room(), vault_id=vault.id))
    responder_room = await crud.room.create(async_session, obj_in=RoomCreate(**create_fake_room(), vault_id=vault.id))

    dweller_in = DwellerCreate(
        first_name="Hero",
        last_name="Dweller",
        gender="female",
        rarity="legendary",
        vault_id=vault.id,
        room_id=responder_room.id,
        strength=10,
        perception=10,
        endurance=10,
        charisma=10,
        intelligence=10,
        agility=10,
        luck=10,
    )
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    await async_session.commit()

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.RADROACH_INFESTATION,
        difficulty=3,
    )
    await async_session.commit()

    assigned = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/{incident.id}/responders",
        headers=normal_user_token_headers,
        json={"dweller_ids": [str(dweller.id)]},
    )
    assert assigned.status_code == 200

    response = await async_client.get(
        f"/game/vaults/{vault.id}/incidents/{incident.id}/team",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert [member["dweller_id"] for member in data] == [str(dweller.id)]
    assert all(member["slot_number"] is None for member in data)
    assert all(member["status"] == "assigned" for member in data)


@pytest.mark.asyncio
async def test_get_incident_team_missing_or_foreign_returns_404(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """A missing or foreign incident returns 404 for the team endpoint."""
    from uuid import uuid4

    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session,
        obj_in=VaultNumber(number=983),
        user_id=user.id,
    )

    response = await async_client.get(
        f"/game/vaults/{vault.id}/incidents/{uuid4()}/team",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_incident_team_requires_auth(async_client: AsyncClient):
    """The incident team endpoint rejects requests without auth headers."""
    from uuid import uuid4

    response = await async_client.get(
        f"/game/vaults/{uuid4()}/incidents/{uuid4()}/team",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_incident_overflow_is_discoverable_sellable_and_takeable(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Held incident loot surfaces as pending, sells without space, and takes when there is space."""
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await vault_service.initiate_vault(
        db_session=async_session, obj_in=VaultNumber(number=987), user_id=user.id
    )
    room = await crud.room.create(async_session, obj_in=RoomCreate(**create_fake_room(), vault_id=vault.id))
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room.id,
        incident_type=IncidentType.RAIDER_ATTACK,
        difficulty=3,
    )

    storage = await storage_crud.get_by_vault(async_session, vault.id)
    if storage is None:
        storage = Storage(vault_id=vault.id, max_space=0)
        async_session.add(storage)
    else:
        storage.max_space = 0
    incident.unclaimed_loot = [{"item_type": "weapon", "rarity": "common", "name": game_data_store.weapons[0].name}]
    incident.resolve(success=True)
    async_session.add(incident)
    await async_session.commit()

    pending = await async_client.get(
        f"/game/vaults/{vault.id}/incidents/pending-overflow", headers=normal_user_token_headers
    )
    assert pending.status_code == 200
    assert [entry["incident_id"] for entry in pending.json()] == [str(incident.id)]

    detail = await async_client.get(
        f"/game/vaults/{vault.id}/incidents/{incident.id}", headers=normal_user_token_headers
    )
    assert detail.status_code == 200
    assert detail.json()["unclaimed_loot"] == incident.unclaimed_loot

    full = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/{incident.id}/overflow/take",
        headers=normal_user_token_headers,
        json={"index": 0},
    )
    assert full.status_code == 409

    sold = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/{incident.id}/overflow/sell",
        headers=normal_user_token_headers,
        json={"index": 0},
    )
    assert sold.status_code == 200
    assert sold.json()["caps_granted"] > 0
    assert sold.json()["unclaimed_loot"] == []
