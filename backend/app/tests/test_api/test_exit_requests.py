"""Tests for the exit-request endpoints: list, refuse, and the one-way grant."""

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.vaults import create_fake_vault

pytestmark = pytest.mark.asyncio(scope="module")


async def _make_vault(async_session: AsyncSession, superuser) -> Vault:
    vault_data = create_fake_vault()
    vault_data["user_id"] = str(superuser.id)
    return await crud.vault.create(async_session, VaultCreateWithUserID(**vault_data))


async def _make_dweller(async_session: AsyncSession, vault_id, *, happiness: int = 80, prefix: str = "Exit") -> Dweller:
    return await crud.dweller.create(
        async_session,
        DwellerCreate(
            first_name=prefix,
            last_name="Seeker",
            vault_id=vault_id,
            gender="male",
            rarity="common",
            happiness=happiness,
            strength=3,
            perception=3,
            endurance=3,
            charisma=3,
            intelligence=3,
            agility=3,
            luck=3,
        ),
    )


async def _vault_with_population(async_session: AsyncSession, superuser) -> Vault:
    """The population floor needs more than `min_population` living dwellers."""
    vault = await _make_vault(async_session, superuser)
    for index in range(game_config.exit_request.min_population + 1):
        await _make_dweller(async_session, vault.id, prefix=f"Dw{index}")
    return vault


async def _ask(async_session: AsyncSession, dweller) -> None:
    await crud.dweller.update(async_session, dweller.id, {"exit_requested_at": datetime.utcnow()})


async def test_list_exit_requests_returns_only_pending(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    vault = await _vault_with_population(async_session, superuser)
    dwelling = await _make_dweller(async_session, vault.id, prefix="Asker")
    await _ask(async_session, dwelling)

    response = await async_client.get(f"/dwellers/vault/{vault.id}/exit-requests", headers=superuser_token_headers)

    assert response.status_code == 200
    requests = response.json()
    assert [entry["dweller_id"] for entry in requests] == [str(dwelling.id)]
    assert requests[0]["dweller_name"] == "Asker Seeker"


async def test_grant_exit_is_permanent_and_removes_the_request(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    vault = await _vault_with_population(async_session, superuser)
    dwelling = await _make_dweller(async_session, vault.id, prefix="Asker")
    await _ask(async_session, dwelling)

    response = await async_client.post(
        f"/dwellers/{dwelling.id}/grant-exit", headers=superuser_token_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["granted"] is True
    assert "did not return" in body["epitaph"]

    await async_session.refresh(dwelling)
    assert dwelling.is_dead is True
    assert dwelling.is_permanently_dead is True
    assert dwelling.death_cause.value == "exile"

    remaining = await async_client.get(f"/dwellers/vault/{vault.id}/exit-requests", headers=superuser_token_headers)
    assert remaining.json() == []


async def test_refuse_exit_keeps_the_request_standing(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    vault = await _vault_with_population(async_session, superuser)
    dwelling = await _make_dweller(async_session, vault.id, prefix="Asker", happiness=80)
    await _ask(async_session, dwelling)

    response = await async_client.post(
        f"/dwellers/{dwelling.id}/refuse-exit", headers=superuser_token_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["granted"] is False
    assert body["happiness"] == 80 - game_config.exit_request.refusal_happiness_penalty

    await async_session.refresh(dwelling)
    assert dwelling.exit_requested_at is not None
    assert dwelling.is_dead is False


async def test_grant_without_a_request_is_rejected(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    superuser,
):
    vault = await _vault_with_population(async_session, superuser)
    quiet = await _make_dweller(async_session, vault.id, prefix="Quiet")

    response = await async_client.post(
        f"/dwellers/{quiet.id}/grant-exit", headers=superuser_token_headers
    )

    assert response.status_code == 400
    assert "has not asked" in response.json()["detail"]
