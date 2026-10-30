"""Pet carrier endpoint tests."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.vault import vault as vault_crud
from app.services.rewards import pet_carrier

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_open_pet_carrier_returns_the_rolled_pet(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault,
) -> None:
    """The endpoint consumes the carrier and returns the pet with its effect."""
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 10
    async_session.add(storage)
    await async_session.flush()
    granted = await pet_carrier.grant_pet_carrier(async_session, vault.id)

    response = await async_client.post(
        f"/storage/vault/{vault.id}/pet-carrier/open",
        json={"item_id": granted["item_id"]},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reward_type"] == "pet_carrier"
    assert body["pet"]["name"]
    assert body["pet"]["effect"]["luck"] is not None


@pytest.mark.asyncio
async def test_open_pet_carrier_unknown_item_is_404(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault,
) -> None:
    """An unknown carrier id is a 404, not a 500."""
    storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 10
    async_session.add(storage)
    await async_session.flush()

    response = await async_client.post(
        f"/storage/vault/{vault.id}/pet-carrier/open",
        json={"item_id": str(uuid4())},
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
