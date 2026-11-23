import pytest

from app import crud
from app.schemas.dweller import DwellerCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


async def _make_vault(async_session, superuser):
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(superuser.id)
    vault_data["bottle_caps"] = 1000
    return await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))


async def _listed_dweller(async_session, vault_id, level: int = 5):
    dweller = await crud.dweller.create(
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
    return await crud.dweller.soft_delete(async_session, dweller.id)


async def test_buy_with_insufficient_caps_fails(async_client, async_session, superuser_token_headers, superuser):
    seller_vault = await _make_vault(async_session, superuser)
    buyer_vault = await _make_vault(async_session, superuser)
    await crud.vault.update(async_session, buyer_vault.id, {"bottle_caps": 0})
    listed = await _listed_dweller(async_session, seller_vault.id)
    response = await async_client.post(
        f"/vaults/{buyer_vault.id}/trading-post/buy",
        params={"dweller_id": str(listed.id)},
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    await async_session.refresh(listed)
    assert str(listed.vault_id) == str(seller_vault.id)  # unchanged
