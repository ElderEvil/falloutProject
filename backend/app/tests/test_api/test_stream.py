import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InterfaceError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.endpoints import stream as stream_module


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sse_endpoints_release_real_connection_before_first_event(
    pg_session_maker, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, maker = pg_session_maker
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")

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
        session = maker()
        await session.execute(text("SELECT 1"))
        assert engine.pool.checkedout() == 1

        generator = endpoint(*args, session)
        event = await anext(generator)

        assert event.event == event_name
        assert engine.pool.checkedout() == 0
        await generator.aclose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_sse_session_close_is_shielded_from_cancellation(
    pg_session_maker, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, _maker = pg_session_maker
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")

    close_started = asyncio.Event()

    class SlowClosingSession(AsyncSession):
        async def close(self) -> None:
            close_started.set()
            await asyncio.sleep(0.2)
            await super().close()

    async def fake_subscribe(*_args, **_kwargs):
        yield {"event_id": "1", "data": {}}

    monkeypatch.setattr(stream_module.sse_manager, "subscribe", fake_subscribe)
    session = SlowClosingSession(bind=engine)
    await session.execute(text("SELECT 1"))
    assert engine.pool.checkedout() == 1

    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    generator = stream_module.stream_notifications(SimpleNamespace(id=uuid4()), request, session)
    task = asyncio.create_task(anext(generator))
    await asyncio.wait_for(close_started.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    for _ in range(200):
        if engine.pool.checkedout() == 0:
            break
        await asyncio.sleep(0.01)

    assert engine.pool.checkedout() == 0
    await generator.aclose()


@pytest.mark.asyncio
async def test_close_session_swallows_closed_connection() -> None:
    error = InterfaceError(
        "ROLLBACK",
        {},
        Exception("cannot call Transaction.rollback(): the underlying connection is closed"),
    )
    session = SimpleNamespace(close=AsyncMock(side_effect=error))

    await stream_module._close_session(session)


@pytest.mark.asyncio
async def test_close_session_reraises_unexpected_interface_error() -> None:
    error = InterfaceError("ROLLBACK", {}, Exception("some other interface failure"))
    session = SimpleNamespace(close=AsyncMock(side_effect=error))

    with pytest.raises(InterfaceError, match="some other interface failure"):
        await stream_module._close_session(session)
