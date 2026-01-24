"""Tests for storage API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.crud.vault import vault as vault_crud
from app.models.junk import Junk
from app.schemas.common import JunkTypeEnum, RarityEnum
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_get_storage_space_info(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test GET /storage/vault/{vault_id}/space returns correct storage info."""
    # Create vault
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)

    # Create storage for the vault
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)

    # Get storage info
    response = await async_client.get(
        f"/storage/vault/{vault.id}/space",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "used_space" in data
    assert "max_space" in data
    assert "available_space" in data
    assert "utilization_pct" in data

    # Verify empty vault storage values
    assert data["used_space"] == 0
    assert data["max_space"] == storage.max_space
    assert data["available_space"] == storage.max_space
    assert data["utilization_pct"] == 0.0


@pytest.mark.asyncio
async def test_get_storage_space_with_items(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test storage space info correctly reflects items in storage."""
    # Create vault
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)

    # Create storage for the vault with a reasonable max_space
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 100  # Set reasonable max space for testing
    async_session.add(storage)
    await async_session.flush()

    # Add items to storage
    for i in range(3):
        junk = Junk(
            name=f"Test Junk {i}",
            junk_type=JunkTypeEnum.VALUABLES,
            rarity=RarityEnum.COMMON,
            description="Test item",
            storage_id=storage.id,
        )
        async_session.add(junk)
    await async_session.flush()

    # Get storage info
    response = await async_client.get(
        f"/storage/vault/{vault.id}/space",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()

    # Verify items are counted
    assert data["used_space"] == 3
    assert data["available_space"] == 100 - 3  # max_space - items
    assert data["utilization_pct"] == 3.0  # 3/100 * 100 = 3%


@pytest.mark.asyncio
async def test_get_storage_space_unauthorized(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],  # noqa: ARG001
):
    """Test storage endpoint requires authentication."""
    # Create vault
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)

    # Create storage for the vault
    await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)

    # Request without auth headers
    response = await async_client.get(f"/storage/vault/{vault.id}/space")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_storage_space_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    """Test storage endpoint returns 403/404 for non-existent vault."""
    import uuid

    fake_vault_id = str(uuid.uuid4())

    response = await async_client.get(
        f"/storage/vault/{fake_vault_id}/space",
        headers=superuser_token_headers,
    )

    # Should return 403 (vault not owned by user) or 404
    assert response.status_code in [403, 404]


@pytest.mark.asyncio
async def test_get_storage_space_different_user(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],  # noqa: ARG001
    normal_user_token_headers: dict[str, str],
):
    """Test user cannot access another user's vault storage."""
    # Create vault for superuser
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)

    # Create storage for the vault
    await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)

    # Normal user tries to access superuser's vault storage
    response = await async_client.get(
        f"/storage/vault/{vault.id}/space",
        headers=normal_user_token_headers,
    )

    # Should be forbidden
    assert response.status_code == 403
