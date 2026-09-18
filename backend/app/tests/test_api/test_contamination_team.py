"""Tests for the contamination team roster endpoint."""

import pytest
from httpx import AsyncClient

from app.models.vault import Vault


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
