import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.crud.vault import vault as vault_crud
from app.schemas.outfit import OutfitCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.items import create_fake_outfit
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_read_outfit_list(async_client: AsyncClient, async_session: AsyncSession, outfit_data: dict):
    outfit_2_data = create_fake_outfit()
    outfit_1 = OutfitCreate(**outfit_data)
    outfit_2 = OutfitCreate(**outfit_2_data)
    await crud.outfit.create(async_session, outfit_1)
    await crud.outfit.create(async_session, outfit_2)
    response = await async_client.get("/outfits/")
    all_outfits = response.json()
    assert response.status_code == 200
    assert len(all_outfits) == 2
    response_outfit_1, response_outfit_2 = all_outfits
    if response_outfit_1["name"] == outfit_2.name:
        response_outfit_1, response_outfit_2 = response_outfit_2, response_outfit_1
    assert response_outfit_1["name"] == outfit_1.name
    assert response_outfit_1["rarity"] == outfit_1.rarity
    assert response_outfit_1["value"] == outfit_1.value
    assert response_outfit_1["outfit_type"] == outfit_1.outfit_type
    assert response_outfit_1["gender"] == outfit_1.gender

    assert response_outfit_2["name"] == outfit_2.name
    assert response_outfit_2["rarity"] == outfit_2.rarity
    assert response_outfit_2["value"] == outfit_2.value
    assert response_outfit_2["outfit_type"] == outfit_2.outfit_type
    assert response_outfit_2["gender"] == outfit_2.gender


@pytest.mark.asyncio
async def test_update_outfit(async_client: AsyncClient, outfit_data: dict):
    response = await async_client.post("/outfits/", json=outfit_data)
    outfit_response = response.json()
    outfit_id = outfit_response["id"]
    outfit_new_data = create_fake_outfit()
    update_response = await async_client.put(f"/outfits/{outfit_id}", json=outfit_new_data)
    updated_outfit = update_response.json()
    assert update_response.status_code == 200
    assert updated_outfit["id"] == outfit_id
    assert updated_outfit["name"] == outfit_new_data["name"]
    assert updated_outfit["rarity"] == outfit_new_data["rarity"]
    assert updated_outfit["value"] == outfit_new_data["value"]
    assert updated_outfit["outfit_type"] == outfit_new_data["outfit_type"]
    assert updated_outfit["gender"] == outfit_new_data["gender"]


@pytest.mark.asyncio
async def test_delete_outfit(async_client: AsyncClient, outfit_data: dict):
    create_response = await async_client.post("/outfits/", json=outfit_data)
    created_outfit = create_response.json()
    delete_response = await async_client.delete(f"/outfits/{created_outfit['id']}")
    assert delete_response.status_code == 204
    read_response = await async_client.get(f"/outfits/{created_outfit['id']}")
    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_scrap_outfit_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    # Setup vault/storage and outfit
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    outfit_in = OutfitCreate(**create_fake_outfit(), storage_id=str(storage.id))
    outfit = await crud.outfit.create(async_session, outfit_in)

    response = await async_client.post(f"/outfits/{outfit.id}/scrap/", headers=superuser_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert "junk" in data
    assert isinstance(data["junk"], list)
    # Outfit should be deleted as part of scrap
    read_response = await async_client.get(f"/outfits/{outfit.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404


@pytest.mark.asyncio
async def test_sell_outfit_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault_in = VaultCreateWithUserID(**vault_data)
    vault = await crud.vault.create(async_session, vault_in)
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    outfit_in = OutfitCreate(**create_fake_outfit(), storage_id=str(storage.id))
    outfit = await crud.outfit.create(async_session, outfit_in)
    vault_before = await crud.vault.get(async_session, id=vault.id)
    pre_caps = vault_before.bottle_caps
    response = await async_client.post(f"/outfits/{outfit.id}/sell/", headers=superuser_token_headers)
    assert response.status_code == 200
    read_response = await async_client.get(f"/outfits/{outfit.id}", headers=superuser_token_headers)
    assert read_response.status_code == 404
    vault_after = await crud.vault.get(async_session, id=vault.id)
    assert vault_after.bottle_caps == pre_caps + (outfit.value or 0)
