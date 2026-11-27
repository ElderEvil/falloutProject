"""Shared Redis lease + task-session wrapper for chained tick actors.

Actors keep their own registration, cadence, logging and stop conditions; this only
holds the lease for one run and gives the runner a background-task session.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.tick_chain import claim_tick_chain
from app.db.session import task_session


async def run_chained_tick[T](
    chain_key: str,
    chain_token: str | None,
    runner: Callable[[AsyncSession], Awaitable[T]],
) -> tuple[str | None, T | None]:
    """Claim one chain step, run it in a task session, and release the Redis client."""
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        claimed = await claim_tick_chain(redis, chain_key, chain_token)
        if claimed is None:
            return None, None
        async with task_session() as session:
            return claimed, await runner(session)
    finally:
        await redis.close()
