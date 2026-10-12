"""Tests for player connections and blocking (A1 + A2 identity slice)."""

from uuid import UUID

import pytest
import pytest_asyncio
from faker import Faker
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.connection import Connection
from app.models.user import User
from app.schemas.user import UserCreate
from app.tests.utils.user import user_authentication_headers

fake = Faker()


@pytest_asyncio.fixture
async def two_users(async_session: AsyncSession) -> tuple[tuple[User, dict], tuple[User, dict]]:
    """Two distinct players with known usernames and their login payloads."""
    user_a_in = UserCreate(username="alpha_player", email="alpha@example.com", password=fake.password(length=12))
    user_b_in = UserCreate(username="bravo_player", email="bravo@example.com", password=fake.password(length=12))
    user_a = await crud.user.create(db_session=async_session, obj_in=user_a_in)
    user_b = await crud.user.create(db_session=async_session, obj_in=user_b_in)
    return (user_a, {"email": user_a_in.email, "password": user_a_in.password}), (
        user_b,
        {"email": user_b_in.email, "password": user_b_in.password},
    )


@pytest.fixture(autouse=True)
def _enable_player_connections(monkeypatch: pytest.MonkeyPatch):
    """The feature ships dark; flip it on for the happy paths."""
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.features, "player_connections", True)


async def _auth_headers(async_client: AsyncClient, payload: dict) -> dict[str, str]:
    return await user_authentication_headers(client=async_client, **payload)


class TestFeatureGate:
    async def test_flag_off_returns_422(
        self, async_client: AsyncClient, async_session: AsyncSession, monkeypatch
    ) -> None:
        """Every service entry raises 422 when the flag is off."""
        from app.core.game_config import game_config

        user_in = UserCreate(username="gate_player", email="gate@example.com", password="correct-password")
        await crud.user.create(db_session=async_session, obj_in=user_in)
        token_headers = await _auth_headers(async_client, {"email": user_in.email, "password": "correct-password"})

        monkeypatch.setattr(game_config.features, "player_connections", False)
        response = await async_client.post("/connections", json={"username": "gate_target"}, headers=token_headers)
        assert response.status_code == 422
        assert "disabled" in response.json()["detail"].lower()

    async def test_features_endpoint_reports_switch(self, async_client: AsyncClient, monkeypatch) -> None:
        """/system/features exposes the player_connections switch and tracks flips."""
        from app.core.game_config import game_config

        monkeypatch.setattr(game_config.features, "player_connections", False)
        response = await async_client.get("/system/features")
        assert response.status_code == 200
        assert response.json()["player_connections"] is False


class TestInviteAcceptRevoke:
    async def test_invite_creates_pending_connection(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, _data_b) = two_users
        headers = await _auth_headers(async_client, data_a)

        response = await async_client.post("/connections", json={"username": user_b.username}, headers=headers)

        assert response.status_code == 201
        body = response.json()
        assert body["requester_id"] == str(user_a.id)
        assert body["addressee_id"] == str(user_b.id)
        assert body["status"] == "pending"
        assert body["counterpart_username"] == user_b.username

    async def test_invite_is_idempotent(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, _data_b) = two_users
        headers = await _auth_headers(async_client, data_a)

        first = await async_client.post("/connections", json={"username": user_b.username}, headers=headers)
        second = await async_client.post("/connections", json={"username": user_b.username}, headers=headers)

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

    async def test_accept_connection(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        invite = await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)
        conn_id = invite.json()["id"]

        headers_b = await _auth_headers(async_client, data_b)
        response = await async_client.post(f"/connections/{conn_id}/accept", headers=headers_b)

        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        assert response.json()["responded_at"] is not None

        # Accepting again is an idempotent no-op, not an error.
        again = await async_client.post(f"/connections/{conn_id}/accept", headers=headers_b)
        assert again.status_code == 200
        assert again.json()["status"] == "accepted"

    async def test_requester_cannot_accept_own_invite(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (_user_b, _data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        invite = await async_client.post("/connections", json={"username": "bravo_player"}, headers=headers_a)

        response = await async_client.post(f"/connections/{invite.json()['id']}/accept", headers=headers_a)
        assert response.status_code == 400

    async def test_decline_discards_invite_and_is_reinvitable(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        invite = await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)
        conn_id = invite.json()["id"]

        headers_b = await _auth_headers(async_client, data_b)
        declined = await async_client.post(f"/connections/{conn_id}/decline", headers=headers_b)
        assert declined.status_code == 204

        # Decline again: safe to retry (no-op), still a 204.
        again = await async_client.post(f"/connections/{conn_id}/decline", headers=headers_b)
        assert again.status_code == 204

        # A fresh invite is now allowed.
        reinvite = await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)
        assert reinvite.status_code == 201

    async def test_revoke_pending_invite(
        self, async_client: AsyncClient, two_users, async_session: AsyncSession
    ) -> None:
        (user_a, data_a), (_user_b, _data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        invite = await async_client.post("/connections", json={"username": "bravo_player"}, headers=headers_a)
        conn_id = invite.json()["id"]

        response = await async_client.delete(f"/connections/{conn_id}", headers=headers_a)
        assert response.status_code == 204
        assert await crud.connection.get_by_id(async_session, UUID(conn_id)) is None

    async def test_list_connections_shows_both_roles(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)

        listed = await async_client.get("/connections", headers=headers_a)
        assert listed.status_code == 200
        assert [row["counterpart_username"] for row in listed.json()] == [user_b.username]

        headers_b = await _auth_headers(async_client, data_b)
        listed_b = await async_client.get("/connections", headers=headers_b)
        assert [row["counterpart_username"] for row in listed_b.json()] == [user_a.username]

    async def test_self_invite_rejected(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (_user_b, _data_b) = two_users
        headers = await _auth_headers(async_client, data_a)

        response = await async_client.post("/connections", json={"username": user_a.username}, headers=headers)
        assert response.status_code == 400

    async def test_invite_unknown_username_returns_404(self, async_client: AsyncClient, two_users) -> None:
        (_user_a, data_a), (_user_b, _data_b) = two_users
        headers = await _auth_headers(async_client, data_a)

        response = await async_client.post("/connections", json={"username": "no_such_player"}, headers=headers)
        assert response.status_code == 404


class TestBlocking:
    async def test_block_is_bilateral_and_blocks_both_directions(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        # A blocks B.
        block = await async_client.post(f"/blocks/{user_b.id}", headers=headers_a)
        assert block.status_code == 201
        assert block.json()["blocked_username"] == user_b.username

        # B can no longer invite A (blocking is bilateral).
        invite = await async_client.post("/connections", json={"username": user_a.username}, headers=headers_b)
        assert invite.status_code == 400

        # A can no longer invite B either.
        invite_a = await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)
        assert invite_a.status_code == 400

        # Idempotent re-block.
        again = await async_client.post(f"/blocks/{user_b.id}", headers=headers_a)
        assert again.status_code == 201
        assert again.json()["id"] == block.json()["id"]

    async def test_block_discards_existing_pending_invite(
        self, async_client: AsyncClient, two_users, async_session: AsyncSession
    ) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        invite = await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)
        conn_id = invite.json()["id"]

        await async_client.post(f"/blocks/{user_a.id}", headers=headers_b)
        assert await crud.connection.get_by_id(async_session, UUID(conn_id)) is None

    async def test_unblock_restores_invite_ability(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        await async_client.post(f"/blocks/{user_b.id}", headers=headers_a)

        unblock = await async_client.delete(f"/blocks/{user_b.id}", headers=headers_a)
        assert unblock.status_code == 204
        # Idempotent unblock.
        again = await async_client.delete(f"/blocks/{user_b.id}", headers=headers_a)
        assert again.status_code == 204

        reinvite = await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)
        assert reinvite.status_code == 201

    async def test_list_blocks(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, _data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        await async_client.post(f"/blocks/{user_b.id}", headers=headers_a)

        listed = await async_client.get("/blocks", headers=headers_a)
        assert listed.status_code == 200
        assert [row["blocked_username"] for row in listed.json()] == [user_b.username]

    async def test_self_block_rejected(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (_user_b, _data_b) = two_users
        headers = await _auth_headers(async_client, data_a)

        response = await async_client.post(f"/blocks/{user_a.id}", headers=headers)
        assert response.status_code == 400


class TestUniquePairConstraint:
    async def test_db_rejects_second_row_for_same_unordered_pair(self, async_session: AsyncSession, two_users) -> None:
        """user_a/user_b hold the sorted pair; a reversed duplicate violates uq_connection_user_pair."""
        from app.crud.connection import _ordered_pair

        (user_a, _data_a), (user_b, _data_b) = two_users
        a_id, b_id = user_a.id, user_b.id  # plain UUIDs survive the rollback below
        first, second = _ordered_pair(a_id, b_id)

        async_session.add(
            Connection(requester_id=a_id, addressee_id=b_id, user_a=first, user_b=second, status="pending")
        )
        await async_session.flush()
        async_session.add(
            Connection(requester_id=b_id, addressee_id=a_id, user_a=first, user_b=second, status="pending")
        )
        with pytest.raises(IntegrityError):
            await async_session.commit()
        await async_session.rollback()

        # A different user on either side is fine: the pair is fully distinct.
        user_c_in = UserCreate(username="charlie_player", email="charlie@example.com", password=fake.password(12))
        user_c = await crud.user.create(db_session=async_session, obj_in=user_c_in)
        c_id = user_c.id
        async_session.add(
            Connection(
                requester_id=a_id,
                addressee_id=c_id,
                user_a=min(a_id, c_id),
                user_b=max(a_id, c_id),
                status="pending",
            )
        )
        await async_session.commit()
        assert await crud.connection.get_by_pair(async_session, c_id, a_id) is not None
