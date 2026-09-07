"""Tests for radio recruitment API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.room import RoomCreate

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_get_radio_stats_with_radio(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test getting radio stats when vault has a radio room."""
    # Create vault
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 998},
        user_id=user.id,
    )

    # Create radio room
    radio_room = RoomCreate(
        name="Radio Studio",
        vault_id=vault.id,
        tier=1,
        size=2,
        coordinate_x=1,
        coordinate_y=1,
        category="misc.",
        ability=None,
        capacity=None,
        output=None,
        base_cost=100,
        incremental_cost=50,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=1,
        size_max=3,
    )
    await crud.room.create(async_session, radio_room)

    response = await async_client.get(
        f"/radio/vault/{vault.id}/stats",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_radio"] is True
    assert data["radio_rooms_count"] == 1
    assert data["recruitment_rate"] >= 0.0
    assert "speedup_multipliers" in data
    assert len(data["speedup_multipliers"]) == 1


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_manual_recruit_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test successful manual recruitment."""
    from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
    from app.schemas.dweller import DwellerCreate

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 995, "bottle_caps": 1000},
        user_id=user.id,
    )

    # Create radio room
    radio_room = RoomCreate(
        name="Radio Studio",
        vault_id=vault.id,
        tier=1,
        size=2,
        coordinate_x=1,
        coordinate_y=1,
        category="misc.",
        ability=None,
        capacity=None,
        output=None,
        base_cost=100,
        incremental_cost=50,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=1,
        size_max=3,
    )
    room = await crud.room.create(async_session, radio_room)

    dweller_data = DwellerCreate(
        first_name="Test",
        last_name="DJ",
        gender=GenderEnum.MALE,
        age_group=AgeGroupEnum.ADULT,
        rarity=RarityEnum.COMMON,
        vault_id=vault.id,
        room_id=room.id,
    )
    dweller = await crud.dweller.create(async_session, dweller_data)
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()

    response = await async_client.post(
        f"/radio/vault/{vault.id}/recruit",
        headers=superuser_token_headers,
        json={},
    )
    assert response.status_code == 200
    data = response.json()
    assert "dweller" in data
    assert "message" in data
    assert data["caps_spent"] == 500


@pytest.mark.asyncio
async def test_set_radio_mode(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test setting radio mode."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 994},
        user_id=user.id,
    )

    # Set to happiness mode
    response = await async_client.put(
        f"/radio/vault/{vault.id}/mode",
        headers=superuser_token_headers,
        params={"mode": "happiness"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["radio_mode"] == "happiness"
    assert "happiness" in data["message"].lower()


@pytest.mark.asyncio
async def test_set_radio_speedup(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test setting radio room speedup multiplier."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 993},
        user_id=user.id,
    )

    # Create radio room
    radio_room = RoomCreate(
        name="Radio Studio",
        vault_id=vault.id,
        tier=1,
        size=2,
        coordinate_x=1,
        coordinate_y=1,
        category="misc.",
        ability=None,
        capacity=None,
        output=None,
        base_cost=100,
        incremental_cost=50,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=1,
        size_max=3,
    )
    room = await crud.room.create(async_session, radio_room)

    # Set speedup to 5.0x
    response = await async_client.put(
        f"/radio/vault/{vault.id}/room/{room.id}/speedup",
        headers=superuser_token_headers,
        params={"speedup": 5.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["speedup"] == 5.0
    assert data["room_id"] == str(room.id)


@pytest.mark.asyncio
async def test_manual_recruit_does_not_break_subsequent_api_calls(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """
    BUG REPRODUCTION TEST: Recruiting a dweller causes logout/404 on subsequent API calls.

    Steps to reproduce:
    1. User successfully accesses their vault (verify auth works)
    2. User recruits a dweller with caps
    3. User tries to fetch dwellers - gets 404 (appears logged out)

    Expected: All API calls succeed with same auth token
    Actual: After recruitment, user appears logged out (404 errors)
    """
    from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
    from app.schemas.dweller import DwellerCreate

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 990, "bottle_caps": 10000},
        user_id=user.id,
    )

    radio_room = RoomCreate(
        name="Radio Studio",
        vault_id=vault.id,
        tier=1,
        size=2,
        coordinate_x=1,
        coordinate_y=1,
        category="misc.",
        ability="CHARISMA",
        capacity=2,
        output=None,
        base_cost=100,
        incremental_cost=50,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=1,
        size_max=3,
    )
    room = await crud.room.create(async_session, radio_room)

    dweller_data = DwellerCreate(
        first_name="Radio",
        last_name="Host",
        gender=GenderEnum.FEMALE,
        age_group=AgeGroupEnum.ADULT,
        rarity=RarityEnum.COMMON,
        vault_id=vault.id,
        room_id=room.id,
    )
    dweller = await crud.dweller.create(async_session, dweller_data)
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()

    response = await async_client.get(
        f"/vaults/{vault.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, "Pre-recruitment: Should access vault"
    vault_before = response.json()
    initial_caps = vault_before["bottle_caps"]

    response = await async_client.get(
        f"/dwellers/vault/{vault.id}/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, "Pre-recruitment: Should fetch dwellers"
    initial_dweller_count = len(response.json())

    response = await async_client.post(
        f"/radio/vault/{vault.id}/recruit",
        headers=superuser_token_headers,
        json={},
    )
    assert response.status_code == 200, (
        f"Recruitment failed: {response.json() if response.status_code != 200 else 'OK'}"
    )
    recruit_data = response.json()
    assert "dweller" in recruit_data
    assert recruit_data["caps_spent"] == 500

    response = await async_client.get(
        f"/vaults/{vault.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, (
        f"BUG REPRODUCED: Post-recruitment vault access failed with {response.status_code}. "
        f"User appears logged out after recruitment. Response: "
        f"{response.json() if response.status_code != 200 else 'OK'}"
    )
    vault_after = response.json()
    assert vault_after["bottle_caps"] == initial_caps - 500, "Caps should be deducted"

    response = await async_client.get(
        f"/dwellers/vault/{vault.id}/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200, (
        f"BUG REPRODUCED: Post-recruitment dweller fetch failed with {response.status_code}. "
        f"This is the main symptom - user gets 404 when fetching dwellers after recruitment. "
        f"Response: {response.json() if response.status_code != 200 else 'OK'}"
    )
    dwellers_after = response.json()
    assert len(dwellers_after) == initial_dweller_count + 1, "Should have one more dweller"

    response = await async_client.get(
        "/users/me",
        headers=superuser_token_headers,
        follow_redirects=False,
    )
    assert response.status_code == 200, (
        f"BUG REPRODUCED: Post-recruitment user profile access failed with {response.status_code}. "
        f"Auth token should still be valid. Response: {response.json() if response.status_code != 200 else 'OK'}"
    )
