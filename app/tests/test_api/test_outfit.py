import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.outfit import OutfitCreate
from app.tests.factory.items import create_fake_outfit


@pytest.mark.asyncio
async def test_create_outfit(async_client: AsyncClient):
    outfit_data = create_fake_outfit()
    response = await async_client.post("/outfits/", json=outfit_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == outfit_data["name"]
    assert response_data["rarity"] == outfit_data["rarity"]
    assert response_data["value"] == outfit_data["value"]
    assert response_data["outfit_type"] == outfit_data["outfit_type"]


@pytest.mark.asyncio
async def test_create_outfit_incomplete(async_client: AsyncClient):
    response = await async_client.post(
        "/outfits/",
        json={"name": "Test Outfit"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_outfit_invalid(async_client: AsyncClient):
    response = await async_client.post(
        "/outfits/",
        json={
            "name": "Test Outfit",
            "rarity": "Unique",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_read_outfit_list(async_client: AsyncClient, async_session: AsyncSession):
    outfit_1_data = create_fake_outfit()
    outfit_2_data = create_fake_outfit()
    outfit_1 = OutfitCreate(**outfit_1_data)
    outfit_2 = OutfitCreate(**outfit_2_data)
    await crud.outfit.create(async_session, outfit_1)
    await crud.outfit.create(async_session, outfit_2)
    response = await async_client.get("/outfits/")
    all_outfits = response.json()
    assert response.status_code == 200
    assert len(all_outfits) == 2
    response_outfit_1, response_outfit_2 = all_outfits
    if response_outfit_1["name"] == outfit_2.name:
        response_outfit_1, response_outfit_2 = response_outfit_2, response_outfit_1
    assert response_outfit_1["name"] == outfit_1.name
    assert response_outfit_1["rarity"] == outfit_1.rarity
    assert response_outfit_1["value"] == outfit_1.value
    assert response_outfit_1["outfit_type"] == outfit_1.outfit_type
    assert response_outfit_1["gender"] == outfit_1.gender

    assert response_outfit_2["name"] == outfit_2.name
    assert response_outfit_2["rarity"] == outfit_2.rarity
    assert response_outfit_2["value"] == outfit_2.value
    assert response_outfit_2["outfit_type"] == outfit_2.outfit_type
    assert response_outfit_2["gender"] == outfit_2.gender


@pytest.mark.asyncio
async def test_read_outfit(async_client: AsyncClient, async_session: AsyncSession):
    outfit_data = create_fake_outfit()
    outfit_obj = OutfitCreate(**outfit_data)
    created_outfit = await crud.outfit.create(async_session, outfit_obj)
    response = await async_client.get(f"/outfits/{created_outfit.id}")
    assert response.status_code == 200
    response_outfit = response.json()
    assert response_outfit["name"] == outfit_obj.name
    assert response_outfit["rarity"] == outfit_obj.rarity
    assert response_outfit["value"] == outfit_obj.value
    assert response_outfit["outfit_type"] == outfit_obj.outfit_type
    assert response_outfit["gender"] == outfit_obj.gender


@pytest.mark.asyncio
async def test_update_outfit(async_client: AsyncClient):
    outfit_data = create_fake_outfit()
    response = await async_client.post("/outfits/", json=outfit_data)
    outfit_response = response.json()
    outfit_id = outfit_response["id"]
    outfit_new_data = create_fake_outfit()
    update_response = await async_client.put(f"/outfits/{outfit_id}", json=outfit_new_data)
    updated_outfit = update_response.json()
    assert update_response.status_code == 200
    assert updated_outfit["id"] == outfit_id
    assert updated_outfit["name"] == outfit_new_data["name"]
    assert updated_outfit["rarity"] == outfit_new_data["rarity"]
    assert updated_outfit["value"] == outfit_new_data["value"]
    assert updated_outfit["outfit_type"] == outfit_new_data["outfit_type"]
    assert updated_outfit["gender"] == outfit_new_data["gender"]


@pytest.mark.asyncio
async def test_delete_outfit(async_client: AsyncClient):
    outfit_data = create_fake_outfit()
    create_response = await async_client.post("/outfits/", json=outfit_data)
    created_outfit = create_response.json()
    delete_response = await async_client.delete(f"/outfits/{created_outfit['id']}")
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/outfits/{created_outfit['id']}")
    assert read_response.status_code == 404
