"""Tests for WebSocket chat endpoint streaming bridge."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import WebSocket
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.endpoints.websocket import chat_websocket_endpoint
from app.models.dweller import Dweller
from app.models.vault import Vault


async def _async_gen(items: list):
    """Yield each item from an async generator — used as mock side-effect."""
    for item in items:
        yield item


# =============================================================================
# Helpers
# =============================================================================


def _mock_ws(*messages: str) -> AsyncMock:
    """Create a mock WebSocket that yields the given text messages, then ends."""
    ws = AsyncMock(spec=WebSocket)
    ws.iter_text.return_value = _async_gen(list(messages))
    return ws


def _patch_all(mock_manager, mock_chat_service, mock_session_maker, mock_crud, user_id, async_session):
    """Apply common patches for all chat WebSocket tests."""
    mock_user = MagicMock()
    mock_user.id = user_id
    mock_crud.user.get = AsyncMock(return_value=mock_user)

    mock_session_maker.return_value.__aenter__.return_value = async_session
    mock_session_maker.return_value.__aexit__.return_value = None

    mock_manager.connect_chat = AsyncMock()
    mock_manager.disconnect_chat = MagicMock()


# =============================================================================
# Tests
# =============================================================================


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.websocket.manager")
@patch("app.api.v1.endpoints.websocket.chat_service")
@patch("app.api.v1.endpoints.websocket.async_session_maker")
@patch("app.api.v1.endpoints.websocket.crud")
async def test_stream_tokens_and_done(
    mock_crud: MagicMock,
    mock_session_maker: MagicMock,
    mock_chat_service: MagicMock,
    mock_manager: MagicMock,
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Token-by-token streaming: tokens received in order, then done metadata matches."""
    user_id = uuid4()
    dweller_msg_id = str(uuid4())
    happiness_impact = {
        "delta": 4,
        "reason_code": "chat_positive",
        "reason_text": "Friendly greeting",
        "happiness_after": 84,
    }

    _patch_all(mock_manager, mock_chat_service, mock_session_maker, mock_crud, user_id, async_session)

    mock_chat_service.stream_response.return_value = _async_gen(
        [
            {"type": "token", "text": "Hello"},
            {"type": "token", "text": " there!"},
            {
                "type": "done",
                "message_id": dweller_msg_id,
                "response": "Hello there!",
                "happiness_impact": happiness_impact,
                "action_suggestion": None,
            },
        ]
    )

    ws = _mock_ws('{"type": "message", "content": "Hi"}')
    await chat_websocket_endpoint(ws, user_id, dweller.id)

    mock_manager.connect_chat.assert_awaited_once_with(ws, user_id, dweller.id)

    # Tokens in correct order
    token_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "token"]
    assert len(token_calls) == 2
    assert token_calls[0][0][0] == {"type": "token", "content": "Hello"}
    assert token_calls[1][0][0] == {"type": "token", "content": " there!"}

    # Done frame
    done_call = next(
        (c for c in ws.send_json.call_args_list if c[0][0].get("type") == "done"),
        None,
    )
    assert done_call is not None
    done = done_call[0][0]
    assert done["message_id"] == dweller_msg_id
    assert done["response"] == "Hello there!"
    assert done["happiness_impact"] == happiness_impact
    assert done["action_suggestion"] is None

    mock_manager.disconnect_chat.assert_called_once_with(ws, user_id, dweller.id)


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.websocket.manager")
@patch("app.api.v1.endpoints.websocket.chat_service")
@patch("app.api.v1.endpoints.websocket.async_session_maker")
@patch("app.api.v1.endpoints.websocket.crud")
async def test_service_error_frame(
    mock_crud: MagicMock,
    mock_session_maker: MagicMock,
    mock_chat_service: MagicMock,
    mock_manager: MagicMock,
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Error frame from service (quota, access denied, etc.) is relayed to client."""
    user_id = uuid4()
    _patch_all(mock_manager, mock_chat_service, mock_session_maker, mock_crud, user_id, async_session)

    mock_chat_service.stream_response.return_value = _async_gen(
        [
            {"type": "token", "text": "So"},
            {"type": "error", "detail": "Quota exceeded for today"},
        ]
    )

    ws = _mock_ws('{"type": "message", "content": "Hello"}')
    await chat_websocket_endpoint(ws, user_id, dweller.id)

    error_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "error"]
    assert len(error_calls) >= 1
    assert error_calls[-1][0][0] == {"type": "error", "message": "Quota exceeded for today"}

    # No done frame emitted after error
    done_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "done"]
    assert len(done_calls) == 0


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.websocket.manager")
@patch("app.api.v1.endpoints.websocket.chat_service")
@patch("app.api.v1.endpoints.websocket.async_session_maker")
@patch("app.api.v1.endpoints.websocket.crud")
async def test_empty_message_error(
    mock_crud: MagicMock,
    mock_session_maker: MagicMock,
    mock_chat_service: MagicMock,
    mock_manager: MagicMock,
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Empty message content returns error frame, does NOT invoke stream."""
    user_id = uuid4()
    _patch_all(mock_manager, mock_chat_service, mock_session_maker, mock_crud, user_id, async_session)
    ws = _mock_ws('{"type": "message", "content": ""}')
    await chat_websocket_endpoint(ws, user_id, dweller.id)

    error_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "error"]
    assert len(error_calls) >= 1
    assert error_calls[0][0][0] == {"type": "error", "message": "Empty message"}

    mock_chat_service.stream_response.assert_not_called()


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.websocket.manager")
@patch("app.api.v1.endpoints.websocket.chat_service")
@patch("app.api.v1.endpoints.websocket.async_session_maker")
@patch("app.api.v1.endpoints.websocket.crud")
async def test_stream_exception_sends_generic_error(
    mock_crud: MagicMock,
    mock_session_maker: MagicMock,
    mock_chat_service: MagicMock,
    mock_manager: MagicMock,
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Unhandled exception during streaming sends generic error and disconnects cleanly."""
    user_id = uuid4()
    _patch_all(mock_manager, mock_chat_service, mock_session_maker, mock_crud, user_id, async_session)

    # stream_response raises instead of yielding an error dict
    mock_chat_service.stream_response.side_effect = RuntimeError("Boom")

    ws = _mock_ws('{"type": "message", "content": "Hello"}')
    await chat_websocket_endpoint(ws, user_id, dweller.id)

    error_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "error"]
    assert len(error_calls) >= 1
    assert error_calls[-1][0][0] == {
        "type": "error",
        "message": "An unexpected error occurred during chat",
    }

    mock_manager.disconnect_chat.assert_called_once_with(ws, user_id, dweller.id)


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.websocket.manager")
@patch("app.api.v1.endpoints.websocket.chat_service")
@patch("app.api.v1.endpoints.websocket.async_session_maker")
@patch("app.api.v1.endpoints.websocket.crud")
async def test_heartbeat_ping_handled(
    mock_crud: MagicMock,
    mock_session_maker: MagicMock,
    mock_chat_service: MagicMock,
    mock_manager: MagicMock,
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Raw 'ping' heartbeat is handled with pong, no JSONDecodeError."""
    user_id = uuid4()
    _patch_all(mock_manager, mock_chat_service, mock_session_maker, mock_crud, user_id, async_session)

    ws = _mock_ws("ping")
    await chat_websocket_endpoint(ws, user_id, dweller.id)

    pong_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "pong"]
    assert len(pong_calls) == 1
    assert pong_calls[0][0][0] == {"type": "pong"}

    error_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "error"]
    assert len(error_calls) == 0

    mock_chat_service.stream_response.assert_not_called()
    mock_manager.disconnect_chat.assert_called_once_with(ws, user_id, dweller.id)


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.websocket.manager")
@patch("app.api.v1.endpoints.websocket.chat_service")
@patch("app.api.v1.endpoints.websocket.async_session_maker")
@patch("app.api.v1.endpoints.websocket.crud")
async def test_double_error_not_sent(
    mock_crud: MagicMock,
    mock_session_maker: MagicMock,
    mock_chat_service: MagicMock,
    mock_manager: MagicMock,
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """RuntimeError from stream_response sends exactly one error frame, not two."""
    user_id = uuid4()
    _patch_all(mock_manager, mock_chat_service, mock_session_maker, mock_crud, user_id, async_session)

    mock_chat_service.stream_response.side_effect = RuntimeError("Boom")

    ws = _mock_ws('{"type": "message", "content": "Hello"}')
    await chat_websocket_endpoint(ws, user_id, dweller.id)

    error_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "error"]
    assert len(error_calls) == 1
    assert error_calls[0][0][0] == {
        "type": "error",
        "message": "An unexpected error occurred during chat",
    }

    mock_manager.disconnect_chat.assert_called_once_with(ws, user_id, dweller.id)


@pytest.mark.asyncio
@patch("app.api.v1.endpoints.websocket.manager")
@patch("app.api.v1.endpoints.websocket.chat_service")
@patch("app.api.v1.endpoints.websocket.async_session_maker")
@patch("app.api.v1.endpoints.websocket.crud")
async def test_heartbeat_ping_before_message(
    mock_crud: MagicMock,
    mock_session_maker: MagicMock,
    mock_chat_service: MagicMock,
    mock_manager: MagicMock,
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Raw ping heartbeat before a valid message still processes the message correctly."""
    user_id = uuid4()
    happiness_impact = {
        "delta": 4,
        "reason_code": "chat_positive",
        "reason_text": "Friendly greeting",
        "happiness_after": 84,
    }

    _patch_all(mock_manager, mock_chat_service, mock_session_maker, mock_crud, user_id, async_session)

    mock_chat_service.stream_response.return_value = _async_gen(
        [
            {"type": "token", "text": "Hello"},
            {
                "type": "done",
                "message_id": str(uuid4()),
                "response": "Hello",
                "happiness_impact": happiness_impact,
                "action_suggestion": None,
            },
        ]
    )

    ws = _mock_ws("ping", '{"type": "message", "content": "Hi"}')
    await chat_websocket_endpoint(ws, user_id, dweller.id)

    pong_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "pong"]
    assert len(pong_calls) == 1

    token_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "token"]
    assert len(token_calls) == 1
    assert token_calls[0][0][0] == {"type": "token", "content": "Hello"}

    done_call = next(
        (c for c in ws.send_json.call_args_list if c[0][0].get("type") == "done"),
        None,
    )
    assert done_call is not None

    error_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "error"]
    assert len(error_calls) == 0

    mock_manager.disconnect_chat.assert_called_once_with(ws, user_id, dweller.id)
