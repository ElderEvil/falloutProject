import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import session as session_module


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_async_session_shields_close_from_cancellation(
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

    maker = async_sessionmaker(engine, class_=SlowClosingSession, expire_on_commit=False)
    monkeypatch.setattr(session_module, "async_session_maker", maker)

    generator = session_module.get_async_session()
    session = await anext(generator)
    await session.execute(text("SELECT 1"))
    assert engine.pool.checkedout() == 1

    close_task = asyncio.create_task(generator.aclose())
    await asyncio.wait_for(close_started.wait(), timeout=5)
    close_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await close_task

    for _ in range(200):
        if engine.pool.checkedout() == 0:
            break
        await asyncio.sleep(0.01)

    assert engine.pool.checkedout() == 0
