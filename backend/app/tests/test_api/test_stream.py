from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.endpoints import stream as stream_module


@pytest.mark.asyncio
async def test_sse_endpoints_release_db_session_before_first_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_subscribe(*_args, **_kwargs):
        yield {"event_id": "1", "data": {}}

    monkeypatch.setattr(stream_module.sse_manager, "subscribe", fake_subscribe)
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    user = SimpleNamespace(id=uuid4())
    vault = SimpleNamespace(id=uuid4())

    cases = [
        (stream_module.stream_notifications, (user, request), "notification"),
        (stream_module.stream_game_ticks, (vault, request), "tick"),
        (stream_module.stream_exploration, (vault, request), "exploration"),
        (stream_module.stream_incidents, (vault, request), "incident"),
    ]

    for endpoint, args, event_name in cases:
        db_session = SimpleNamespace(close=AsyncMock())
        generator = endpoint(*args, db_session)

        event = await anext(generator)

        db_session.close.assert_awaited_once()
        assert event.event == event_name
        await generator.aclose()
