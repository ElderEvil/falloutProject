import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.vault import Vault
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
async def test_read_room_list(async_client: AsyncClient, async_session: AsyncSession):
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_obj = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_obj)
    room_1_data = create_fake_room()
    room_2_data = create_fake_room()
    room_1 = RoomCreate(**room_1_data, vault_id=vault.id)
    room_2 = RoomCreate(**room_2_data, vault_id=vault.id)
    await crud.room.create(async_session, room_1)
    await crud.room.create(async_session, room_2)
    response = await async_client.get("/rooms/")
    all_rooms = response.json()
    assert response.status_code == 200
    assert len(all_rooms) == 2
    response_room_1, response_room_2 = all_rooms
    if response_room_1["name"] == room_2.name:
        response_room_1, response_room_2 = response_room_2, response_room_1
    assert response_room_1["name"] == room_1.name
    assert response_room_1["category"] == room_1.category
    assert response_room_1["ability"] == room_1.ability
    assert response_room_1["population_required"] == room_1.population_required
    assert response_room_1["base_cost"] == room_1.base_cost
    assert response_room_1["incremental_cost"] == room_1.incremental_cost
    assert response_room_1["tier"] == room_1.tier
    assert response_room_1["max_tier"] == room_1.max_tier
    assert response_room_1["t2_upgrade_cost"] == room_1.t2_upgrade_cost
    assert response_room_1["t3_upgrade_cost"] == room_1.t3_upgrade_cost
    assert response_room_1["output"] == room_1.output
    assert response_room_1["size"] == room_1.size

    assert response_room_2["name"] == room_2.name
    assert response_room_2["category"] == room_2.category
    assert response_room_2["ability"] == room_2.ability
    assert response_room_2["population_required"] == room_2.population_required
    assert response_room_2["base_cost"] == room_2.base_cost
    assert response_room_2["incremental_cost"] == room_2.incremental_cost
    assert response_room_2["tier"] == room_2.tier
    assert response_room_2["max_tier"] == room_2.max_tier
    assert response_room_2["t2_upgrade_cost"] == room_2.t2_upgrade_cost
    assert response_room_2["t3_upgrade_cost"] == room_2.t3_upgrade_cost
    assert response_room_2["output"] == room_2.output
    assert response_room_2["size"] == room_2.size


@pytest.mark.asyncio
async def test_read_room(async_client: AsyncClient, async_session: AsyncSession):
    room_data = create_fake_room()
    room_obj = RoomCreate(**room_data)
    created_room = await crud.room.create(async_session, room_obj)
    response = await async_client.get(f"/rooms/{created_room.id}")
    assert response.status_code == 200
    response_room = response.json()
    assert response_room["name"] == room_obj.name
    assert response_room["category"] == room_obj.category
    assert response_room["ability"] == room_obj.ability
    assert response_room["population_required"] == room_obj.population_required
    assert response_room["base_cost"] == room_obj.base_cost
    assert response_room["incremental_cost"] == room_obj.incremental_cost
    assert response_room["tier"] == room_obj.tier
    assert response_room["max_tier"] == room_obj.max_tier
    assert response_room["t2_upgrade_cost"] == room_obj.t2_upgrade_cost
    assert response_room["t3_upgrade_cost"] == room_obj.t3_upgrade_cost
    assert response_room["output"] == room_obj.output
    assert response_room["size"] == room_obj.size


@pytest.mark.asyncio
async def test_update_room(async_client: AsyncClient):
    room_data = create_fake_room()
    response = await async_client.post("/rooms/", json=room_data)
    room_response = response.json()
    room_id = room_response["id"]
    room_new_data = create_fake_room()
    update_response = await async_client.put(f"/rooms/{room_id}", json=room_new_data)
    updated_room = update_response.json()
    assert update_response.status_code == 200
    assert updated_room["id"] == room_id
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
    assert updated_room["size"] == room_new_data["size"]


@pytest.mark.asyncio
async def test_delete_room(async_client: AsyncClient):
    room_data = create_fake_room()
    create_response = await async_client.post("/rooms/", json=room_data)
    created_room = create_response.json()
    delete_response = await async_client.delete(f"/rooms/{created_room['id']}")
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/rooms/{created_room['id']}")
    assert read_response.status_code == 404
