"""Tests for radio recruitment API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.room import RoomCreate

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_get_radio_stats_no_radio(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test getting radio stats when vault has no radio room."""
    # Create vault
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 999},
        user_id=user.id,
    )

    response = await async_client.get(
        f"/radio/vault/{vault.id}/stats",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_radio"] is False
    assert data["recruitment_rate"] == 0.0
    assert data["radio_rooms_count"] == 0
    assert data["manual_cost_caps"] == 500
    assert data["radio_mode"] in ["recruitment", "happiness"]


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


@pytest.mark.asyncio
async def test_manual_recruit_no_radio(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test manual recruitment fails when vault has no radio room."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 997, "bottle_caps": 1000},
        user_id=user.id,
    )

    response = await async_client.post(
        f"/radio/vault/{vault.id}/recruit",
        headers=superuser_token_headers,
        json={},
    )
    assert response.status_code == 400
    assert "No radio room" in response.json()["detail"]


@pytest.mark.skip(reason="FIXME: Session isolation issue - dweller created in test not visible to service query")
@pytest.mark.asyncio
async def test_manual_recruit_insufficient_caps(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test manual recruitment fails with insufficient caps."""
    from app.schemas.dweller import DwellerCreate
    from app.schemas.common import GenderEnum, AgeGroupEnum, RarityEnum, SPECIALEnum

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 996, "bottle_caps": 100},  # Not enough caps
        user_id=user.id,
    )

    radio_room_data = {
        "name": "Radio Studio",
        "category": "misc.",
        "ability": "CHARISMA",
        "population_required": None,
        "base_cost": 100,
        "incremental_cost": 50,
        "t2_upgrade_cost": 500,
        "t3_upgrade_cost": 1500,
        "capacity": 2,
        "output": None,
        "size_min": 1,
        "size_max": 3,
        "size": 2,
        "tier": 1,
        "coordinate_x": 0,
        "coordinate_y": 0,
        "image_url": None,
    }
    room_in = RoomCreate(**radio_room_data, vault_id=vault.id)
    room = await crud.room.create(db_session=async_session, obj_in=room_in)

    dweller_data = DwellerCreate(
        first_name="Test",
        last_name="DJ",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        age_group=AgeGroupEnum.ADULT,
        level=5,
        experience=100,
        max_health=100,
        health=100,
        radiation=0,
        happiness=80,
        room_id=room.id,
        strength=3,
        perception=4,
        endurance=4,
        charisma=10,
        intelligence=5,
        agility=4,
        luck=5,
        vault_id=vault.id,
    )
    await crud.dweller.create(db_session=async_session, obj_in=dweller_data)

    response = await async_client.post(
        f"/radio/vault/{vault.id}/recruit",
        headers=superuser_token_headers,
        json={},
    )
    assert response.status_code == 400
    assert "Insufficient caps" in response.json()["detail"]


@pytest.mark.skip(reason="FIXME: Session isolation issue - dweller created in test not visible to service query")
@pytest.mark.asyncio
async def test_manual_recruit_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test successful manual recruitment."""
    from app.schemas.dweller import DwellerCreate
    from app.schemas.common import GenderEnum, AgeGroupEnum, RarityEnum

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
    await crud.dweller.create(async_session, dweller_data)
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
async def test_set_radio_speedup_invalid_range(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test setting speedup outside valid range fails."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 992},
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

    # Try to set speedup to 15.0x (out of range)
    response = await async_client.put(
        f"/radio/vault/{vault.id}/room/{room.id}/speedup",
        headers=superuser_token_headers,
        params={"speedup": 15.0},
    )
    assert response.status_code == 400
    assert "between 1.0 and 10.0" in response.json()["detail"]
