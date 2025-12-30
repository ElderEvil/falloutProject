import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_dweller


@pytest.mark.asyncio
async def test_create_dweller(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    room: Room,
    dweller_data: dict,
) -> None:
    dweller_data.update({"vault_id": str(room.vault_id), "room_id": str(room.id)})
    response = await async_client.post("/dwellers/", json=dweller_data, headers=superuser_token_headers)
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
    assert "status" in response_data


@pytest.mark.asyncio
async def test_read_dweller_list(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
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
    response = await async_client.get("/dwellers/", headers=superuser_token_headers)
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 2
    for dweller in dwellers:
        assert "id" in dweller
        assert "first_name" in dweller
        assert "last_name" in dweller
        assert "level" in dweller
        assert "health" in dweller
        assert "max_health" in dweller
        assert "radiation" in dweller
        assert "happiness" in dweller
        assert "status" in dweller


@pytest.mark.asyncio
async def test_read_dweller(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    response = await async_client.get(f"/dwellers/{dweller.id}", headers=superuser_token_headers)
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
    assert "status" in response_data


@pytest.mark.asyncio
async def test_update_dweller(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    dweller_new_data = create_fake_dweller()
    update_response = await async_client.put(
        f"/dwellers/{dweller.id}", json=dweller_new_data, headers=superuser_token_headers
    )
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
async def test_delete_dweller(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    dweller: Dweller,
) -> None:
    delete_response = await async_client.delete(f"/dwellers/{dweller.id}", headers=superuser_token_headers)
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/dwellers/{dweller.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_filter_dwellers_by_status(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    room: Room,
) -> None:
    """Test filtering dwellers by status."""
    from app.schemas.common import DwellerStatusEnum  # noqa: PLC0415
    from app.schemas.dweller import DwellerCreate, DwellerUpdate  # noqa: PLC0415

    # Create dwellers with different statuses
    dweller_1_data = create_fake_dweller()
    dweller_2_data = create_fake_dweller()
    dweller_1_data.update({"vault_id": str(room.vault_id), "room_id": str(room.id)})
    dweller_2_data.update({"vault_id": str(room.vault_id)})

    dweller_1_in = DwellerCreate(**dweller_1_data)
    dweller_2_in = DwellerCreate(**dweller_2_data)

    dweller_1 = await crud.dweller.create(async_session, dweller_1_in)
    dweller_2 = await crud.dweller.create(async_session, dweller_2_in)  # noqa: F841

    # Update dweller_1 to WORKING status
    await crud.dweller.update(async_session, dweller_1.id, DwellerUpdate(status=DwellerStatusEnum.WORKING))
    # dweller_2 stays IDLE

    # Filter by WORKING status
    response = await async_client.get(
        f"/dwellers/vault/{room.vault_id}/?status=working", headers=superuser_token_headers
    )
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 1
    assert dwellers[0]["status"] == "working"

    # Filter by IDLE status
    response = await async_client.get(f"/dwellers/vault/{room.vault_id}/?status=idle", headers=superuser_token_headers)
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 1
    assert dwellers[0]["status"] == "idle"


@pytest.mark.asyncio
async def test_search_dwellers_by_name(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    room: Room,
) -> None:
    """Test searching dwellers by name."""
    from app.schemas.dweller import DwellerCreate  # noqa: PLC0415

    # Create dwellers with specific names
    dweller_1_data = create_fake_dweller()
    dweller_2_data = create_fake_dweller()
    dweller_1_data.update(
        {
            "first_name": "John",
            "last_name": "Smith",
            "vault_id": str(room.vault_id),
        }
    )
    dweller_2_data.update(
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "vault_id": str(room.vault_id),
        }
    )

    dweller_1_in = DwellerCreate(**dweller_1_data)
    dweller_2_in = DwellerCreate(**dweller_2_data)

    await crud.dweller.create(async_session, dweller_1_in)
    await crud.dweller.create(async_session, dweller_2_in)

    # Search by first name
    response = await async_client.get(f"/dwellers/vault/{room.vault_id}/?search=John", headers=superuser_token_headers)
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 1
    assert dwellers[0]["first_name"] == "John"

    # Search by last name (case insensitive)
    response = await async_client.get(f"/dwellers/vault/{room.vault_id}/?search=doe", headers=superuser_token_headers)
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 1
    assert dwellers[0]["last_name"] == "Doe"


@pytest.mark.asyncio
async def test_sort_dwellers(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    room: Room,
) -> None:
    """Test sorting dwellers."""
    from app.schemas.dweller import DwellerCreate  # noqa: PLC0415

    # Create dwellers with different levels
    dweller_1_data = create_fake_dweller()
    dweller_2_data = create_fake_dweller()
    dweller_1_data.update({"level": 5, "vault_id": str(room.vault_id)})
    dweller_2_data.update({"level": 10, "vault_id": str(room.vault_id)})

    dweller_1_in = DwellerCreate(**dweller_1_data)
    dweller_2_in = DwellerCreate(**dweller_2_data)

    await crud.dweller.create(async_session, dweller_1_in)
    await crud.dweller.create(async_session, dweller_2_in)

    # Sort by level ascending
    response = await async_client.get(
        f"/dwellers/vault/{room.vault_id}/?sort_by=level&order=asc", headers=superuser_token_headers
    )
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 2
    assert dwellers[0]["level"] == 5
    assert dwellers[1]["level"] == 10

    # Sort by level descending
    response = await async_client.get(
        f"/dwellers/vault/{room.vault_id}/?sort_by=level&order=desc", headers=superuser_token_headers
    )
    assert response.status_code == 200
    dwellers = response.json()
    assert len(dwellers) == 2
    assert dwellers[0]["level"] == 10
    assert dwellers[1]["level"] == 5
