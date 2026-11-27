"""Unit coverage for the shared chained-tick wrapper."""

from typing import Any

import app.core.chained_tick as chained


class _FakeRedis:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeSession:
    async def __aenter__(self) -> str:
        return "session"

    async def __aexit__(self, *exc: object) -> bool:
        return False


async def test_run_chained_tick_claims_then_runs_in_a_task_session(monkeypatch) -> None:
    async def claim(redis: Any, chain_key: str, chain_token: str | None) -> str:
        return "next-token"

    fake_redis = _FakeRedis()
    monkeypatch.setattr(chained, "claim_tick_chain", claim)
    monkeypatch.setattr(chained, "task_session", lambda: _FakeSession())
    monkeypatch.setattr(chained.Redis, "from_url", lambda *args, **kwargs: fake_redis)

    seen: list[str] = []

    async def runner(session: str) -> int:
        seen.append(session)
        return 42

    token, result = await chained.run_chained_tick("chain", None, runner)

    assert token == "next-token"
    assert result == 42
    assert seen == ["session"]
    assert fake_redis.closed is True


async def test_run_chained_tick_skips_the_runner_when_the_lease_is_lost(monkeypatch) -> None:
    async def claim(redis: Any, chain_key: str, chain_token: str | None) -> None:
        return None

    fake_redis = _FakeRedis()
    monkeypatch.setattr(chained, "claim_tick_chain", claim)
    monkeypatch.setattr(chained, "task_session", lambda: _FakeSession())
    monkeypatch.setattr(chained.Redis, "from_url", lambda *args, **kwargs: fake_redis)

    async def runner(session: str) -> int:
        raise AssertionError("runner must not execute without a lease")

    token, result = await chained.run_chained_tick("chain", "stale", runner)

    assert token is None
    assert result is None
    assert fake_redis.closed is True
