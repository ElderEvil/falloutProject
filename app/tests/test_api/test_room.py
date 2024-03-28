import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.vault import Vault
from app.models.room import Room
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_create_room(async_client: AsyncClient, async_session: AsyncSession, vault: Vault, room_data: dict):
    room_data.update({"vault_id": str(vault.id)})
    response = await async_client.post(f"/rooms/{vault.id}", json=room_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == room_data["name"]
    assert response_data["category"] == room_data["category"]
    assert response_data["ability"] == room_data["ability"]
    assert response_data["population_required"] == room_data["population_required"]
    assert response_data["base_cost"] == room_data["base_cost"]
    assert response_data["incremental_cost"] == room_data["incremental_cost"]
    assert response_data["tier"] == room_data["tier"]
    assert response_data["max_tier"] == room_data["max_tier"]
    assert response_data["t2_upgrade_cost"] == room_data["t2_upgrade_cost"]
    assert response_data["t3_upgrade_cost"] == room_data["t3_upgrade_cost"]
    assert response_data["output"] == room_data["output"]
    assert response_data["size_min"] == room_data["size_min"]
    assert response_data["size_max"] == room_data["size_max"]


@pytest.mark.asyncio
async def test_create_room_incomplete(async_client: AsyncClient, vault: Vault):
    response = await async_client.post(
        f"/rooms/{vault.id}",
        json={"name": "Test Room"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_room_invalid(async_client: AsyncClient, vault: Vault):
    response = await async_client.post(
        f"/rooms/{vault.id}",
        json={
            "name": "Test Room",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_read_room_list(async_client: AsyncClient, async_session: AsyncSession, room: Room):
    room_2_data = create_fake_room()
    room_2 = RoomCreate(**room_2_data, vault_id=room.vault_id)
    await crud.room.create(async_session, room_2)
    response = await async_client.get("/rooms/")
    rooms = response.json()
    assert response.status_code == 200
    assert len(rooms) == 2
    for room in rooms:
        assert "id" in room
        assert "name" in room
        assert "category" in room
        assert "ability" in room
        assert "population_required" in room
        assert "base_cost" in room
        assert "incremental_cost" in room
        assert "tier" in room
        assert "max_tier" in room
        assert "t2_upgrade_cost" in room
        assert "t3_upgrade_cost" in room
        assert "output" in room
        assert "size_min" in room
        assert "size_max" in room



@pytest.mark.asyncio
async def test_read_room(async_client: AsyncClient, async_session: AsyncSession, room: Room):
    response = await async_client.get(f"/rooms/{room.id}")
    assert response.status_code == 200
    response_room = response.json()
    assert response_room["name"] == room.name
    assert response_room["category"] == room.category
    assert response_room["ability"] == room.ability
    assert response_room["population_required"] == room.population_required
    assert response_room["base_cost"] == room.base_cost
    assert response_room["incremental_cost"] == room.incremental_cost
    assert response_room["tier"] == room.tier
    assert response_room["max_tier"] == room.max_tier
    assert response_room["t2_upgrade_cost"] == room.t2_upgrade_cost
    assert response_room["t3_upgrade_cost"] == room.t3_upgrade_cost
    assert response_room["output"] == room.output
    assert response_room["size_min"] == room.size_min
    assert response_room["size_max"] == room.size_max



@pytest.mark.asyncio
async def test_update_room(async_client: AsyncClient, room: Room):
    room_new_data = create_fake_room()
    update_response = await async_client.put(f"/rooms/{room.id}", json=room_new_data)
    updated_room = update_response.json()
    assert update_response.status_code == 200
    assert updated_room["id"] == str(room.id)
    assert updated_room["name"] == room_new_data["name"]
    assert updated_room["category"] == room_new_data["category"]
    assert updated_room["ability"] == room_new_data["ability"]
    assert updated_room["population_required"] == room_new_data["population_required"]
    assert updated_room["base_cost"] == room_new_data["base_cost"]
    assert updated_room["incremental_cost"] == room_new_data["incremental_cost"]
    assert updated_room["tier"] == room_new_data["tier"]
    assert updated_room["max_tier"] == room_new_data["max_tier"]
    assert updated_room["t2_upgrade_cost"] == room_new_data["t2_upgrade_cost"]
    assert updated_room["t3_upgrade_cost"] == room_new_data["t3_upgrade_cost"]
    assert updated_room["output"] == room_new_data["output"]
    assert updated_room["size_min"] == room_new_data["size_min"]
    assert updated_room["size_max"] == room_new_data["size_max"]


@pytest.mark.asyncio
async def test_delete_room(async_client: AsyncClient, room: Room):
    delete_response = await async_client.delete(f"/rooms/{room.id}")
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/rooms/{room.id}")
    assert read_response.status_code == 404
