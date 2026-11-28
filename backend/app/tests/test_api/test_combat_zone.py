"""Combat Zone API tests: feature gate, auth, and the thin endpoint contracts."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import CombatZonePartyStatus, CombatZoneStance
from app.core.game_config import game_config
from app.crud.combat_zone import combat_zone_crud


@pytest.fixture(autouse=True)
def combat_zone_enabled(monkeypatch):
    monkeypatch.setattr(game_config.combat_zone, "enabled", True)
    monkeypatch.setattr(game_config.combat_zone, "travel_seconds", 0)

    monkeypatch.setattr("app.services.combat.combat_zone_service.request_combat_zone_tick", lambda: None)


async def test_lobby_is_readable_but_writes_404_when_the_feature_flag_is_off(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    user_with_vault,
    dweller_in_vault,
    monkeypatch,
):
    _user, vault = user_with_vault
    monkeypatch.setattr(game_config.combat_zone, "enabled", False)

    lobby = await async_client.get("/combat-zone/lobby", headers=superuser_token_headers)
    assert lobby.status_code == 200
    assert lobby.json()["enabled"] is False

    sent = await async_client.post(
        f"/combat-zone/vault/{vault.id}/party",
        headers=superuser_token_headers,
        json={"dweller_id": str(dweller_in_vault.id)},
    )
    assert sent.status_code == 404


async def test_send_read_and_recall_party(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    user_with_vault,
    dweller_in_vault,
):
    _user, vault = user_with_vault
    async_session.add(vault)
    await async_session.commit()

    sent = await async_client.post(
        f"/combat-zone/vault/{vault.id}/party",
        headers=superuser_token_headers,
        json={"dweller_id": str(dweller_in_vault.id)},
    )
    assert sent.status_code == 200
    assert sent.json()["status"] == CombatZonePartyStatus.TRAVELING.value
    assert sent.json()["escrow_caps"] == game_config.combat_zone.entry_fee_caps

    fetched = await async_client.get(f"/combat-zone/vault/{vault.id}/party", headers=superuser_token_headers)
    assert fetched.status_code == 200
    assert fetched.json()["dweller_id"] == str(dweller_in_vault.id)

    party = await combat_zone_crud.get_party_by_vault(async_session, vault.id)
    assert party is not None
    party.status = CombatZonePartyStatus.QUEUED
    party.arrives_at = datetime.now(UTC)
    async_session.add(party)
    await async_session.commit()

    stance = await async_client.post(
        f"/combat-zone/vault/{vault.id}/stance",
        headers=superuser_token_headers,
        json={"stance": CombatZoneStance.FOCUS.value},
    )
    assert stance.status_code == 200
    assert stance.json()["stance"] == CombatZoneStance.FOCUS.value

    recalled = await async_client.delete(f"/combat-zone/vault/{vault.id}/party", headers=superuser_token_headers)
    assert recalled.status_code == 200
    assert recalled.json()["status"] == CombatZonePartyStatus.RETURNING.value
    assert recalled.json()["escrow_caps"] == 0


async def test_send_requires_vault_ownership(
    async_client: AsyncClient,
    async_session: AsyncSession,
    user_with_vault,
    dweller_in_vault,
):
    from app import crud
    from app.schemas.user import UserCreate
    from app.tests.utils.user import user_authentication_headers

    _user, vault = user_with_vault
    await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username="combat_outsider", email="combat_outsider@example.com", password="testpass123"),
    )
    outsider_headers = await user_authentication_headers(
        client=async_client, email="combat_outsider@example.com", password="testpass123"
    )

    response = await async_client.post(
        f"/combat-zone/vault/{vault.id}/party",
        headers=outsider_headers,
        json={"dweller_id": str(dweller_in_vault.id)},
    )

    assert response.status_code == 403


async def test_unknown_match_and_empty_lobby(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    lobby = await async_client.get("/combat-zone/lobby", headers=superuser_token_headers)
    assert lobby.status_code == 200
    assert lobby.json()["enabled"] is True
    assert lobby.json()["queued"] == []

    missing = await async_client.get(
        f"/combat-zone/matches/{uuid4()}",
        headers=superuser_token_headers,
    )
    assert missing.status_code == 404
