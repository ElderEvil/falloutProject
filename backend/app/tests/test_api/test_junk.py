import random

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.common import JunkTypeEnum
from app.schemas.junk import JunkCreate
from app.tests.utils.utils import random_lower_string

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_create_junk(async_client: AsyncClient, junk_data: dict):
    response = await async_client.post("/junk/", json=junk_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == junk_data["name"]
    assert response_data["rarity"] == junk_data["rarity"]
    assert response_data["value"] == junk_data["value"]
    assert response_data["junk_type"] == junk_data["junk_type"]
    assert response_data["description"] == junk_data["description"]


@pytest.mark.asyncio
async def test_create_junk_incomplete(async_client: AsyncClient):
    response = await async_client.post(
        "/junk/",
        json={"name": "Test Junk"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_junk_invalid(async_client: AsyncClient):
    response = await async_client.post(
        "/junk/",
        json={
            "name": "Test Junk",
            "rarity": "Unique",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_read_junk_list(async_client: AsyncClient, async_session: AsyncSession, junk_data: dict):
    junk_data_2 = {
        "name": "Test Junk 2",
        "rarity": "Common",
        "value": 10,
        "junk_type": "Adhesive",
        "description": "Very sticky.",
    }
    junk_obj_1 = JunkCreate(**junk_data)
    junk_obj_2 = JunkCreate(**junk_data_2)
    await crud.junk.create(async_session, junk_obj_1)
    await crud.junk.create(async_session, junk_obj_2)
    response = await async_client.get("/junk/")
    all_junk = response.json()
    assert response.status_code == 200
    assert len(all_junk) == 2

    response_junk_1, response_junk_2 = all_junk
    if response_junk_1["name"] == junk_obj_2.name:
        response_junk_1, response_junk_2 = response_junk_2, response_junk_1

    assert response_junk_1["name"] == junk_obj_1.name
    assert response_junk_1["rarity"] == junk_obj_1.rarity
    assert response_junk_1["value"] == junk_obj_1.value
    assert response_junk_1["junk_type"] == junk_obj_1.junk_type
    assert response_junk_1["description"] == junk_obj_1.description

    assert response_junk_2["name"] == junk_obj_2.name
    assert response_junk_2["rarity"] == junk_obj_2.rarity
    assert response_junk_2["value"] == junk_obj_2.value
    assert response_junk_2["junk_type"] == junk_obj_2.junk_type
    assert response_junk_2["description"] == junk_obj_2.description


@pytest.mark.asyncio
async def test_read_junk(async_client: AsyncClient, async_session: AsyncSession, junk_data: dict):
    junk_obj = JunkCreate(**junk_data)
    junk_item = await crud.junk.create(async_session, junk_obj)
    response = await async_client.get(f"/junk/{junk_item.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == junk_data["name"]
    assert data["rarity"] == junk_data["rarity"]
    assert data["value"] == junk_data["value"]
    assert data["junk_type"] == junk_data["junk_type"]
    assert data["description"] == junk_data["description"]


@pytest.mark.asyncio
async def test_update_junk(async_client: AsyncClient, junk_data: dict):
    response = await async_client.post("/junk/", json=junk_data)
    junk_item = response.json()
    junk_new_data = {
        "name": random_lower_string(16).capitalize(),
        "rarity": "legendary",
        "value": random.randint(1, 1_000),
        "junk_type": random.choice(list(JunkTypeEnum)),
        "description": random_lower_string(16),
    }
    update_response = await async_client.put(f"/junk/{junk_item['id']}", json=junk_new_data)
    updated_junk = update_response.json()
    assert update_response.status_code == 200
    assert updated_junk["name"] == junk_new_data["name"]
    assert updated_junk["rarity"] == junk_new_data["rarity"]
    assert updated_junk["value"] == junk_new_data["value"]
    assert updated_junk["junk_type"] == junk_new_data["junk_type"]
    assert updated_junk["description"] == junk_new_data["description"]


@pytest.mark.asyncio
async def test_delete_junk(async_client: AsyncClient, junk_data: dict):
    create_response = await async_client.post("/junk/", json=junk_data)
    created_junk = create_response.json()
    delete_response = await async_client.delete(f"/junk/{created_junk['id']}")
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/junk/{created_junk['id']}")
    assert read_response.status_code == 404
