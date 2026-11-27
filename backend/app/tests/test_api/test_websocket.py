"""WebSocket endpoint authentication: an unauthenticated socket must never be registered
with the connection manager, so auth failure rejects the handshake (close before accept)."""

from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.chat import ChatStreamError, ChatStreamToken
from main import app


@pytest.fixture
def ws_client() -> TestClient:
    return TestClient(app)


def _token(user_id) -> str:
    return create_access_token(subject=str(user_id))


def _connect(client: TestClient, user_id, dweller_id=None, token: str | None = None):
    query = f"?token={token}" if token is not None else ""
    return client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{dweller_id or uuid4()}{query}")


class _FakeSessionCM:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *args: object) -> None:
        return None


class _EmptyUserSessionCM:
    """A real (empty) user table so the WebSocket lookup runs for a missing id."""

    async def __aenter__(self) -> AsyncSession:
        self._engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
        async with self._engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        self._session = AsyncSession(bind=self._engine, expire_on_commit=False)
        return self._session

    async def __aexit__(self, *args: object) -> None:
        await self._session.close()
        await self._engine.dispose()


@contextmanager
def _ws_patches(user, stream=None):
    with ExitStack() as stack:
        stack.enter_context(patch("app.api.v1.endpoints.websocket.async_session_maker", return_value=_FakeSessionCM()))
        stack.enter_context(
            patch("app.api.v1.endpoints.websocket.user_service.find_user", new=AsyncMock(return_value=user))
        )
        if stream is not None:
            stack.enter_context(patch("app.api.v1.endpoints.websocket.chat_service.stream_response", new=stream))
        yield


class TestChatWebSocketAuth:
    def test_valid_token_connects(self, ws_client: TestClient) -> None:
        user_id = uuid4()
        with _connect(ws_client, user_id, token=_token(user_id)) as ws:
            ws.send_json({"type": "ping"})
            assert ws.receive_json()["type"] == "pong"

    @pytest.mark.parametrize("token", ["not-a-real-jwt", None])
    def test_invalid_or_missing_token_rejected_before_connect(self, ws_client: TestClient, token) -> None:
        with pytest.raises(WebSocketDisconnect) as exc, _connect(ws_client, uuid4(), token=token):
            pass
        assert exc.value.code == 4008

    def test_mismatched_subject_rejected_before_connect(self, ws_client: TestClient) -> None:
        token = _token(uuid4())
        with pytest.raises(WebSocketDisconnect) as exc, _connect(ws_client, uuid4(), token=token):
            pass
        assert exc.value.code == 4008

    @pytest.mark.parametrize("purpose", ["refresh", "email_verification", "password_reset", None])
    def test_non_access_tokens_rejected_before_connect(self, ws_client: TestClient, purpose: str | None) -> None:
        user_id = uuid4()
        payload = {"sub": str(user_id), "exp": datetime.now(UTC) + timedelta(minutes=5)}
        if purpose is not None:
            payload["type"] = purpose
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        with pytest.raises(WebSocketDisconnect) as exc, _connect(ws_client, user_id, token=token):
            pass
        assert exc.value.code == 4008


class TestLegacyPersonalWebSocketRetired:
    def test_legacy_personal_websocket_route_removed(self, ws_client: TestClient) -> None:
        """Connecting to /api/v1/ws/{user_id} must fail — the route no longer exists."""
        with pytest.raises(WebSocketDisconnect), ws_client.websocket_connect(f"/api/v1/ws/{uuid4()}"):
            pass


class TestNotificationSseAuth:
    def test_sse_notifications_rejects_unauthenticated(self, ws_client: TestClient) -> None:
        assert ws_client.get("/api/v1/stream/notifications").status_code == 401

    def test_sse_notifications_route_is_registered(self, ws_client: TestClient) -> None:
        assert "/api/v1/stream/notifications" in ws_client.get("/api/v1/openapi.json").json()["paths"]


class TestChatWebSocketStreaming:
    def test_empty_content_returns_error(self, ws_client: TestClient) -> None:
        user_id = uuid4()
        with _connect(ws_client, user_id, token=_token(user_id)) as ws:
            ws.send_json({"type": "message", "content": "   "})
            assert ws.receive_json() == {"type": "error", "detail": "Message content must be a non-empty string"}

    def test_user_not_found_returns_error(self, ws_client: TestClient) -> None:
        user_id = uuid4()
        with (
            patch("app.api.v1.endpoints.websocket.async_session_maker", new=lambda: _EmptyUserSessionCM()),
            _connect(ws_client, user_id, token=_token(user_id)) as ws,
        ):
            ws.send_json({"type": "message", "content": "Hello!"})
            assert ws.receive_json() == {"type": "error", "detail": "User not found"}

    def test_stream_error_chunk_forwarded(self, ws_client: TestClient) -> None:
        user_id = uuid4()

        async def failing_stream(db_session, user, dweller_id, message_text, *, debug: bool = False):
            yield ChatStreamToken(text="Partial response")
            yield ChatStreamError(detail="AI quota exceeded")

        with (
            _ws_patches(object(), stream=failing_stream),
            _connect(ws_client, user_id, token=_token(user_id)) as ws,
        ):
            ws.send_json({"type": "message", "content": "Hello!"})
            assert ws.receive_json() == {"type": "token", "text": "Partial response"}
            assert ws.receive_json() == {"type": "error", "detail": "AI quota exceeded"}

    @pytest.mark.parametrize("is_superuser", [False, True])
    def test_debug_flag_follows_superuser(self, ws_client: TestClient, is_superuser: bool) -> None:
        """A streamed message passes debug through only for superusers."""
        user_id = uuid4()
        captured: dict[str, object] = {}

        async def stream(db_session, user, dweller_id, message_text, *, debug: bool = False):
            captured["debug"] = debug
            yield ChatStreamToken(text="ok")

        with (
            _ws_patches(SimpleNamespace(is_superuser=is_superuser), stream=stream),
            _connect(ws_client, user_id, token=_token(user_id)) as ws,
        ):
            ws.send_json({"type": "message", "content": "Hello!", "debug": True})
            assert ws.receive_json() == {"type": "token", "text": "ok"}
        assert captured["debug"] is is_superuser


class TestChatWebSocketRoundTrip:
    def test_typing_indicator_round_trips_to_sender(self, ws_client: TestClient) -> None:
        user_id = uuid4()
        with _connect(ws_client, user_id, token=_token(user_id)) as ws:
            ws.send_json({"type": "typing", "is_typing": True})
            assert ws.receive_json() == {"type": "typing", "is_typing": True, "sender": "user"}

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("[1, 2, 3]", {"type": "error", "message": "Message must be a JSON object"}),
            ("{not valid json", {"type": "error", "message": "Invalid JSON format"}),
        ],
    )
    def test_malformed_payloads_return_errors(self, ws_client: TestClient, raw: str, expected: dict) -> None:
        user_id = uuid4()
        with _connect(ws_client, user_id, token=_token(user_id)) as ws:
            ws.send_text(raw)
            assert ws.receive_json() == expected

    def test_unknown_message_type_returns_error(self, ws_client: TestClient) -> None:
        user_id = uuid4()
        with _connect(ws_client, user_id, token=_token(user_id)) as ws:
            ws.send_json({"type": "bogus"})
            assert ws.receive_json() == {"type": "error", "message": "Unknown message type: bogus"}
