from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app import crud
from app.core.enums import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum, TrainingStatus
from app.models.training import Training
from app.schemas.room import RoomCreate
from app.services.training_service import training_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, VaultOperationException

EP = "app.api.v1.endpoints.training."
START = "/training/start"


@contextmanager
def _patched(*targets: tuple[str, object]):
    with ExitStack() as stack:
        for target, value in targets:
            stack.enter_context(patch(target, value))
        yield


def _make_mock_training(**overrides):
    now = datetime.now(UTC)
    attrs: dict = {
        "id": overrides.pop("id", uuid4()),
        "dweller_id": uuid4(),
        "room_id": uuid4(),
        "vault_id": uuid4(),
        "stat_being_trained": SPECIALEnum.STRENGTH,
        "current_stat_value": 5,
        "target_stat_value": 6,
        "goal_stat_value": 10,
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
    mock = MagicMock()
    mock.id = uuid4()
    mock.vault_id = vault_id or uuid4()
    return mock


def _not_found() -> ResourceNotFoundException:
    model = MagicMock()
    model.__name__ = "Training"
    return ResourceNotFoundException(model, "fake-id")


async def _training_room(async_session, vault, **overrides):
    data = {
        "name": "Weight Room",
        "vault_id": vault.id,
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
    } | overrides
    return await crud.room.create(async_session, RoomCreate(**data))


async def _start_training(async_client, headers, dweller, room):
    return await async_client.post(
        START, params={"dweller_id": str(dweller.id), "room_id": str(room.id)}, headers=headers
    )


async def test_continuous_training_setting_round_trips(async_client, superuser_token_headers, async_session, vault):
    assert vault.continuous_training is False
    for enabled in (True, False):
        response = await async_client.put(
            f"/vaults/{vault.id}", headers=superuser_token_headers, json={"continuous_training": enabled}
        )
        assert response.status_code == 200
        assert response.json()["continuous_training"] is enabled
        await async_session.refresh(vault)
        assert vault.continuous_training is enabled


async def test_continuous_training_setting_rejects_foreign_vault(
    async_client, normal_user_token_headers, async_session, vault
):
    response = await async_client.put(
        f"/vaults/{vault.id}", headers=normal_user_token_headers, json={"continuous_training": True}
    )
    assert response.status_code == 403
    await async_session.refresh(vault)
    assert vault.continuous_training is False


async def test_unassigning_a_training_dweller_cancels_active_session(
    async_client, superuser_token_headers, async_session, vault, dweller
):
    room = await _training_room(async_session, vault)
    dweller.status = DwellerStatusEnum.IDLE
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()

    start_response = await _start_training(async_client, superuser_token_headers, dweller, room)
    assert start_response.status_code == 201
    training_id = start_response.json()["id"]

    response = await async_client.put(
        f"/dwellers/{dweller.id}", json={"room_id": None}, headers=superuser_token_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == DwellerStatusEnum.IDLE.value
    training = await crud.training.training.get(async_session, UUID(training_id))
    assert training.status == TrainingStatus.CANCELLED


async def test_complete_training_already_completed(
    async_client, superuser_token_headers, async_session, vault, dweller
):
    room = await _training_room(async_session, vault)
    dweller.status = DwellerStatusEnum.IDLE
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)

    start_response = await _start_training(async_client, superuser_token_headers, dweller, room)
    assert start_response.status_code == 201
    training_id = start_response.json()["id"]

    response = await async_client.post(f"/training/{training_id}/complete", headers=superuser_token_headers)
    assert response.status_code == 200

    response = await async_client.post(f"/training/{training_id}/complete", headers=superuser_token_headers)
    assert response.status_code == 400
    assert "cannot complete" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (_not_found(), 404, "unable to find"),
        (ResourceConflictException("Dweller is already training"), 409, None),
        (VaultOperationException("Invalid training room"), 400, None),
    ],
)
async def test_start_training_errors(async_client, superuser_token_headers, error, status, detail):
    with _patched(
        (f"{EP}get_user_vault_or_403", AsyncMock(return_value=None)),
        ("app.crud.dweller.dweller.get", AsyncMock(return_value=_make_mock_dweller())),
        (f"{EP}training_service.start_training", AsyncMock(side_effect=error)),
    ):
        response = await async_client.post(
            START,
            params={"dweller_id": str(uuid4()), "room_id": str(uuid4())},
            headers=superuser_token_headers,
        )
    assert response.status_code == status
    if detail is not None:
        assert detail in response.json()["detail"].lower()


async def test_get_dweller_training_success(async_client, superuser_token_headers):
    mock_training = _make_mock_training()
    with _patched(
        (f"{EP}crud_training.training.get_active_by_dweller", AsyncMock(return_value=mock_training)),
        (f"{EP}get_user_vault_or_403", AsyncMock(return_value=None)),
    ):
        response = await async_client.get(
            f"/training/dweller/{mock_training.dweller_id}", headers=superuser_token_headers
        )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(mock_training.id)
    assert data["status"] == TrainingStatus.ACTIVE.value


@pytest.mark.parametrize(
    ("segment", "crud_method", "kwarg"),
    [("vault", "get_active_by_vault", "vault_id"), ("room", "get_active_by_room", "room_id")],
)
async def test_list_training_success(async_client, superuser_token_headers, segment, crud_method, kwarg):
    ident = uuid4()
    items = [_make_mock_training(**{kwarg: ident}) for _ in range(2)]
    with _patched(
        (f"{EP}crud_training.training.{crud_method}", AsyncMock(return_value=items)),
        (f"{EP}get_user_vault_or_403", AsyncMock(return_value=None)),
    ):
        response = await async_client.get(f"/training/{segment}/{ident}", headers=superuser_token_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


async def test_get_training_success(async_client, superuser_token_headers):
    mock_training = _make_mock_training(progress=0.75)
    with _patched(
        (f"{EP}crud_training.training.get", AsyncMock(return_value=mock_training)),
        (f"{EP}get_user_vault_or_403", AsyncMock(return_value=None)),
        (f"{EP}training_service.update_training_progress", AsyncMock(return_value=mock_training)),
    ):
        response = await async_client.get(f"/training/{mock_training.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(mock_training.id)
    assert "progress_percentage" in data
    assert "time_remaining_seconds" in data
    assert "is_ready_to_complete" in data


@pytest.mark.parametrize("action", ["view", "cancel"])
async def test_training_session_not_found(async_client, superuser_token_headers, action):
    training_id = uuid4()
    with _patched((f"{EP}crud_training.training.get", AsyncMock(return_value=None))):
        if action == "view":
            response = await async_client.get(f"/training/{training_id}", headers=superuser_token_headers)
        else:
            response = await async_client.post(f"/training/{training_id}/cancel", headers=superuser_token_headers)
    assert response.status_code == 404
    assert "training session not found" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    ("action", "error", "status"),
    [
        ("complete", VaultOperationException("Training not ready to complete"), 400),
        ("complete", _not_found(), 404),
        ("cancel", _not_found(), 404),
        ("cancel", VaultOperationException("Training not active"), 400),
    ],
)
async def test_training_action_service_errors(async_client, superuser_token_headers, action, error, status):
    mock_training = _make_mock_training()
    with _patched(
        (f"{EP}crud_training.training.get", AsyncMock(return_value=mock_training)),
        (f"{EP}get_user_vault_or_403", AsyncMock(return_value=None)),
        (f"{EP}training_service.{action}_training", AsyncMock(side_effect=error)),
    ):
        response = await async_client.post(f"/training/{mock_training.id}/{action}", headers=superuser_token_headers)
    assert response.status_code == status


async def test_training_goal_is_saved_and_owner_only(
    async_client, superuser_token_headers, normal_user_token_headers, async_session, vault, dweller
):
    room = await _training_room(async_session, vault, size=3, size_min=3, size_max=9, capacity=2, base_cost=100)
    dweller.strength = 5
    dweller.status = DwellerStatusEnum.IDLE
    async_session.add(dweller)
    await async_session.commit()
    training = await training_service.start_training(async_session, dweller.id, room.id)
    url = f"/training/{training.id}/goal"
    forbidden = await async_client.patch(url, headers=normal_user_token_headers, json={"goal_stat_value": 7})
    assert forbidden.status_code == 403
    await async_session.refresh(training)
    assert training.goal_stat_value == 10
    for goal, status in [(11, 422), (5, 400), (7, 200)]:
        response = await async_client.patch(url, headers=superuser_token_headers, json={"goal_stat_value": goal})
        assert response.status_code == status
    response = await async_client.get(f"/training/vault/{vault.id}", headers=superuser_token_headers)
    assert response.json()[0]["goal_stat_value"] == 7
    missing = await async_client.patch(
        f"/training/{uuid4()}/goal", headers=superuser_token_headers, json={"goal_stat_value": 7}
    )
    assert missing.status_code == 404
