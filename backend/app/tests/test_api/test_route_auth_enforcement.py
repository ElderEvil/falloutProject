"""Behavioural checks that the routers hardened in the 2026-09-01 audit reject callers:
401 anonymous, 403 for a foreign vault."""

from uuid import UUID

import pytest

pytestmark = pytest.mark.asyncio

AUTHENTICATED_BUT_FOREIGN = (401, 403)

# Fixed ids: parametrize must produce identical ids in every xdist worker.
ITEM = UUID("11111111-1111-4111-8111-111111111111")
VAULT = UUID("22222222-2222-4222-8222-222222222222")
DWELLER = UUID("33333333-3333-4333-8333-333333333333")

PREVIOUSLY_OPEN_ROUTES = [
    ("GET", f"/weapons/?vault_id={VAULT}"),
    ("GET", f"/weapons/{ITEM}"),
    ("POST", "/weapons/"),
    ("PUT", f"/weapons/{ITEM}"),
    ("DELETE", f"/weapons/{ITEM}"),
    ("POST", f"/weapons/{DWELLER}/equip/{ITEM}"),
    ("POST", f"/weapons/{ITEM}/unequip/"),
    ("POST", f"/weapons/{ITEM}/scrap/"),
    ("POST", f"/weapons/{ITEM}/sell/"),
    ("GET", f"/junk/?vault_id={VAULT}"),
    ("GET", f"/junk/{ITEM}"),
    ("POST", "/junk/"),
    ("PUT", f"/junk/{ITEM}"),
    ("DELETE", f"/junk/{ITEM}"),
    ("POST", f"/junk/{ITEM}/sell/"),
    ("GET", f"/outfits/?vault_id={VAULT}"),
    ("GET", f"/outfits/{ITEM}"),
    ("POST", "/outfits/"),
    ("PUT", f"/outfits/{ITEM}"),
    ("DELETE", f"/outfits/{ITEM}"),
    ("POST", f"/outfits/{DWELLER}/equip/{ITEM}"),
    ("POST", f"/outfits/{ITEM}/unequip/"),
    ("POST", f"/outfits/{ITEM}/scrap/"),
    ("POST", f"/outfits/{ITEM}/sell/"),
    ("POST", f"/objectives/{VAULT}/"),
    ("GET", f"/objectives/{VAULT}/"),
    ("POST", f"/objectives/{VAULT}/{ITEM}/progress"),
    ("POST", f"/objectives/{VAULT}/assign-random"),
    ("PUT", f"/quests/{VAULT}/{ITEM}"),
]


@pytest.mark.parametrize(("method", "url"), PREVIOUSLY_OPEN_ROUTES)
async def test_previously_open_routes_reject_anonymous_callers(async_client, method: str, url: str) -> None:
    response = await async_client.request(method, url)
    assert response.status_code in AUTHENTICATED_BUT_FOREIGN, (
        f"{method} {url} answered {response.status_code} without credentials"
    )


async def test_item_routes_reject_a_foreign_vault(async_client, normal_user_token_headers, vault) -> None:
    foreign_vault_id = vault.id
    for url in (
        f"/weapons/?vault_id={foreign_vault_id}",
        f"/outfits/?vault_id={foreign_vault_id}",
        f"/junk/?vault_id={foreign_vault_id}",
        f"/objectives/{foreign_vault_id}/",
    ):
        response = await async_client.get(url, headers=normal_user_token_headers)
        assert response.status_code == 403, f"{url} answered {response.status_code} for a foreign vault"


async def test_catalog_writes_require_superuser(async_client, normal_user_token_headers) -> None:
    response = await async_client.delete(f"/weapons/{ITEM}", headers=normal_user_token_headers)
    # Insufficient privileges is an authorization failure, not a bad request.
    assert response.status_code == 403, "non-superuser catalog write was not rejected"
