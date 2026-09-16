"""Behavioural checks that the routers hardened in the 2026-09-01 audit reject callers.

The weapon/junk/outfit/objective routers were reachable with no authentication at
all; `test_route_auth_guard.py` proves the schema now requires auth, and these
tests prove it is enforced at runtime (401 anonymous, 403 for a foreign vault).
"""

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.vault import Vault

pytestmark = pytest.mark.asyncio

AUTHENTICATED_BUT_FOREIGN = (401, 403)

# Fixed ids: parametrize must produce identical ids in every xdist worker.
ITEM = UUID("11111111-1111-4111-8111-111111111111")
VAULT = UUID("22222222-2222-4222-8222-222222222222")
DWELLER = UUID("33333333-3333-4333-8333-333333333333")


def _previously_open_routes() -> list[tuple[str, str]]:
    return [
        ("GET", "/weapons/"),
        ("GET", f"/weapons/{ITEM}"),
        ("POST", "/weapons/"),
        ("PUT", f"/weapons/{ITEM}"),
        ("DELETE", f"/weapons/{ITEM}"),
        ("POST", f"/weapons/{DWELLER}/equip/{ITEM}"),
        ("POST", f"/weapons/{ITEM}/unequip/"),
        ("POST", f"/weapons/{ITEM}/scrap/"),
        ("POST", f"/weapons/{ITEM}/sell/"),
        ("GET", "/junk/"),
        ("GET", f"/junk/{ITEM}"),
        ("POST", "/junk/"),
        ("PUT", f"/junk/{ITEM}"),
        ("DELETE", f"/junk/{ITEM}"),
        ("POST", f"/junk/{ITEM}/sell/"),
        ("GET", "/outfits/"),
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


@pytest.mark.parametrize(("method", "url"), _previously_open_routes())
async def test_previously_open_routes_reject_anonymous_callers(
    async_client: AsyncClient, method: str, url: str
) -> None:
    """No bearer token means no access — regardless of the route's own checks."""
    response = await async_client.request(method, url)

    assert response.status_code in AUTHENTICATED_BUT_FOREIGN, (
        f"{method} {url} answered {response.status_code} without credentials"
    )


async def test_item_routes_reject_a_foreign_vault(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
    vault: Vault,
) -> None:
    """An authenticated user cannot read another vault's item listing or objectives."""
    foreign_vault_id = vault.id

    for url in (
        f"/weapons/?vault_id={foreign_vault_id}",
        f"/outfits/?vault_id={foreign_vault_id}",
        f"/objectives/{foreign_vault_id}/",
    ):
        response = await async_client.get(url, headers=normal_user_token_headers)
        assert response.status_code == 403, f"{url} answered {response.status_code} for a foreign vault"


async def test_catalog_writes_require_superuser(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Catalog mutation is an admin action, not something any account can do."""
    response = await async_client.delete(f"/weapons/{ITEM}", headers=normal_user_token_headers)

    assert response.status_code == 400, "non-superuser catalog write was not rejected"


async def test_authenticated_reads_still_work(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
) -> None:
    """Hardening must not break the happy path the frontend uses."""
    response = await async_client.get("/weapons/", headers=superuser_token_headers)

    assert response.status_code == 200
