import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.weapon import WeaponCreate
from app.tests.factory.items import create_fake_weapon


@pytest.mark.asyncio
async def test_create_weapon(async_client: AsyncClient):
    weapon_data = create_fake_weapon()
    response = await async_client.post("/weapons/", json=weapon_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == weapon_data["name"]
    assert response_data["rarity"] == weapon_data["rarity"]
    assert response_data["value"] == weapon_data["value"]
    assert response_data["weapon_type"] == weapon_data["weapon_type"]
    assert response_data["weapon_subtype"] == weapon_data["weapon_subtype"]
    assert response_data["stat"] == weapon_data["stat"]
    assert response_data["damage_min"] == weapon_data["damage_min"]
    assert response_data["damage_max"] == weapon_data["damage_max"]


@pytest.mark.asyncio
async def test_create_weapon_incomplete(async_client: AsyncClient):
    response = await async_client.post(
        "/weapons/",
        json={"name": "Test Weapon"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_weapon_invalid(async_client: AsyncClient):
    response = await async_client.post(
        "/weapons/",
        json={
            "name": "Test Weapon",
            "rarity": "Unique",
            "weapon_type": ["Melee"],
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_read_weapon_list(async_client: AsyncClient, async_session: AsyncSession):
    weapon_1_data = create_fake_weapon()
    weapon_2_data = create_fake_weapon()
    weapon_1 = WeaponCreate(**weapon_1_data)
    weapon_2 = WeaponCreate(**weapon_2_data)
    await crud.weapon.create(async_session, weapon_1)
    await crud.weapon.create(async_session, weapon_2)
    response = await async_client.get("/weapons/")
    all_weapons = response.json()
    assert response.status_code == 200
    assert len(all_weapons) == 2
    response_weapon_1, response_weapon_2 = all_weapons
    if response_weapon_1["name"] == weapon_2.name:
        response_weapon_1, response_weapon_2 = response_weapon_2, response_weapon_1
    assert response_weapon_1["name"] == weapon_1.name
    assert response_weapon_1["rarity"] == weapon_1.rarity.value
    assert response_weapon_1["value"] == response_weapon_1["value"]
    assert response_weapon_1["weapon_type"] == weapon_1.weapon_type.value
    assert response_weapon_1["weapon_subtype"] == weapon_1.weapon_subtype.value
    assert response_weapon_1["stat"] == weapon_1.stat
    assert response_weapon_1["damage_min"] == weapon_1.damage_min
    assert response_weapon_1["damage_max"] == weapon_1.damage_max

    assert response_weapon_2["name"] == weapon_2.name
    assert response_weapon_2["rarity"] == weapon_2.rarity.value
    assert response_weapon_2["value"] == response_weapon_2["value"]
    assert response_weapon_2["weapon_type"] == weapon_2.weapon_type.value
    assert response_weapon_2["weapon_subtype"] == weapon_2.weapon_subtype.value
    assert response_weapon_2["stat"] == weapon_2.stat
    assert response_weapon_2["damage_min"] == weapon_2.damage_min
    assert response_weapon_2["damage_max"] == weapon_2.damage_max


@pytest.mark.asyncio
async def test_read_weapon(async_client: AsyncClient, async_session: AsyncSession, weapon_data: dict):
    weapon_obj = WeaponCreate(**weapon_data)
    created_weapon = await crud.weapon.create(async_session, weapon_obj)
    response = await async_client.get(f"/weapons/{created_weapon.id}")
    assert response.status_code == 200
    response_weapon = response.json()
    assert response_weapon["name"] == weapon_obj.name
    assert response_weapon["rarity"] == weapon_obj.rarity.value
    assert response_weapon["weapon_type"] == weapon_obj.weapon_type.value
    assert response_weapon["weapon_subtype"] == weapon_obj.weapon_subtype.value
    assert response_weapon["stat"] == weapon_obj.stat
    assert response_weapon["damage_min"] == weapon_obj.damage_min
    assert response_weapon["damage_max"] == weapon_obj.damage_max


@pytest.mark.asyncio
async def test_update_weapon(async_client: AsyncClient):
    weapon_data = create_fake_weapon()
    response = await async_client.post("/weapons/", json=weapon_data)
    weapon_response = response.json()
    weapon_id = weapon_response["id"]
    weapon_new_data = create_fake_weapon()
    update_response = await async_client.put(f"/weapons/{weapon_id}", json=weapon_new_data)
    updated_weapon = update_response.json()
    assert update_response.status_code == 200
    assert updated_weapon["id"] == weapon_id
    assert updated_weapon["name"] == weapon_new_data["name"]
    assert updated_weapon["rarity"] == weapon_new_data["rarity"]
    assert updated_weapon["weapon_type"] == weapon_new_data["weapon_type"]
    assert updated_weapon["weapon_subtype"] == weapon_new_data["weapon_subtype"]
    assert updated_weapon["stat"] == weapon_new_data["stat"]
    assert updated_weapon["damage_min"] == weapon_new_data["damage_min"]
    assert updated_weapon["damage_max"] == weapon_new_data["damage_max"]


@pytest.mark.asyncio
async def test_delete_weapon(async_client: AsyncClient):
    weapon_data = create_fake_weapon()
    create_response = await async_client.post("/weapons/", json=weapon_data)
    weapon_1 = create_response.json()
    delete_response = await async_client.delete(f"/weapons/{weapon_1['id']}")
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/weapons/{weapon_1['id']}")
    assert read_response.status_code == 404
