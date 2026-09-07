"""Tests for storage API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.crud.vault import vault as vault_crud
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.weapon import Weapon
from app.schemas.common import JunkTypeEnum, RarityEnum
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.items import create_fake_junk, create_fake_outfit, create_fake_weapon
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


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
async def test_get_storage_items_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Test GET /storage/vault/{vault_id}/items returns all item types."""
    # Create vault for superuser
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)

    # Create storage for the vault
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)

    # Create items for storage
    for _ in range(2):
        w = Weapon(**create_fake_weapon(), storage_id=storage.id)
        async_session.add(w)
    o = Outfit(**create_fake_outfit(), storage_id=storage.id)
    async_session.add(o)
    j = Junk(**create_fake_junk(), storage_id=storage.id)
    async_session.add(j)
    await async_session.flush()

    # Get items
    response = await async_client.get(
        f"/storage/vault/{vault.id}/items",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, dict)
    assert "weapons" in data
    assert isinstance(data["weapons"], list)
    assert "outfits" in data
    assert isinstance(data["outfits"], list)
    assert "junk" in data
    assert isinstance(data["junk"], list)
    assert len(data["weapons"]) == 2
    assert len(data["outfits"]) == 1
    assert len(data["junk"]) == 1

    # Basic field checks on returned items
    for item in data["weapons"]:
        assert "id" in item
        assert "name" in item
    for item in data["outfits"]:
        assert "id" in item
        assert "name" in item
    for item in data["junk"]:
        assert "id" in item
        assert "name" in item
