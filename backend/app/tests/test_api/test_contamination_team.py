"""Tests for the contamination team roster endpoint."""

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.hazard_team_service import TEAM_SIZE
from app.tests.test_services._hazard_team_helpers import make_member


@pytest.mark.asyncio
async def test_roster_reports_every_team(
    async_client: AsyncClient, superuser_token_headers: dict[str, str], vault: Vault
):
    """A vault where nobody has qualified still reports both teams, both empty."""
    response = await async_client.get(
        f"/contamination-team/vault/{vault.id}/roster",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["vault_id"] == str(vault.id)
    assert {team["team"] for team in body["teams"]} == {"fire", "radiation"}
    assert all(team["active"] == [] and team["reserve"] == [] for team in body["teams"])


@pytest.mark.asyncio
async def test_set_place_activates_a_reserve_member(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller_data: dict,
):
    """PUT moves a reserve member to active and returns the updated roster."""
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)

    response = await async_client.put(
        f"/contamination-team/vault/{vault.id}/fire/{dweller.id}",
        json={"active": True},
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["vault_id"] == str(vault.id)
    fire = next(team for team in body["teams"] if team["team"] == "fire")
    assert [place["dweller_id"] for place in fire["active"]] == [str(dweller.id)]
    assert fire["active"][0]["name"] == dweller.display_name
    assert fire["active"][0]["level"] == dweller.level
    assert fire["reserve"] == []


@pytest.mark.asyncio
async def test_set_place_full_team_returns_409(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller_data: dict,
):
    """Activating a fourth member while three hold active places is refused."""
    dwellers = []
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
        )
    for dweller in dwellers[:TEAM_SIZE]:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    await make_member(async_session, vault.id, dwellers[TEAM_SIZE].id, HazardTeam.FIRE, RESERVE_STATUS)

    response = await async_client.put(
        f"/contamination-team/vault/{vault.id}/fire/{dwellers[TEAM_SIZE].id}",
        json={"active": True},
        headers=superuser_token_headers,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_set_place_without_a_place_returns_404(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller_data: dict,
):
    """A dweller holding no place on the team cannot be moved."""
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))

    response = await async_client.put(
        f"/contamination-team/vault/{vault.id}/fire/{dweller.id}",
        json={"active": True},
        headers=superuser_token_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_set_place_requires_vault_ownership(
    async_client: AsyncClient,
    normal_user_token_headers: dict[str, str],
    async_session: AsyncSession,
    vault: Vault,
    dweller_data: dict,
):
    """A user who does not own the vault cannot move its team members."""
    dweller = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)

    response = await async_client.put(
        f"/contamination-team/vault/{vault.id}/fire/{dweller.id}",
        json={"active": True},
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
