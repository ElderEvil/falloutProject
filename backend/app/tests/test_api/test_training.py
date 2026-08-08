"""Tests for training API endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.training import Training, TrainingStatus
from app.models.vault import Vault
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, VaultOperationException


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


# ---------------------------------------------------------------------------
# Mock-based tests for uncovered endpoint paths
# ---------------------------------------------------------------------------


def _make_mock_training(**overrides):
    """Create a mock training object with all attributes needed for serialization."""
    now = datetime.now(UTC)
    tid = overrides.pop("id", uuid4())
    attrs: dict = {
        "id": tid,
        "dweller_id": uuid4(),
        "room_id": uuid4(),
        "vault_id": uuid4(),
        "stat_being_trained": SPECIALEnum.STRENGTH,
        "current_stat_value": 5,
        "target_stat_value": 6,
        "progress": 0.5,
        "started_at": now - timedelta(hours=1),
        "estimated_completion_at": now + timedelta(hours=1),
        "completed_at": None,
        "status": TrainingStatus.ACTIVE,
        "created_at": now - timedelta(hours=1),
        "updated_at": now,
        **overrides,
    }
    mock = MagicMock(spec=Training)
    for key, value in attrs.items():
        setattr(mock, key, value)

    mock.model_dump.return_value = dict(attrs)
    mock.progress_percentage.return_value = attrs["progress"] * 100
    mock.time_remaining_seconds.return_value = 3600
    mock.is_ready_to_complete.return_value = False
    return mock


def _make_mock_dweller(vault_id=None):
    """Create a mock dweller with vault_id."""
    mock = MagicMock()
    mock.id = uuid4()
    mock.vault_id = vault_id or uuid4()
    return mock


# --- POST /training/start ---------------------------------------------------


@pytest.mark.asyncio
async def test_start_training_resource_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /training/start returns 404 when ResourceNotFoundException raised."""
    mock_dweller = _make_mock_dweller()
    training_model = MagicMock()
    training_model.__name__ = "Training"

    with (
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.crud.dweller.dweller.get",
            AsyncMock(return_value=mock_dweller),
        ),
        patch(
            "app.api.v1.endpoints.training.training_service.start_training",
            AsyncMock(side_effect=ResourceNotFoundException(training_model, "fake-id")),
        ),
    ):
        response = await async_client.post(
            "/training/start",
            params={"dweller_id": str(uuid4()), "room_id": str(uuid4())},
            headers=superuser_token_headers,
        )
    assert response.status_code == 404
    assert "unable to find" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_start_training_conflict(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /training/start returns 409 when dweller is already training."""
    mock_dweller = _make_mock_dweller()

    with (
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.crud.dweller.dweller.get",
            AsyncMock(return_value=mock_dweller),
        ),
        patch(
            "app.api.v1.endpoints.training.training_service.start_training",
            AsyncMock(side_effect=ResourceConflictException("Dweller is already training")),
        ),
    ):
        response = await async_client.post(
            "/training/start",
            params={"dweller_id": str(uuid4()), "room_id": str(uuid4())},
            headers=superuser_token_headers,
        )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_start_training_vault_operation_error(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /training/start returns 400 when VaultOperationException raised."""
    mock_dweller = _make_mock_dweller()

    with (
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.crud.dweller.dweller.get",
            AsyncMock(return_value=mock_dweller),
        ),
        patch(
            "app.api.v1.endpoints.training.training_service.start_training",
            AsyncMock(side_effect=VaultOperationException("Invalid training room")),
        ),
    ):
        response = await async_client.post(
            "/training/start",
            params={"dweller_id": str(uuid4()), "room_id": str(uuid4())},
            headers=superuser_token_headers,
        )
    assert response.status_code == 400


# --- GET /training/dweller/{dweller_id} --------------------------------------


@pytest.mark.asyncio
async def test_get_dweller_training_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /training/dweller/{id} returns active training when found."""
    mock_training = _make_mock_training()

    with (
        patch(
            "app.api.v1.endpoints.training.crud_training.training.get_active_by_dweller",
            AsyncMock(return_value=mock_training),
        ),
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
    ):
        response = await async_client.get(
            f"/training/dweller/{mock_training.dweller_id}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(mock_training.id)
    assert data["status"] == TrainingStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_get_dweller_training_none(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /training/dweller/{id} returns None when no active training."""
    with patch(
        "app.api.v1.endpoints.training.crud_training.training.get_active_by_dweller",
        AsyncMock(return_value=None),
    ):
        response = await async_client.get(
            f"/training/dweller/{uuid4()}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    assert response.json() is None


# --- GET /training/vault/{vault_id} -----------------------------------------


@pytest.mark.asyncio
async def test_list_vault_training_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /training/vault/{id} returns list of active trainings."""
    vault_id = uuid4()
    t1 = _make_mock_training(vault_id=vault_id)
    t2 = _make_mock_training(vault_id=vault_id)

    with (
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.training.crud_training.training.get_active_by_vault",
            AsyncMock(return_value=[t1, t2]),
        ),
    ):
        response = await async_client.get(
            f"/training/vault/{vault_id}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


# --- GET /training/{training_id} --------------------------------------------


@pytest.mark.asyncio
async def test_get_training_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /training/{id} returns training with progress details."""
    mock_training = _make_mock_training(progress=0.75)

    with (
        patch(
            "app.api.v1.endpoints.training.crud_training.training.get",
            AsyncMock(return_value=mock_training),
        ),
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.training.training_service.update_training_progress",
            AsyncMock(return_value=mock_training),
        ),
    ):
        response = await async_client.get(
            f"/training/{mock_training.id}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(mock_training.id)
    assert "progress_percentage" in data
    assert "time_remaining_seconds" in data
    assert "is_ready_to_complete" in data


@pytest.mark.asyncio
async def test_get_training_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /training/{id} returns 404 when training not found."""
    with patch(
        "app.api.v1.endpoints.training.crud_training.training.get",
        AsyncMock(return_value=None),
    ):
        response = await async_client.get(
            f"/training/{uuid4()}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 404
    assert "training session not found" in response.json()["detail"].lower()


# --- POST /training/{training_id}/complete ----------------------------------


@pytest.mark.asyncio
async def test_complete_training_service_error(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /training/{id}/complete returns 400 when VaultOperationException raised."""
    mock_training = _make_mock_training()

    with (
        patch(
            "app.api.v1.endpoints.training.crud_training.training.get",
            AsyncMock(return_value=mock_training),
        ),
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.training.training_service.complete_training",
            AsyncMock(side_effect=VaultOperationException("Training not ready to complete")),
        ),
    ):
        response = await async_client.post(
            f"/training/{mock_training.id}/complete",
            headers=superuser_token_headers,
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_complete_training_not_found_from_service(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /training/{id}/complete returns 404 from service ResourceNotFoundException."""
    mock_training = _make_mock_training()
    training_model = MagicMock()
    training_model.__name__ = "Training"

    with (
        patch(
            "app.api.v1.endpoints.training.crud_training.training.get",
            AsyncMock(return_value=mock_training),
        ),
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.training.training_service.complete_training",
            AsyncMock(side_effect=ResourceNotFoundException(training_model, "fake-id")),
        ),
    ):
        response = await async_client.post(
            f"/training/{mock_training.id}/complete",
            headers=superuser_token_headers,
        )
    assert response.status_code == 404


# --- POST /training/{training_id}/cancel ------------------------------------


@pytest.mark.asyncio
async def test_cancel_training_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /training/{id}/cancel returns cancelled training."""
    mock_training = _make_mock_training(status=TrainingStatus.CANCELLED)
    cancelled_training = _make_mock_training(status=TrainingStatus.CANCELLED)

    with (
        patch(
            "app.api.v1.endpoints.training.crud_training.training.get",
            AsyncMock(return_value=mock_training),
        ),
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.training.training_service.cancel_training",
            AsyncMock(return_value=cancelled_training),
        ),
    ):
        response = await async_client.post(
            f"/training/{mock_training.id}/cancel",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == TrainingStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_cancel_training_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /training/{id}/cancel returns 404 when training not found."""
    with patch(
        "app.api.v1.endpoints.training.crud_training.training.get",
        AsyncMock(return_value=None),
    ):
        response = await async_client.post(
            f"/training/{uuid4()}/cancel",
            headers=superuser_token_headers,
        )
    assert response.status_code == 404
    assert "training session not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancel_training_not_found_from_service(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /training/{id}/cancel returns 404 from service ResourceNotFoundException."""
    mock_training = _make_mock_training()
    training_model = MagicMock()
    training_model.__name__ = "Training"

    with (
        patch(
            "app.api.v1.endpoints.training.crud_training.training.get",
            AsyncMock(return_value=mock_training),
        ),
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.training.training_service.cancel_training",
            AsyncMock(side_effect=ResourceNotFoundException(training_model, "fake-id")),
        ),
    ):
        response = await async_client.post(
            f"/training/{mock_training.id}/cancel",
            headers=superuser_token_headers,
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_training_vault_operation_error(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /training/{id}/cancel returns 400 when VaultOperationException raised."""
    mock_training = _make_mock_training()

    with (
        patch(
            "app.api.v1.endpoints.training.crud_training.training.get",
            AsyncMock(return_value=mock_training),
        ),
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.training.training_service.cancel_training",
            AsyncMock(side_effect=VaultOperationException("Training not active")),
        ),
    ):
        response = await async_client.post(
            f"/training/{mock_training.id}/cancel",
            headers=superuser_token_headers,
        )
    assert response.status_code == 400


# --- GET /training/room/{room_id} -------------------------------------------


@pytest.mark.asyncio
async def test_list_room_training_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /training/room/{id} returns list of active trainings in the room."""
    room_id = uuid4()
    t1 = _make_mock_training(room_id=room_id)
    t2 = _make_mock_training(room_id=room_id)

    with (
        patch(
            "app.api.v1.endpoints.training.crud_training.training.get_active_by_room",
            AsyncMock(return_value=[t1, t2]),
        ),
        patch(
            "app.api.v1.endpoints.training.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
    ):
        response = await async_client.get(
            f"/training/room/{room_id}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_room_training_empty(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /training/room/{id} returns empty list when no trainings in room."""
    with patch(
        "app.api.v1.endpoints.training.crud_training.training.get_active_by_room",
        AsyncMock(return_value=[]),
    ):
        response = await async_client.get(
            f"/training/room/{uuid4()}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    assert response.json() == []
