"""Process-wide Redis client shared by request-scoped dependencies.

Request dependencies previously built a client (and its own connection pool) per request and
closed it on teardown, so every login, refresh, OAuth step and quota check paid a fresh
handshake. One client per process is enough; the app lifespan closes it.
"""

from redis.asyncio import Redis

from app.core.config import settings

# A hung Redis must fail the request instead of parking it on the default infinite socket wait.
REDIS_SOCKET_TIMEOUT_SECONDS = 5.0


class _RedisHolder:
    """Module-level slot; a holder keeps the mutable state out of a `global` statement."""

    client: Redis | None = None


_holder = _RedisHolder()


def get_shared_redis() -> Redis:
    """Return the process-wide client, creating it on first use."""
    if _holder.client is None:
        _holder.client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
        )
    return _holder.client


async def close_shared_redis() -> None:
    """Close the process-wide client on shutdown."""
    client = _holder.client
    if client is not None:
        _holder.client = None
        await client.aclose()
