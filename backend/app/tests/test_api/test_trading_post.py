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


def _price(level: int) -> int:
    return 50 + level * 10  # common base + level bonus


async def test_market_lists_other_vaults_deleted_dwellers(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    seller_vault = await _make_vault(async_session, superuser)
    buyer_vault = await _make_vault(async_session, superuser)
    listed = await _soft_delete(async_session, await _make_dweller(async_session, seller_vault.id, level=7))
    await _make_dweller(async_session, seller_vault.id)  # alive, must not appear

    response = await async_client.get(f"/vaults/{buyer_vault.id}/trading-post/market", headers=superuser_token_headers)

    assert response.status_code == 200
    body = response.json()
    offer_ids = [offer["dweller"]["id"] for offer in body["market_offers"]]
    assert str(listed.id) in offer_ids
    assert body["market_offers"][0]["price"] == _price(7)
    assert body["market_offers"][0]["places_visited"] >= 0
    assert body["bottle_caps"] == 1000


async def test_market_offer_highlights_reflect_dweller_data(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    """has_bio/has_image/places_visited must reflect the dweller's actual data."""
    seller_vault = await _make_vault(async_session, superuser)
    buyer_vault = await _make_vault(async_session, superuser)
    dweller = await _make_dweller(async_session, seller_vault.id, level=2)
    dweller.bio = "Wasteland legend."
    dweller.thumbnail_url = "/static/portraits/test.webp"
    async_session.add(dweller)
    await async_session.commit()

    from app.models.wasteland_location import (
        DwellerLocation,
        DwellerLocationRelationEnum,
        LocationTypeEnum,
        WastelandLocation,
    )

    loc = WastelandLocation(
        name="Super Duper Mart",
        normalized_name="super duper mart",
        type=LocationTypeEnum.VISITED,
        coord_x=10.0,
        coord_y=20.0,
        vault_id=seller_vault.id,
    )
    async_session.add(loc)
    await async_session.commit()
    await async_session.refresh(loc)
    async_session.add(
        DwellerLocation(dweller_id=dweller.id, location_id=loc.id, relation=DwellerLocationRelationEnum.VISITED)
    )
    await async_session.commit()

    await _soft_delete(async_session, dweller)

    response = await async_client.get(f"/vaults/{buyer_vault.id}/trading-post/market", headers=superuser_token_headers)

    assert response.status_code == 200
    offer = next(o for o in response.json()["market_offers"] if o["dweller"]["id"] == str(dweller.id))
    assert offer["has_bio"] is True
    assert offer["dweller"]["thumbnail_url"] == "/static/portraits/test.webp"
    assert offer["places_visited"] == 1


async def test_market_shows_own_soft_deleted_as_listings(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    vault = await _make_vault(async_session, superuser)
    listed = await _soft_delete(async_session, await _make_dweller(async_session, vault.id))

    response = await async_client.get(f"/vaults/{vault.id}/trading-post/market", headers=superuser_token_headers)

    assert response.status_code == 200
    assert [offer["dweller"]["id"] for offer in response.json()["my_listings"]] == [str(listed.id)]


async def test_sell_soft_deleted_dweller_deposits_caps(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    vault = await _make_vault(async_session, superuser)
    dweller = await _soft_delete(async_session, await _make_dweller(async_session, vault.id, level=10))

    response = await async_client.post(
        f"/vaults/{vault.id}/trading-post/sell",
        params={"dweller_id": str(dweller.id)},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["price"] == _price(10)
    assert body["bottle_caps"] == 1000 + body["price"]


async def test_sell_alive_dweller_not_found(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    vault = await _make_vault(async_session, superuser)
    dweller = await _make_dweller(async_session, vault.id)

    response = await async_client.post(
        f"/vaults/{vault.id}/trading-post/sell",
        params={"dweller_id": str(dweller.id)},
        headers=superuser_token_headers,
    )

    assert response.status_code == 404


async def test_buy_moves_dweller_and_caps_between_vaults(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    seller_vault = await _make_vault(async_session, superuser)
    buyer_vault = await _make_vault(async_session, superuser)
    listed = await _soft_delete(async_session, await _make_dweller(async_session, seller_vault.id, level=4))

    response = await async_client.post(
        f"/vaults/{buyer_vault.id}/trading-post/buy",
        params={"dweller_id": str(listed.id)},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["bottle_caps"] == 1000 - _price(4)

    await async_session.refresh(listed)
    assert str(listed.vault_id) == str(buyer_vault.id)
    assert not listed.is_deleted
    assert listed.level == 1  # reset_stats=True
    assert listed.room_id is None

    await async_session.refresh(seller_vault)
    assert seller_vault.bottle_caps == 1000 + _price(4)


async def test_buy_own_listing_conflicts(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    vault = await _make_vault(async_session, superuser)
    listed = await _soft_delete(async_session, await _make_dweller(async_session, vault.id))

    response = await async_client.post(
        f"/vaults/{vault.id}/trading-post/buy",
        params={"dweller_id": str(listed.id)},
        headers=superuser_token_headers,
    )

    assert response.status_code == 400


async def test_sell_same_dweller_twice_rejected(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    """A sale is single-use: the second sell must not grant caps again."""
    vault = await _make_vault(async_session, superuser)
    dweller = await _soft_delete(async_session, await _make_dweller(async_session, vault.id, level=5))

    first = await async_client.post(
        f"/vaults/{vault.id}/trading-post/sell",
        params={"dweller_id": str(dweller.id)},
        headers=superuser_token_headers,
    )
    assert first.status_code == 200

    second = await async_client.post(
        f"/vaults/{vault.id}/trading-post/sell",
        params={"dweller_id": str(dweller.id)},
        headers=superuser_token_headers,
    )

    assert second.status_code == 400
    await async_session.refresh(vault)
    assert vault.bottle_caps == 1000 + _price(5)  # only one payout


async def test_buy_traded_dweller_does_not_credit_seller_again(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    """Seller collected proceeds at sell time; a later buy must not pay twice."""
    seller_vault = await _make_vault(async_session, superuser)
    buyer_vault = await _make_vault(async_session, superuser)
    listed = await _soft_delete(async_session, await _make_dweller(async_session, seller_vault.id, level=4))

    sold = await async_client.post(
        f"/vaults/{seller_vault.id}/trading-post/sell",
        params={"dweller_id": str(listed.id)},
        headers=superuser_token_headers,
    )
    assert sold.status_code == 200
    seller_caps_after_sell = 1000 + _price(4)

    bought = await async_client.post(
        f"/vaults/{buyer_vault.id}/trading-post/buy",
        params={"dweller_id": str(listed.id)},
        headers=superuser_token_headers,
    )

    assert bought.status_code == 200
    await async_session.refresh(seller_vault)
    assert seller_vault.bottle_caps == seller_caps_after_sell  # no second payout

    await async_session.refresh(listed)
    assert str(listed.vault_id) == str(buyer_vault.id)
    assert not listed.is_traded  # recycled into the buyer un-traded


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
