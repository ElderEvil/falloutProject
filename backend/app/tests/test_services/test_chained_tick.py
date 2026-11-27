"""Unit coverage for the shared chained-tick wrapper."""

from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

import app.core.chained_tick as chained


class _FakeRedis:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


async def test_run_chained_tick_claims_then_runs_in_a_task_session(async_session: AsyncSession, monkeypatch) -> None:
    async def claim(redis: Any, chain_key: str, chain_token: str | None) -> str:
        return "next-token"

    fake_redis = _FakeRedis()
    monkeypatch.setattr(chained, "claim_tick_chain", claim)

    @asynccontextmanager
    async def task_session():
        yield async_session

    monkeypatch.setattr(chained, "task_session", task_session)
    monkeypatch.setattr(chained.Redis, "from_url", lambda *args, **kwargs: fake_redis)

    seen: list[AsyncSession] = []

    async def runner(session: AsyncSession) -> int:
        await session.execute(text("SELECT 1"))
        seen.append(session)
        return 42

    token, result = await chained.run_chained_tick("chain", None, runner)

    assert token == "next-token"
    assert result == 42
    assert seen == [async_session]
    assert fake_redis.closed is True


async def test_run_chained_tick_skips_the_runner_when_the_lease_is_lost(monkeypatch) -> None:
    async def claim(redis: Any, chain_key: str, chain_token: str | None) -> None:
        return None

    fake_redis = _FakeRedis()
    monkeypatch.setattr(chained, "claim_tick_chain", claim)
    monkeypatch.setattr(chained.Redis, "from_url", lambda *args, **kwargs: fake_redis)

    async def runner(session: AsyncSession) -> int:
        raise AssertionError("runner must not execute without a lease")

    token, result = await chained.run_chained_tick("chain", "stale", runner)

    assert token is None
    assert result is None
    assert fake_redis.closed is True
