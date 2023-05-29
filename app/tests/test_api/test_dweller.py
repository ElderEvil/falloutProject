import pytest

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_dweller


@pytest.mark.asyncio
async def test_create_dweller(client: AsyncClient):
    dweller_data = create_fake_dweller()
    response = await client.post("/dwellers/", json=dweller_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["first_name"] == dweller_data["first_name"]
    assert response_data["last_name"] == dweller_data["last_name"]
    assert response_data["rarity"] == dweller_data["rarity"]
    assert response_data["level"] == dweller_data["level"]
    assert response_data["experience"] == dweller_data["experience"]
    assert response_data["max_health"] == dweller_data["max_health"]
    assert response_data["health"] == dweller_data["health"]
    assert response_data["happiness"] == dweller_data["happiness"]
    assert response_data["is_adult"] == dweller_data["is_adult"]


@pytest.mark.asyncio
async def test_read_dwellers(session: AsyncSession, client: AsyncClient):
    dweller_1_data = create_fake_dweller()
    dweller_2_data = create_fake_dweller()

    dweller_1 = DwellerCreate(**dweller_1_data)
    crud.dweller.create(session, dweller_1)

    dweller_2 = DwellerCreate(**dweller_2_data)
    crud.dweller.create(session, dweller_2)

    response = await client.get("/dwellers/")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_read_dweller(session: AsyncSession, client: AsyncClient):
    dweller_data = create_fake_dweller()

    dweller_1 = DwellerCreate(**dweller_data)
    created_dweller = crud.dweller.create(session, dweller_1)

    response = await client.get(f"/dwellers/{created_dweller.id}/")

    assert response.status_code == 200

    response_dweller = response.json()
    assert response_dweller["first_name"] == dweller_1.first_name
    assert response_dweller["last_name"] == dweller_1.last_name
    assert response_dweller["gender"] == dweller_1.gender
    assert response_dweller["rarity"] == dweller_1.rarity
    assert response_dweller["level"] == dweller_1.level
    assert response_dweller["experience"] == dweller_1.experience
    assert response_dweller["max_health"] == dweller_1.max_health
    assert response_dweller["health"] == dweller_1.health
    assert response_dweller["happiness"] == dweller_1.happiness
    assert response_dweller["is_adult"] == dweller_1.is_adult


@pytest.mark.asyncio
async def test_update_dweller(session: AsyncSession, client: AsyncClient):
    dweller_data = create_fake_dweller()
    response = await client.post("/dwellers/", json=dweller_data)
    dweller_response = response.json()
    dweller_id = dweller_response["id"]
    dweller_new_data = create_fake_dweller()

    update_response = await client.put(f"/dwellers/{dweller_id}", json=dweller_new_data)
    updated_dweller = update_response.json()

    assert update_response.status_code == 200
    assert updated_dweller["id"] == dweller_id
    assert updated_dweller["first_name"] == dweller_new_data["first_name"]
    assert updated_dweller["last_name"] == dweller_new_data["last_name"]
    assert updated_dweller["gender"] == dweller_new_data["gender"].value
    assert updated_dweller["rarity"] == dweller_new_data["rarity"].value
    assert updated_dweller["level"] == dweller_new_data["level"]
    assert updated_dweller["experience"] == dweller_new_data["experience"]
    assert updated_dweller["max_health"] == dweller_new_data["max_health"]
    assert updated_dweller["health"] == dweller_new_data["health"]
    assert updated_dweller["happiness"] == dweller_new_data["happiness"]
    assert updated_dweller["is_adult"] == dweller_new_data["is_adult"]


def test_delete_dweller(session: AsyncSession, client: AsyncClient):
    dweller_data = create_fake_dweller()
    create_response = client.post(f"{settings.API_V1_STR}/dwellers/", json=dweller_data)
    created_dweller = create_response.json()

    delete_response = client.delete(f"{settings.API_V1_STR}/dwellers/{created_dweller['id']}")

    assert delete_response.status_code == 204

    # TODO Check that the dweller is actually deleted
    # read_response = client.get(f"{settings.API_V1_STR}/dwellers/{dweller_1['id']}")
    # assert read_response.status_code == 404
