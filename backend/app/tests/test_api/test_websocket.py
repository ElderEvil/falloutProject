"""Tests for WebSocket endpoint authentication.

Covers the auth-before-connect ordering fix: an unauthenticated socket must
never be registered with the connection manager. The token is verified from
the query string before the connection is accepted/registered, so a failed
auth causes the WebSocket handshake to be rejected (close before accept).
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from main import app


@pytest.fixture
def ws_client() -> TestClient:
    return TestClient(app)


class TestChatWebSocketAuth:
    """Auth ordering for the chat WebSocket endpoint."""

    def test_valid_token_connects(self, ws_client: TestClient) -> None:
        """A valid token matching the user_id allows the WebSocket to connect."""
        user_id = uuid4()
        token = create_access_token(subject=str(user_id))

        with ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{uuid4()}?token={token}") as ws:
            ws.send_json({"type": "ping"})
            assert ws.receive_json()["type"] == "pong"

    def test_missing_token_rejected_before_connect(self, ws_client: TestClient) -> None:
        """No token → handshake rejected, socket never registered with the manager."""
        user_id = uuid4()
        with (
            pytest.raises(WebSocketDisconnect) as exc,
            ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{uuid4()}"),
        ):
            pass
        assert exc.value.code == 4008

    def test_invalid_token_rejected_before_connect(self, ws_client: TestClient) -> None:
        """Garbage token → handshake rejected."""
        user_id = uuid4()
        with (
            pytest.raises(WebSocketDisconnect) as exc,
            ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{uuid4()}?token=not-a-real-jwt"),
        ):
            pass
        assert exc.value.code == 4008

    def test_token_for_different_user_rejected(self, ws_client: TestClient) -> None:
        """A valid token for a *different* user must not connect to this user_id."""
        token = create_access_token(subject=str(uuid4()))
        with (
            pytest.raises(WebSocketDisconnect) as exc,
            ws_client.websocket_connect(f"/api/v1/ws/chat/{uuid4()}/{uuid4()}?token={token}"),
        ):
            pass
        assert exc.value.code == 4008


class _FakeSessionCM:
    """Async context manager yielding a fake DB session for stream patching."""

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *args: object) -> None:
        return None


async def _fake_stream_response(db_session: object, user: object, dweller_id: object, message_text: str):
    """Async generator mimicking chat_service.stream_response output."""
    yield {"type": "token", "text": "Hello"}
    yield {"type": "token", "text": " world"}
    yield {"type": "done", "dweller_message_id": "msg-1", "happiness_impact": None, "action_suggestion": None}


class TestChatWebSocketStreaming:
    """Text messages stream token/done chunks over the chat WebSocket."""

    def test_message_streams_tokens_then_done(self, ws_client: TestClient) -> None:
        """A valid message streams token chunks followed by a done chunk."""
        user_id = uuid4()
        dweller_id = uuid4()
        token = create_access_token(subject=str(user_id))

        with (
            patch(
                "app.api.v1.endpoints.websocket.async_session_maker",
                return_value=_FakeSessionCM(),
            ),
            patch(
                "app.api.v1.endpoints.websocket.user_crud.get",
                new=AsyncMock(return_value=object()),
            ),
            patch(
                "app.api.v1.endpoints.websocket.chat_service.stream_response",
                new=_fake_stream_response,
            ),
            ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{dweller_id}?token={token}") as ws,
        ):
            ws.send_json({"type": "message", "content": "Hello!"})
            assert ws.receive_json() == {"type": "token", "text": "Hello"}
            assert ws.receive_json() == {"type": "token", "text": " world"}
            done = ws.receive_json()
            assert done["type"] == "done"
            assert done["dweller_message_id"] == "msg-1"

    def test_empty_content_returns_error(self, ws_client: TestClient) -> None:
        """Empty/whitespace-only content is rejected before streaming."""
        user_id = uuid4()
        dweller_id = uuid4()
        token = create_access_token(subject=str(user_id))

        with ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{dweller_id}?token={token}") as ws:
            ws.send_json({"type": "message", "content": "   "})
            assert ws.receive_json() == {
                "type": "error",
                "detail": "Message content must be a non-empty string",
            }

    def test_user_not_found_returns_error(self, ws_client: TestClient) -> None:
        """A missing user yields an error chunk instead of streaming."""
        user_id = uuid4()
        dweller_id = uuid4()
        token = create_access_token(subject=str(user_id))

        with (
            patch(
                "app.api.v1.endpoints.websocket.async_session_maker",
                return_value=_FakeSessionCM(),
            ),
            patch(
                "app.api.v1.endpoints.websocket.user_crud.get",
                new=AsyncMock(return_value=None),
            ),
            ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{dweller_id}?token={token}") as ws,
        ):
            ws.send_json({"type": "message", "content": "Hello!"})
            assert ws.receive_json() == {"type": "error", "detail": "User not found"}

    def test_stream_error_chunk_forwarded(self, ws_client: TestClient) -> None:
        """Error chunks produced by stream_response are forwarded verbatim."""
        user_id = uuid4()
        dweller_id = uuid4()
        token = create_access_token(subject=str(user_id))

        async def failing_stream(db_session: object, user: object, dweller_id: object, message_text: str):
            yield {"type": "error", "detail": "AI quota exceeded"}

        with (
            patch(
                "app.api.v1.endpoints.websocket.async_session_maker",
                return_value=_FakeSessionCM(),
            ),
            patch(
                "app.api.v1.endpoints.websocket.user_crud.get",
                new=AsyncMock(return_value=object()),
            ),
            patch(
                "app.api.v1.endpoints.websocket.chat_service.stream_response",
                new=failing_stream,
            ),
            ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{dweller_id}?token={token}") as ws,
        ):
            ws.send_json({"type": "message", "content": "Hello!"})
            assert ws.receive_json() == {"type": "error", "detail": "AI quota exceeded"}


class TestChatWebSocketRoundTrip:
    """Full round-trip coverage: typing, malformed payloads, unknown types."""

    def test_typing_indicator_round_trips_to_sender(self, ws_client: TestClient) -> None:
        """A typing event is delivered back to the connected chat socket."""
        user_id = uuid4()
        dweller_id = uuid4()
        token = create_access_token(subject=str(user_id))

        with ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{dweller_id}?token={token}") as ws:
            ws.send_json({"type": "typing", "is_typing": True})
            assert ws.receive_json() == {
                "type": "typing",
                "is_typing": True,
                "sender": "user",
            }

    def test_non_object_payload_returns_error(self, ws_client: TestClient) -> None:
        """A JSON array payload is rejected with a clear error."""
        user_id = uuid4()
        dweller_id = uuid4()
        token = create_access_token(subject=str(user_id))

        with ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{dweller_id}?token={token}") as ws:
            ws.send_text("[1, 2, 3]")
            assert ws.receive_json() == {"type": "error", "message": "Message must be a JSON object"}

    def test_invalid_json_returns_error(self, ws_client: TestClient) -> None:
        """Malformed JSON is rejected with an invalid-format error."""
        user_id = uuid4()
        dweller_id = uuid4()
        token = create_access_token(subject=str(user_id))

        with ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{dweller_id}?token={token}") as ws:
            ws.send_text("{not valid json")
            assert ws.receive_json() == {"type": "error", "message": "Invalid JSON format"}

    def test_unknown_message_type_returns_error(self, ws_client: TestClient) -> None:
        """An unsupported message type is reported to the client."""
        user_id = uuid4()
        dweller_id = uuid4()
        token = create_access_token(subject=str(user_id))

        with ws_client.websocket_connect(f"/api/v1/ws/chat/{user_id}/{dweller_id}?token={token}") as ws:
            ws.send_json({"type": "bogus"})
            assert ws.receive_json() == {"type": "error", "message": "Unknown message type: bogus"}
