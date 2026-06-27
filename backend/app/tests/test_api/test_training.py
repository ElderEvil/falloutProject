"""Tests for training API endpoints."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate


@pytest.mark.asyncio
async def test_complete_training(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test completing an active training session via the API."""
    # Create a training room
    room_data = {
        "name": "Weight Room",
        "category": RoomTypeEnum.TRAINING,
        "tier": 1,
        "size": 2,
        "capacity": 6,
        "ability": SPECIALEnum.STRENGTH,
        "base_cost": 1000,
        "t2_upgrade_cost": 2500,
        "t3_upgrade_cost": 5000,
        "size_min": 1,
        "size_max": 3,
    }
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    # Set dweller to IDLE and reasonable strength
    dweller.status = DwellerStatusEnum.IDLE
    initial_strength = 5
    dweller.strength = initial_strength
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)

    # Start training via the API
    start_response = await async_client.post(
        "/training/start",
        params={"dweller_id": str(dweller.id), "room_id": str(room.id)},
        headers=superuser_token_headers,
    )
    assert start_response.status_code == 201
    training_id = start_response.json()["id"]

    # Complete training via the new endpoint
    response = await async_client.post(
        f"/training/{training_id}/complete",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "completed"
    assert data["progress"] == 1.0
    assert data["completed_at"] is not None
    assert data["id"] == training_id

    # Verify dweller's strength increased
    await async_session.refresh(dweller)
    assert dweller.strength == initial_strength + 1
    assert dweller.status == DwellerStatusEnum.IDLE


@pytest.mark.asyncio
async def test_complete_training_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Test completing a non-existent training session returns 404."""
    fake_id = str(uuid4())
    response = await async_client.post(
        f"/training/{fake_id}/complete",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert "unable to find" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_complete_training_already_completed(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Test completing an already completed training returns 400."""
    # Create a training room
    room_data = {
        "name": "Weight Room",
        "category": RoomTypeEnum.TRAINING,
        "tier": 1,
        "size": 2,
        "capacity": 6,
        "ability": SPECIALEnum.STRENGTH,
        "base_cost": 1000,
        "t2_upgrade_cost": 2500,
        "t3_upgrade_cost": 5000,
        "size_min": 1,
        "size_max": 3,
    }
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await crud.room.create(async_session, room_in)

    dweller.status = DwellerStatusEnum.IDLE
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)

    # Start training
    start_response = await async_client.post(
        "/training/start",
        params={"dweller_id": str(dweller.id), "room_id": str(room.id)},
        headers=superuser_token_headers,
    )
    assert start_response.status_code == 201
    training_id = start_response.json()["id"]

    # Complete once
    response = await async_client.post(
        f"/training/{training_id}/complete",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    # Complete again should fail
    response = await async_client.post(
        f"/training/{training_id}/complete",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "cannot complete" in response.json()["detail"].lower()
