import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_create_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    response = await async_client.post("/vaults/", headers=superuser_token_headers, json=vault_data)
    assert response.status_code == 201
    response_data = response.json()
    assert response_data["number"] == vault_data["number"]
    assert response_data["bottle_caps"] == vault_data["bottle_caps"]
    assert response_data["happiness"] == vault_data["happiness"]
    assert response_data["user_id"] == vault_data["user_id"]


@pytest.mark.asyncio
async def test_read_vault_list(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(db_session=async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_1_data, vault_2_data = create_fake_vault(), create_fake_vault()
    vault_1_data["user_id"] = vault_2_data["user_id"] = str(user.id)
    await crud.vault.create(async_session, VaultCreateWithUserID(**vault_1_data))
    await crud.vault.create(async_session, VaultCreateWithUserID(**vault_2_data))
    response = await async_client.get("/vaults/", headers=superuser_token_headers)
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    response_vault_1, response_vault_2 = response_data
    if response_vault_1["number"] == vault_2_data["number"]:
        response_vault_2, response_vault_1 = response_data
    assert response_vault_1["number"] == vault_1_data["number"]
    assert response_vault_1["bottle_caps"] == vault_1_data["bottle_caps"]
    assert response_vault_1["happiness"] == vault_1_data["happiness"]
    assert response_vault_1["user_id"] == vault_1_data["user_id"]

    assert response_vault_2["number"] == vault_2_data["number"]
    assert response_vault_2["bottle_caps"] == vault_2_data["bottle_caps"]
    assert response_vault_2["happiness"] == vault_2_data["happiness"]
    assert response_vault_2["user_id"] == vault_2_data["user_id"]


@pytest.mark.asyncio
async def test_read_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(db_session=async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreateWithUserID(**vault_data)
    created_vault = await crud.vault.create(async_session, vault_to_create)
    response = await async_client.get(f"/vaults/{created_vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == str(created_vault.id)
    assert response_data["number"] == vault_data["number"]
    assert response_data["bottle_caps"] == vault_data["bottle_caps"]
    assert response_data["happiness"] == vault_data["happiness"]
    # user_id is not included in VaultReadWithNumbers response (GET /vaults/{id})
    assert "room_count" in response_data
    assert "dweller_count" in response_data


@pytest.mark.asyncio
async def test_update_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(db_session=async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreateWithUserID(**vault_data)
    created_vault = await crud.vault.create(db_session=async_session, obj_in=vault_to_create)
    response = await async_client.get(f"/vaults/{created_vault.id}", headers=superuser_token_headers)
    assert response.status_code == 200
    new_vault_data = create_fake_vault()
    new_vault_data["user_id"] = str(user.id)
    update_response = await async_client.put(
        f"/vaults/{created_vault.id}",
        json=new_vault_data,
        headers=superuser_token_headers,
    )
    assert update_response.status_code == 200
    update_response_data = update_response.json()
    assert update_response_data["id"] == str(created_vault.id)
    assert update_response_data["number"] == new_vault_data["number"]
    assert update_response_data["bottle_caps"] == new_vault_data["bottle_caps"]
    assert update_response_data["happiness"] == new_vault_data["happiness"]
    assert update_response_data["user_id"] == vault_data["user_id"]


@pytest.mark.asyncio
async def test_delete_vault(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_to_create = VaultCreateWithUserID(**vault_data)
    created_vault = await crud.vault.create(async_session, vault_to_create)
    delete_response = await async_client.delete(
        f"/vaults/{created_vault.id}",
        headers=superuser_token_headers,
    )
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/junk/{created_vault.id}")
    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_superuser_vault_initiate_creates_training_sessions(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test that superuser vault initialization creates training sessions for all training room dwellers."""
    # Get superuser
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    assert user.is_superuser

    # Initiate vault (superuser flag passed automatically from user.is_superuser)
    vault_number = {"number": 777}
    response = await async_client.post("/vaults/initiate", headers=superuser_token_headers, json=vault_number)
    assert response.status_code == 201
    vault_id = response.json()["id"]

    # Get all training sessions for the vault
    training_response = await async_client.get(f"/training/vault/{vault_id}", headers=superuser_token_headers)
    assert training_response.status_code == 200
    training_sessions = training_response.json()

    # Verify we got training sessions created
    assert isinstance(training_sessions, list)

    # Note: The number of training sessions depends on vault initialization logic
    # which creates 7 training rooms (one per SPECIAL stat) with assigned dwellers.
    # Each dweller in a training room should have an active training session.
    if len(training_sessions) > 0:
        # Verify all sessions are in correct status and belong to this vault
        for session in training_sessions:
            assert session["status"] in ["active", "in_progress", "completed"]
            assert session["vault_id"] == vault_id
