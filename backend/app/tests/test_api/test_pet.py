"""Pet API endpoint tests (Phase A)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import RarityEnum
from app.crud.vault import vault as vault_crud
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


def _pet_data(**overrides) -> dict:
    return {
        "name": "Dogmeat",
        "rarity": RarityEnum.LEGENDARY,
        "value": 500,
        **overrides,
    }


@pytest.mark.asyncio
async def test_read_pet_list(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault,
) -> None:
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    await crud.pet.create(async_session, {**_pet_data(name="Pet One"), "storage_id": storage.id})
    await crud.pet.create(async_session, {**_pet_data(name="Pet Two"), "storage_id": storage.id})

    response = await async_client.get(f"/pets/?vault_id={vault.id}", headers=superuser_token_headers)

    assert response.status_code == 200
    pets = response.json()
    assert len(pets) == 2
    assert {pet["name"] for pet in pets} == {"Pet One", "Pet Two"}
    assert all(pet["rarity"] == "legendary" for pet in pets)


@pytest.mark.asyncio
async def test_read_pet(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault,
) -> None:
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    pet = await crud.pet.create(async_session, {**_pet_data(), "storage_id": storage.id})

    response = await async_client.get(f"/pets/{pet.id}", headers=superuser_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(pet.id)
    assert data["name"] == "Dogmeat"
    assert data["storage_id"] == str(storage.id)


@pytest.mark.asyncio
async def test_read_pet_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = await async_client.get(f"/pets/{uuid.uuid4()}", headers=superuser_token_headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_equip_pet(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault,
    dweller,
) -> None:
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    pet = await crud.pet.create(async_session, {**_pet_data(), "storage_id": storage.id})

    response = await async_client.post(
        f"/pets/{dweller.id}/equip/{pet.id}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(pet.id)
    assert data["dweller_id"] == str(dweller.id)
    assert data["storage_id"] is None


@pytest.mark.asyncio
async def test_equip_pet_not_found(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    dweller,
) -> None:
    response = await async_client.post(
        f"/pets/{dweller.id}/equip/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unequip_pet(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault,
    dweller,
) -> None:
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    pet = await crud.pet.create(async_session, {**_pet_data(), "storage_id": storage.id})
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)

    response = await async_client.post(f"/pets/{pet.id}/unequip/", headers=superuser_token_headers)

    assert response.status_code == 200
    reloaded = await crud.pet.get(async_session, pet.id)
    assert reloaded.dweller_id is None
    assert reloaded.storage_id == storage.id


@pytest.mark.asyncio
async def test_unequip_pet_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = await async_client.post(f"/pets/{uuid.uuid4()}/unequip/", headers=superuser_token_headers)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_storage_items_response_includes_pets(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
) -> None:
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(user.id)
    vault = await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    await crud.pet.create(async_session, {**_pet_data(), "storage_id": storage.id})

    response = await async_client.get(
        f"/storage/vault/{vault.id}/items",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["pets"]) == 1
    assert data["pets"][0]["name"] == "Dogmeat"
