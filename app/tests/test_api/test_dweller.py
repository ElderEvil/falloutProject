import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_dweller


@pytest.mark.asyncio
async def test_create_dweller(async_client: AsyncClient, room: Room, dweller_data: dict) -> None:
    dweller_data.update({"vault_id": str(room.vault_id), "room_id": str(room.id)})
    response = await async_client.post("/dwellers/", json=dweller_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["first_name"] == dweller_data["first_name"]
    assert response_data["last_name"] == dweller_data["last_name"]
    assert response_data["is_adult"] == dweller_data["is_adult"]
    assert response_data["gender"] == dweller_data["gender"]
    assert response_data["rarity"] == dweller_data["rarity"]
    assert response_data["level"] == dweller_data["level"]
    assert response_data["experience"] == dweller_data["experience"]
    assert response_data["max_health"] == dweller_data["max_health"]
    assert response_data["health"] == dweller_data["health"]
    assert response_data["radiation"] == dweller_data["radiation"]
    assert response_data["happiness"] == dweller_data["happiness"]
    assert response_data["stimpack"] == dweller_data["stimpack"]
    assert response_data["radaway"] == dweller_data["radaway"]


@pytest.mark.asyncio
async def test_read_dweller_list(
    async_client: AsyncClient,
    async_session: AsyncSession,
    room: Room,
    dweller_data: dict,
) -> None:
    dweller_1_data = dweller_data
    dweller_2_data = create_fake_dweller()
    dweller_1_data.update({"vault_id": str(room.vault_id), "room_id": str(room.id)})
    dweller_2_data.update({"vault_id": str(room.vault_id), "room_id": str(room.id)})
    dweller_1 = DwellerCreate(**dweller_1_data)
    dweller_2 = DwellerCreate(**dweller_2_data)
    await crud.dweller.create(async_session, dweller_1)
    await crud.dweller.create(async_session, dweller_2)
    response = await async_client.get("/dwellers/")
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 2
    for dweller in dwellers:
        assert "id" in dweller
        assert "first_name" in dweller
        assert "last_name" in dweller
        assert "is_adult" in dweller
        assert "gender" in dweller
        assert "rarity" in dweller
        assert "level" in dweller
        assert "experience" in dweller
        assert "max_health" in dweller
        assert "health" in dweller
        assert "radiation" in dweller
        assert "happiness" in dweller
        assert "stimpack" in dweller
        assert "radaway" in dweller


@pytest.mark.asyncio
async def test_read_dweller(async_client: AsyncClient, async_session: AsyncSession, dweller: Dweller) -> None:
    response = await async_client.get(f"/dwellers/{dweller.id}")
    assert response.status_code == 200
    response_data = response.json()
    dweller_data = dweller.model_dump()
    assert response_data["first_name"] == dweller_data["first_name"]
    assert response_data["last_name"] == dweller_data["last_name"]
    assert response_data["is_adult"] == dweller_data["is_adult"]
    assert response_data["gender"] == dweller_data["gender"]
    assert response_data["rarity"] == dweller_data["rarity"]
    assert response_data["level"] == dweller_data["level"]
    assert response_data["experience"] == dweller_data["experience"]
    assert response_data["max_health"] == dweller_data["max_health"]
    assert response_data["health"] == dweller_data["health"]
    assert response_data["radiation"] == dweller_data["radiation"]
    assert response_data["happiness"] == dweller_data["happiness"]
    assert response_data["stimpack"] == dweller_data["stimpack"]
    assert response_data["radaway"] == dweller_data["radaway"]


@pytest.mark.asyncio
async def test_update_dweller(async_client: AsyncClient, dweller: Dweller) -> None:
    dweller_new_data = create_fake_dweller()
    update_response = await async_client.put(f"/dwellers/{dweller.id}", json=dweller_new_data)
    updated_dweller = update_response.json()
    assert update_response.status_code == 200
    assert updated_dweller["id"] == str(dweller.id)
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


@pytest.mark.asyncio
async def test_delete_dweller(async_client: AsyncClient, dweller: Dweller) -> None:
    delete_response = await async_client.delete(f"/dwellers/{dweller.id}")
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/dwellers/{dweller.id}")
    assert read_response.status_code == 404
