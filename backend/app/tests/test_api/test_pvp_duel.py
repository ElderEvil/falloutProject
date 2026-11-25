from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio

from app.api.deps import get_current_active_user
from app.core.game_config import game_config
from app.models.user import User
from main import app

BANDS = {"light", "steady", "strong", "elite"}


@pytest.fixture(autouse=True)
def _pvp_duels_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(game_config.features, "pvp_duels", True)


@pytest_asyncio.fixture(name="owner")
async def owner_fixture(user: User) -> AsyncGenerator[User]:
    app.dependency_overrides[get_current_active_user] = lambda: user
    try:
        yield user
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


async def test_flag_off_returns_404_on_all_five_routes(async_client, owner, vault, monkeypatch) -> None:
    monkeypatch.setattr(game_config.features, "pvp_duels", False)
    duel_id = uuid4()
    responses = [
        await async_client.get(f"/vaults/{vault.id}/pvp-duels"),
        await async_client.get(f"/vaults/{vault.id}/pvp-duels/current"),
        await async_client.post(f"/vaults/{vault.id}/pvp-duels", json={}),
        await async_client.post(f"/vaults/{vault.id}/pvp-duels/{duel_id}/accept", json={}),
        await async_client.get(f"/vaults/{vault.id}/pvp-duels/{duel_id}"),
    ]
    assert [response.status_code for response in responses] == [404, 404, 404, 404, 404]


async def test_post_board_accept_and_replay(
    async_client, owner, vault, dweller, user_with_vault, dweller_in_vault
) -> None:
    defender_user, defender_vault = user_with_vault
    posted = await async_client.post(f"/vaults/{vault.id}/pvp-duels", json={"dweller_ids": [str(dweller.id)]})
    assert posted.status_code == 201, posted.text
    duel_id = posted.json()["duel_id"]
    assert posted.json()["challenger_party"]["member_names"] == [dweller.display_name]
    current = await async_client.get(f"/vaults/{vault.id}/pvp-duels/current")
    assert current.status_code == 200
    assert current.json()["duel_id"] == duel_id
    own_board = await async_client.get(f"/vaults/{vault.id}/pvp-duels")
    assert own_board.status_code == 200
    assert own_board.json() == []
    app.dependency_overrides[get_current_active_user] = lambda: defender_user
    board = await async_client.get(f"/vaults/{defender_vault.id}/pvp-duels")
    assert board.status_code == 200
    entry = board.json()[0]
    assert set(entry) == {
        "duel_id",
        "challenger_vault_name",
        "party_size",
        "member_names",
        "power_band",
        "expires_at",
    }
    assert entry["party_size"] == 1
    assert entry["member_names"] == [dweller.display_name]
    assert entry["power_band"] in BANDS
    assert "power" not in entry
    accepted = await async_client.post(
        f"/vaults/{defender_vault.id}/pvp-duels/{duel_id}/accept",
        json={"dweller_ids": [str(dweller_in_vault.id)]},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "ACCEPTED"
    assert accepted.json()["outcome"] in {"challenger", "defender"}
    app.dependency_overrides[get_current_active_user] = lambda: owner
    replay = await async_client.get(f"/vaults/{vault.id}/pvp-duels/{duel_id}")
    assert replay.status_code == 200, replay.text
    body = replay.json()
    assert body["status"] == "ACCEPTED"
    assert body["defender_party"]["vault_name"]
    assert body["journal"][-1]["kind"] == "outcome"
    assert body["accepted_at"] is not None
    current = await async_client.get(f"/vaults/{vault.id}/pvp-duels/current")
    assert current.status_code == 200
    assert current.json() is None


async def test_post_rejects_a_party_outside_one_to_three(async_client, vault, dweller, owner) -> None:
    empty = await async_client.post(f"/vaults/{vault.id}/pvp-duels", json={"dweller_ids": []})
    assert empty.status_code == 422, empty.text
    oversized = await async_client.post(f"/vaults/{vault.id}/pvp-duels", json={"dweller_ids": [str(dweller.id)] * 4})
    assert oversized.status_code == 422, oversized.text
    missing = await async_client.post(f"/vaults/{vault.id}/pvp-duels", json={})
    assert missing.status_code == 422, missing.text
