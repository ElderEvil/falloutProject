from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.v1.endpoints.dweller import extend_bio
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.tests.factory.dwellers import create_fake_dweller


async def test_extend_bio_endpoint_delegates_to_ai_service() -> None:
    user = MagicMock()
    session = MagicMock()
    dweller_id = uuid4()
    expected = MagicMock()

    with patch("app.api.v1.endpoints.dweller.dweller_ai.extend_bio", new=AsyncMock(return_value=expected)) as extend:
        result = await extend_bio(dweller_id=dweller_id, user=user, db_session=session)

    assert result is expected
    extend.assert_awaited_once_with(db_session=session, dweller_id=dweller_id, user=user)


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
async def test_read_dweller_list_exposes_weapon_type(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    equipped_dweller: tuple[Dweller, object, object],
) -> None:
    """DwellerReadLess must serialize weapon_type without lazy-loading (MissingGreenlet guard)."""
    dweller, _, weapon = equipped_dweller
    response = await async_client.get("/dwellers/", headers=superuser_token_headers)
    assert response.status_code == 200
    by_id = {d["id"]: d for d in response.json()}
    assert by_id[str(dweller.id)]["weapon_type"] == weapon.weapon_type.value


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
    from app.schemas.common import DwellerStatusEnum
    from app.schemas.dweller import DwellerUpdate

    # Create dwellers with different statuses
    dweller_1_data = create_fake_dweller()
    dweller_2_data = create_fake_dweller()
    dweller_1_data.update({"vault_id": str(room.vault_id), "room_id": str(room.id)})
    dweller_2_data.update({"vault_id": str(room.vault_id)})

    dweller_1_in = DwellerCreate(**dweller_1_data)
    dweller_2_in = DwellerCreate(**dweller_2_data)

    dweller_1 = await crud.dweller.create(async_session, dweller_1_in)
    dweller_2 = await crud.dweller.create(async_session, dweller_2_in)

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


@pytest.mark.asyncio
async def test_read_dweller_lineage_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /dwellers/{id}/lineage returns 404 for a non-existent dweller."""
    response = await async_client.get(f"/dwellers/{uuid4()}/lineage", headers=superuser_token_headers)
    assert response.status_code == 404
