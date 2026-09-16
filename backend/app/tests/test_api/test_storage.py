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


@pytest.mark.smoke
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


@pytest.mark.smoke
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


@pytest.mark.asyncio
async def test_open_lunchbox_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Test POST /storage/vault/{vault_id}/lunchbox/open consumes the box and reveals contents."""
    from uuid import UUID

    from app.services.reward_service import reward_service

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 100
    async_session.add(storage)
    await async_session.flush()

    minted = await reward_service.grant_lunchbox(async_session, vault.id)

    response = await async_client.post(
        f"/storage/vault/{vault.id}/lunchbox/open",
        json={"item_id": minted["item_id"]},
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["reward_type"] == "lunchbox"
    assert len(data["items"]) == 3
    assert data["dweller"]["dweller_id"]
    assert data["dweller"]["name"]

    remaining = await crud.storage.get_unopened_lunchbox(async_session, UUID(minted["item_id"]), vault.id)
    assert remaining is None


@pytest.mark.asyncio
async def test_open_lunchbox_unknown_item_404(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Test opening an unknown lunchbox returns 404 without distinguishing the cause."""
    from uuid import uuid4

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))
    await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)

    response = await async_client.post(
        f"/storage/vault/{vault.id}/lunchbox/open",
        json={"item_id": str(uuid4())},
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_storage_space_reports_over_capacity_instead_of_500(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """Scrapping can leave more items than slots; the endpoint must still answer."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 2
    async_session.add(storage)
    await async_session.flush()

    for index in range(5):
        async_session.add(
            Junk(
                name=f"Overflow {index}",
                junk_type=JunkTypeEnum.VALUABLES,
                rarity=RarityEnum.COMMON,
                description="Over-capacity fixture",
                storage_id=storage.id,
            )
        )
    await async_session.flush()

    response = await async_client.get(
        f"/storage/vault/{vault.id}/space",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["used_space"] == 5
    assert data["max_space"] == 2
    assert data["available_space"] == 0
    assert data["utilization_pct"] > 100


@pytest.mark.asyncio
async def test_distribute_recovery_supplies_endpoint(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    """The one-shot action treats irradiated dwellers and reports the supplies used."""
    from app.schemas.dweller import DwellerCreate
    from app.tests.factory.dwellers import create_fake_dweller

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))

    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.radaway = 10
    storage.stimpack = 10
    async_session.add(storage)

    dweller_data = create_fake_dweller()
    dweller_data["vault_id"] = vault.id
    dweller_data["radiation"] = 40
    dweller_data["max_health"] = 100
    dweller_data["health"] = 1
    dweller = await crud.dweller.create(async_session, DwellerCreate(**dweller_data))
    await async_session.flush()

    response = await async_client.post(
        f"/storage/vault/{vault.id}/medical/distribute-recovery-supplies",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["dwellers_treated"] == 1
    assert data["radaways_used"] == 1
    assert data["stimpaks_used"] == 1
    assert data["vault_radaways"] == 9
    assert data["vault_stimpacks"] == 9
    await async_session.refresh(dweller)
    assert dweller.radiation == 0
    assert dweller.health >= 40
