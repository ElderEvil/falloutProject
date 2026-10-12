"""Tests for account-owned direct messages, requests, blocks, and WS delivery (B1)."""

import pytest
import pytest_asyncio
from faker import Faker
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.user import User
from app.schemas.user import UserCreate
from app.tests.utils.user import user_authentication_headers

fake = Faker()


@pytest_asyncio.fixture
async def two_users(async_session: AsyncSession) -> tuple[tuple[User, dict], tuple[User, dict]]:
    """Two distinct players with known usernames and their login payloads."""
    user_a_in = UserCreate(username="delta_player", email="delta@example.com", password=fake.password(length=12))
    user_b_in = UserCreate(username="echo_player", email="echo@example.com", password=fake.password(length=12))
    user_a = await crud.user.create(db_session=async_session, obj_in=user_a_in)
    user_b = await crud.user.create(db_session=async_session, obj_in=user_b_in)
    return (user_a, {"email": user_a_in.email, "password": user_a_in.password}), (
        user_b,
        {"email": user_b_in.email, "password": user_b_in.password},
    )


@pytest.fixture(autouse=True)
def _enable_multiple_player_features(monkeypatch: pytest.MonkeyPatch):
    """The feature ships dark; flip it on for the happy paths."""
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.features, "player_connections", True)


@pytest.fixture(autouse=True)
def _capture_ws_delivery(monkeypatch: pytest.MonkeyPatch):
    """Swap the WebSocket manager for a recording double; no Redis in tests."""
    from app.services import direct_message_service as dms

    class FakeManager:
        def __init__(self):
            self.sent: list[tuple[dict, str]] = []

        async def send_personal_message(self, payload: dict, user_id) -> None:
            self.sent.append((payload, str(user_id)))

    fake = FakeManager()
    monkeypatch.setattr(dms.direct_message_service, "manager", fake)


async def _auth_headers(async_client: AsyncClient, payload: dict) -> dict[str, str]:
    return await user_authentication_headers(client=async_client, **payload)


class TestRequestGating:
    async def test_first_message_to_non_connection_is_a_request(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, _data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)

        response = await async_client.post(f"/messages/{user_b.id}", json={"body": "can we talk?"}, headers=headers_a)

        assert response.status_code == 201
        body = response.json()
        assert body["is_request"] is True
        assert body["sender_user_id"] == str(user_a.id)
        assert body["recipient_user_id"] == str(user_b.id)
        assert body["body"] == "can we talk?"
        assert "read_at" not in body  # read receipts stay internal

    async def test_second_message_gated_until_acceptance(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, _data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)

        first = await async_client.post(f"/messages/{user_b.id}", json={"body": "hello"}, headers=headers_a)
        assert first.status_code == 201

        second = await async_client.post(f"/messages/{user_b.id}", json={"body": "again?"}, headers=headers_a)
        assert second.status_code == 400

    async def test_accepting_request_promotes_to_connection(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        await async_client.post(f"/messages/{user_b.id}", json={"body": "hello"}, headers=headers_a)

        accepted = await async_client.post(f"/messages/{user_a.id}/accept", headers=headers_b)
        assert accepted.status_code == 200
        assert accepted.json()["status"] == "accepted"

        # Accepting again is an idempotent no-op.
        again = await async_client.post(f"/messages/{user_a.id}/accept", headers=headers_b)
        assert again.status_code == 200
        assert again.json()["id"] == accepted.json()["id"]

        # Now real (non-request) messages flow both ways.
        normal = await async_client.post(f"/messages/{user_b.id}", json={"body": "thanks!"}, headers=headers_a)
        assert normal.status_code == 201
        assert normal.json()["is_request"] is False

        reply = await async_client.post(f"/messages/{user_a.id}", json={"body": "any_time"}, headers=headers_b)
        assert reply.status_code == 201
        assert reply.json()["is_request"] is False

    async def test_accept_without_open_request_rejected(self, async_client: AsyncClient, two_users) -> None:
        (user_a, _data_a), (_user_b, data_b) = two_users
        headers_b = await _auth_headers(async_client, data_b)

        response = await async_client.post(f"/messages/{user_a.id}/accept", headers=headers_b)
        assert response.status_code == 400

    async def test_decline_request_discards_and_allows_new_request(self, async_client: AsyncClient, two_users) -> None:
        import uuid

        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        await async_client.post(f"/messages/{user_b.id}", json={"body": "hi"}, headers=headers_a)

        declined = await async_client.post(f"/messages/{user_a.id}/decline", headers=headers_b)
        assert declined.status_code == 204
        again = await async_client.post(f"/messages/{user_a.id}/decline", headers=headers_b)
        assert again.status_code == 204

        # A NEW request after a decline is allowed (the old one was discarded).
        retry = await async_client.post(f"/messages/{user_b.id}", json={"body": "hi again"}, headers=headers_a)
        assert retry.status_code == 201
        assert retry.json()["is_request"] is True
        assert uuid.UUID(retry.json()["id"]) is not None

    async def test_accept_then_revoke_allows_a_fresh_request(self, async_client: AsyncClient, two_users) -> None:
        """Accepting must retire the request; after a revoke a new request is allowed again."""
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        await async_client.post(f"/messages/{user_b.id}", json={"body": "hi"}, headers=headers_a)
        accepted = await async_client.post(f"/messages/{user_a.id}/accept", headers=headers_b)
        assert accepted.status_code == 200

        revoked = await async_client.delete(f"/connections/{accepted.json()['id']}", headers=headers_a)
        assert revoked.status_code == 204

        fresh = await async_client.post(f"/messages/{user_b.id}", json={"body": "still there?"}, headers=headers_a)
        assert fresh.status_code == 201
        assert fresh.json()["is_request"] is True

    async def test_block_then_unblock_allows_a_fresh_request(self, async_client: AsyncClient, two_users) -> None:
        """A block discards the pending request, so an unblocked sender can request again."""
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        await async_client.post(f"/messages/{user_b.id}", json={"body": "hi"}, headers=headers_a)
        assert (await async_client.post(f"/blocks/{user_a.id}", headers=headers_b)).status_code == 201
        assert (await async_client.delete(f"/blocks/{user_a.id}", headers=headers_b)).status_code == 204

        fresh = await async_client.post(f"/messages/{user_b.id}", json={"body": "unblocked?"}, headers=headers_a)
        assert fresh.status_code == 201
        assert fresh.json()["is_request"] is True


class TestMessaging:
    async def test_self_message_rejected(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (_user_b, _data_b) = two_users
        headers = await _auth_headers(async_client, data_a)

        response = await async_client.post(f"/messages/{user_a.id}", json={"body": "nope"}, headers=headers)
        assert response.status_code == 400

    async def test_empty_body_rejected(self, async_client: AsyncClient, two_users) -> None:
        (_user_a, data_a), (user_b, _data_b) = two_users
        headers = await _auth_headers(async_client, data_a)

        blank = await async_client.post(f"/messages/{user_b.id}", json={"body": "   "}, headers=headers)
        assert blank.status_code == 422
        too_long = await async_client.post(f"/messages/{user_b.id}", json={"body": "x" * 2001}, headers=headers)
        assert too_long.status_code == 422

    async def test_thread_isolation_between_accounts(
        self, async_client: AsyncClient, async_session: AsyncSession, two_users
    ) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        await async_client.post(f"/messages/{user_b.id}", json={"body": "private"}, headers=headers_a)

        thread = await async_client.get(f"/messages/{user_b.id}", headers=headers_a)
        assert thread.status_code == 200
        assert [m["body"] for m in thread.json()] == ["private"]

        # A third user cannot see it: their thread with A is empty and the
        # counterpart list never exposes A<->B content.
        outsider_in = UserCreate(
            username="foxtrot_player", email="foxtrot@example.com", password=fake.password(length=12)
        )
        outsider = await crud.user.create(db_session=async_session, obj_in=outsider_in)
        outsider_data = {"email": outsider_in.email, "password": outsider_in.password}
        outsider_headers = await _auth_headers(async_client, outsider_data)
        spy = await async_client.get(f"/messages/{user_a.id}", headers=outsider_headers)
        assert spy.status_code == 200
        assert spy.json() == []

        conversations = await async_client.get("/messages", headers=outsider_headers)
        assert conversations.status_code == 200
        assert all(c["counterpart_user_id"] != str(user_b.id) for c in conversations.json())

    async def test_ws_push_to_both_participants(self, async_client: AsyncClient, two_users) -> None:
        from app.services.direct_message_service import direct_message_service

        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        send = await async_client.post(f"/messages/{user_b.id}", json={"body": "over the wire"}, headers=headers_a)
        assert send.status_code == 201

        sent = direct_message_service.manager.sent
        assert len(sent) == 2
        payloads = {user: payload for payload, user in sent}
        assert set(payloads) == {str(user_a.id), str(user_b.id)}
        for payload in payloads.values():
            assert payload["type"] == "direct_message"
            assert payload["message"]["body"] == "over the wire"
            assert payload["message"]["sender_user_id"] == str(user_a.id)

    async def test_delivery_failure_does_not_fail_the_send(
        self, async_client: AsyncClient, two_users, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A committed message must survive a socket failure: delivery is best-effort."""
        from app.services.direct_message_service import direct_message_service

        (_user_a, data_a), (user_b, _data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)

        async def boom(*_args, **_kwargs):
            raise RuntimeError("socket gone")

        monkeypatch.setattr(direct_message_service.manager, "send_personal_message", boom)
        send = await async_client.post(f"/messages/{user_b.id}", json={"body": "hi"}, headers=headers_a)
        assert send.status_code == 201


class TestBlockingMessages:
    async def test_block_stops_messages_both_directions(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        block = await async_client.post(f"/blocks/{user_b.id}", headers=headers_a)
        assert block.status_code == 201

        from_b = await async_client.post(f"/messages/{user_a.id}", json={"body": "hi"}, headers=headers_b)
        assert from_b.status_code == 400
        from_a = await async_client.post(f"/messages/{user_b.id}", json={"body": "hi"}, headers=headers_a)
        assert from_a.status_code == 400

    async def test_existing_thread_becomes_read_only(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        # Connect first, exchange messages, then block: history stays readable.
        await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)
        invite = await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)
        accepted = await async_client.post(f"/connections/{invite.json()['id']}/accept", headers=headers_b)
        assert accepted.status_code == 200

        original = await async_client.post(f"/messages/{user_b.id}", json={"body": "before block"}, headers=headers_a)
        assert original.status_code == 201

        await async_client.post(f"/blocks/{user_b.id}", headers=headers_a)

        # Read-only: both sides can still read the thread.
        thread_a = await async_client.get(f"/messages/{user_b.id}", headers=headers_a)
        assert thread_a.status_code == 200
        assert [m["body"] for m in thread_a.json()] == ["before block"]
        thread_b = await async_client.get(f"/messages/{user_a.id}", headers=headers_b)
        assert thread_b.status_code == 200
        assert [m["body"] for m in thread_b.json()] == ["before block"]

        # But neither can send anymore.
        send_a = await async_client.post(f"/messages/{user_b.id}", json={"body": "can I?"}, headers=headers_a)
        assert send_a.status_code == 400


class TestConversationList:
    async def test_list_shows_summary_with_unread_and_request_flag(self, async_client: AsyncClient, two_users) -> None:
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        await async_client.post(f"/messages/{user_b.id}", json={"body": "request message"}, headers=headers_a)

        # B's list: pending request flagged, unread 1.
        mine = await async_client.get("/messages", headers=headers_b)
        assert mine.status_code == 200
        assert len(mine.json()) == 1
        summary = mine.json()[0]
        assert summary["counterpart_user_id"] == str(user_a.id)
        assert summary["counterpart_username"] == user_a.username
        assert summary["has_pending_request"] is True
        assert summary["unread_count"] == 1
        assert summary["last_message"]["body"] == "request message"

        # Reading the thread clears the unread count and the request flag once
        # the pair is connected.
        await async_client.post(f"/messages/{user_a.id}/accept", headers=headers_b)
        await async_client.get(f"/messages/{user_a.id}", headers=headers_b)
        await async_client.post(f"/messages/{user_b.id}", json={"body": "accepted"}, headers=headers_a)

        mine = await async_client.get("/messages", headers=headers_b)
        summary = mine.json()[0]
        assert summary["has_pending_request"] is False
        assert summary["unread_count"] == 1
        assert summary["last_message"]["body"] == "accepted"


class TestRateLimit:
    async def test_send_cap_enforced_per_user(self, async_client: AsyncClient, two_users, monkeypatch) -> None:
        from app.services.direct_message_service import direct_message_service

        monkeypatch.setattr(direct_message_service, "max_sends_per_window", 2)
        (user_a, data_a), (user_b, data_b) = two_users
        headers_a = await _auth_headers(async_client, data_a)
        headers_b = await _auth_headers(async_client, data_b)

        # Connect the pair so every send is a normal message.
        invite = await async_client.post("/connections", json={"username": user_b.username}, headers=headers_a)
        await async_client.post(f"/connections/{invite.json()['id']}/accept", headers=headers_b)

        assert (
            await async_client.post(f"/messages/{user_b.id}", json={"body": "1"}, headers=headers_a)
        ).status_code == 201
        assert (
            await async_client.post(f"/messages/{user_b.id}", json={"body": "2"}, headers=headers_a)
        ).status_code == 201
        third = await async_client.post(f"/messages/{user_b.id}", json={"body": "3"}, headers=headers_a)
        assert third.status_code == 400
