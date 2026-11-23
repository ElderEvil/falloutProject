from uuid import uuid4

import pytest

from app import crud
from app.core.config import settings
from app.core.enums import IncidentType
from app.crud.storage import storage as storage_crud
from app.models.storage import Storage
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultNumber
from app.services.vault_service import vault_service
from app.tests.factory.rooms import create_fake_room
from app.utils.static_data import game_data_store

pytestmark = pytest.mark.asyncio(scope="module")


async def _vault(async_session, number: int):
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    assert user is not None
    return await vault_service.initiate_vault(
        db_session=async_session, obj_in=VaultNumber(number=number), user_id=user.id
    )


async def _room(async_session, vault):
    return await crud.room.create(async_session, obj_in=RoomCreate(**create_fake_room(), vault_id=vault.id))


async def _dweller(async_session, vault, room, *, first="Hero", rarity="legendary", stat=10):
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            first_name=first,
            last_name="Dweller",
            gender="female",
            rarity=rarity,
            vault_id=vault.id,
            room_id=room.id,
            strength=stat,
            perception=stat,
            endurance=stat,
            charisma=stat,
            intelligence=stat,
            agility=stat,
            luck=stat,
        ),
    )
    await async_session.commit()
    return dweller


async def _incident(async_session, vault, room, incident_type):
    return await crud.incident_crud.create(
        async_session, vault_id=vault.id, room_id=room.id, incident_type=incident_type, difficulty=3
    )


@pytest.mark.smoke
async def test_resume_vault(async_client, async_session, normal_user_token_headers):
    vault = await _vault(async_session, 998)
    await async_client.post(f"/game/vaults/{vault.id}/pause", headers=normal_user_token_headers)

    response = await async_client.post(f"/game/vaults/{vault.id}/resume", headers=normal_user_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["is_paused"] is False
    assert data["resumed_at"] is not None


@pytest.mark.smoke
async def test_manual_tick(async_client, async_session, normal_user_token_headers):
    vault = await _vault(async_session, 996)
    initial_food, initial_water = vault.food, vault.water

    response = await async_client.post(f"/game/vaults/{vault.id}/tick", headers=normal_user_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "vault_id" in data
    assert "seconds_passed" in data
    assert "updates" in data
    assert data["updates"]["arena"] == {"rooms": []}

    await async_session.refresh(vault)
    # Dwellers produce; food or water must rise even if power is consumed.
    assert vault.food > initial_food or vault.water > initial_water


async def test_get_incidents(async_client, async_session, normal_user_token_headers):
    vault = await _vault(async_session, 995)
    await async_session.commit()

    response = await async_client.get(f"/game/vaults/{vault.id}/incidents", headers=normal_user_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "incidents" in data
    assert data["incident_count"] == 0
    assert len(data["incidents"]) == 0


@pytest.mark.smoke
async def test_vault_initialization_creates_game_state(async_client, normal_user_token_headers):
    response = await async_client.post("/vaults/initiate", headers=normal_user_token_headers, json={"number": 994})
    assert response.status_code == 201
    vault_data = response.json()
    vault_id = vault_data["id"]

    assert vault_data["power_max"] > 0
    assert vault_data["food_max"] > 0
    assert vault_data["water_max"] > 0
    assert vault_data["power"] > 0
    assert vault_data["food"] > 0
    assert vault_data["water"] > 0

    game_state_response = await async_client.get(
        f"/game/vaults/{vault_id}/game-state", headers=normal_user_token_headers
    )
    assert game_state_response.status_code == 200
    game_state = game_state_response.json()
    assert game_state["is_active"] is True
    assert game_state["is_paused"] is False
    assert game_state["total_game_time"] == 0


async def test_spawn_incident_specific_type(async_client, async_session, normal_user_token_headers):
    vault = await _vault(async_session, 992)
    room = await _room(async_session, vault)
    await _dweller(async_session, vault, room, first="Test", rarity="common", stat=5)

    response = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/spawn",
        headers=normal_user_token_headers,
        params={"incident_type": "fire"},
    )
    assert response.status_code == 201
    assert response.json()["type"] == "fire"


async def test_spawn_incident_disabled_vault_rejected(async_client, async_session, normal_user_token_headers):
    vault = await _vault(async_session, 990)
    vault.incidents_disabled = True
    async_session.add(vault)
    await async_session.commit()

    response = await async_client.post(f"/game/vaults/{vault.id}/incidents/spawn", headers=normal_user_token_headers)
    assert response.status_code == 400
    assert "disabled" in response.json()["detail"].lower()


async def test_fire_incident_details_describe_containment(async_client, async_session, normal_user_token_headers):
    vault = await _vault(async_session, 989)
    room = await _room(async_session, vault)
    incident = await _incident(async_session, vault, room, IncidentType.FIRE)

    response = await async_client.get(
        f"/game/vaults/{vault.id}/incidents/{incident.id}", headers=normal_user_token_headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["family"] == "hazard"
    assert data["objective"] == "contain"
    assert data["progress"]["label"] == "Fire contained"
    assert data["response"]["label"] == "Send responders"


async def test_assign_incident_responders(async_client, async_session, normal_user_token_headers):
    vault = await _vault(async_session, 990)
    room = await _room(async_session, vault)
    responder_room = await _room(async_session, vault)
    dweller = await _dweller(async_session, vault, responder_room)
    incident = await _incident(async_session, vault, room, IncidentType.RADROACH_INFESTATION)
    await async_session.commit()

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


async def test_get_incident_team_returns_assigned_responders(async_client, async_session, normal_user_token_headers):
    vault = await _vault(async_session, 984)
    room = await _room(async_session, vault)
    responder_room = await _room(async_session, vault)
    dweller = await _dweller(async_session, vault, responder_room)
    incident = await _incident(async_session, vault, room, IncidentType.RADROACH_INFESTATION)
    await async_session.commit()

    assigned = await async_client.post(
        f"/game/vaults/{vault.id}/incidents/{incident.id}/responders",
        headers=normal_user_token_headers,
        json={"dweller_ids": [str(dweller.id)]},
    )
    assert assigned.status_code == 200

    response = await async_client.get(
        f"/game/vaults/{vault.id}/incidents/{incident.id}/team", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert [member["dweller_id"] for member in data] == [str(dweller.id)]
    assert all(member["slot_number"] is None for member in data)
    assert all(member["status"] == "assigned" for member in data)


async def test_get_incident_team_missing_or_foreign_returns_404(async_client, async_session, normal_user_token_headers):
    vault = await _vault(async_session, 983)

    response = await async_client.get(
        f"/game/vaults/{vault.id}/incidents/{uuid4()}/team", headers=normal_user_token_headers
    )
    assert response.status_code == 404


async def test_get_incident_team_requires_auth(async_client):
    response = await async_client.get(f"/game/vaults/{uuid4()}/incidents/{uuid4()}/team")
    assert response.status_code == 401


async def test_incident_overflow_is_discoverable_sellable_and_takeable(
    async_client, async_session, normal_user_token_headers
):
    vault = await _vault(async_session, 987)
    room = await _room(async_session, vault)
    incident = await _incident(async_session, vault, room, IncidentType.RAIDER_ATTACK)

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
