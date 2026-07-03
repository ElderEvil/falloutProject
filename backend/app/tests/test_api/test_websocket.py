"""Tests for WebSocket endpoint authentication.

Covers the auth-before-connect ordering fix: an unauthenticated socket must
never be registered with the connection manager. The token is verified from
the query string before the connection is accepted/registered, so a failed
auth causes the WebSocket handshake to be rejected (close before accept).
"""

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
