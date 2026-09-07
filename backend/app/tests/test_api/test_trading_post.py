"""Tests for the Trading Post PoC (trading soft-deleted dwellers)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas.dweller import DwellerCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


async def _make_vault(async_session: AsyncSession, superuser) -> "Vault":
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(superuser.id)
    vault_data["bottle_caps"] = 1000
    return await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))


async def _make_dweller(async_session: AsyncSession, vault_id, level: int = 5) -> "Dweller":
    return await crud.dweller.create(
        async_session,
        DwellerCreate(
            first_name="Trade",
            last_name="Fodder",
            vault_id=vault_id,
            gender="male",
            rarity="common",
            strength=5,
            perception=3,
            endurance=3,
            charisma=3,
            intelligence=3,
            agility=3,
            luck=3,
            level=level,
        ),
    )


async def _soft_delete(async_session: AsyncSession, dweller: "Dweller") -> "Dweller":
    return await crud.dweller.soft_delete(async_session, dweller.id)


async def test_buy_with_insufficient_caps_fails(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    seller_vault = await _make_vault(async_session, superuser)
    buyer_vault = await _make_vault(async_session, superuser)
    await crud.vault.update(async_session, buyer_vault.id, {"bottle_caps": 0})
    listed = await _soft_delete(async_session, await _make_dweller(async_session, seller_vault.id))

    response = await async_client.post(
        f"/vaults/{buyer_vault.id}/trading-post/buy",
        params={"dweller_id": str(listed.id)},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
    await async_session.refresh(listed)
    assert str(listed.vault_id) == str(seller_vault.id)  # unchanged
