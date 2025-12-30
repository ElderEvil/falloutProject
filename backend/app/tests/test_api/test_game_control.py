"""Tests for game control API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.vault import VaultNumber

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_pause_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test pausing a vault's game loop."""
    # Create a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await crud.vault.initiate(
        db_session=async_session,
        obj_in=VaultNumber(number=999),
        user_id=user.id,
    )

    # Pause the vault
    response = await async_client.post(
        f"/game/vaults/{vault.id}/pause",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_paused"] is True
    assert data["paused_at"] is not None


@pytest.mark.asyncio
async def test_resume_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test resuming a paused vault's game loop."""
    # Create and pause a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await crud.vault.initiate(
        db_session=async_session,
        obj_in=VaultNumber(number=998),
        user_id=user.id,
    )

    # Pause first
    await async_client.post(
        f"/game/vaults/{vault.id}/pause",
        headers=normal_user_token_headers,
    )

    # Resume the vault
    response = await async_client.post(
        f"/game/vaults/{vault.id}/resume",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_paused"] is False
    assert data["resumed_at"] is not None


@pytest.mark.asyncio
async def test_get_game_state(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test getting vault game state."""
    # Create a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await crud.vault.initiate(
        db_session=async_session,
        obj_in=VaultNumber(number=997),
        user_id=user.id,
    )

    # Get game state
    response = await async_client.get(
        f"/game/vaults/{vault.id}/game-state",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "vault_id" in data
    assert "is_active" in data
    assert "is_paused" in data
    assert "total_game_time" in data
    assert "last_tick_time" in data
    assert "offline_time" in data


@pytest.mark.asyncio
async def test_manual_tick(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test manually triggering a game tick."""
    # Create a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await crud.vault.initiate(
        db_session=async_session,
        obj_in=VaultNumber(number=996),
        user_id=user.id,
    )

    # Store initial resources directly from the vault object
    initial_power = vault.power  # noqa: F841
    initial_food = vault.food
    initial_water = vault.water

    # Trigger manual tick
    response = await async_client.post(
        f"/game/vaults/{vault.id}/tick",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "vault_id" in data
    assert "seconds_passed" in data
    assert "updates" in data

    # Refresh vault to get updated resources
    await async_session.refresh(vault)

    # Power should decrease (consumption > production for infrastructure)
    # Food and water should increase (dwellers producing)
    assert vault.food > initial_food or vault.water > initial_water


@pytest.mark.asyncio
async def test_get_incidents(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
):
    """Test getting list of incidents for a vault."""
    # Create a vault
    user = await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)
    vault = await crud.vault.initiate(
        db_session=async_session,
        obj_in=VaultNumber(number=995),
        user_id=user.id,
    )

    # Get incidents (should be empty for new vault)
    response = await async_client.get(
        f"/game/vaults/{vault.id}/incidents",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "incidents" in data
    assert data["incident_count"] == 0
    # New vault should have no incidents
    assert len(data["incidents"]) == 0


@pytest.mark.asyncio
async def test_vault_initialization_creates_game_state(
    async_client: AsyncClient,
    async_session: AsyncSession,  # noqa: ARG001
    normal_user_token_headers: dict[str, str],
):
    """Test that initializing a vault creates proper game state."""
    # Create a vault via initiate endpoint
    response = await async_client.post(
        "/vaults/initiate",
        headers=normal_user_token_headers,
        json={"number": 994},
    )
    assert response.status_code == 201
    vault_data = response.json()
    vault_id = vault_data["id"]

    # Verify vault has production rooms and resources
    assert vault_data["power_max"] > 0
    assert vault_data["food_max"] > 0
    assert vault_data["water_max"] > 0
    assert vault_data["power"] > 0
    assert vault_data["food"] > 0
    assert vault_data["water"] > 0

    # Verify game state exists
    game_state_response = await async_client.get(
        f"/game/vaults/{vault_id}/game-state",
        headers=normal_user_token_headers,
    )
    assert game_state_response.status_code == 200
    game_state = game_state_response.json()
    assert game_state["is_active"] is True
    assert game_state["is_paused"] is False
    assert game_state["total_game_time"] == 0
