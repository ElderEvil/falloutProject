import logging
from typing import Final
from uuid import uuid4

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

TICK_CHAIN_LEASE_SECONDS: Final = 300
_RENEW_CHAIN_SCRIPT: Final = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
end
return false
"""


async def claim_tick_chain(redis: Redis, key: str, token: str | None) -> str | None:
    """Claim a new tick chain or renew a continuation owned by ``token``."""
    candidate = token or uuid4().hex
    if token is None:
        claimed = await redis.set(key, candidate, nx=True, ex=TICK_CHAIN_LEASE_SECONDS)
    else:
        claimed = await redis.eval(
            _RENEW_CHAIN_SCRIPT,
            1,
            key,
            candidate,
            TICK_CHAIN_LEASE_SECONDS,
        )
        if claimed is None:
            logger.warning("Lost tick chain lease for %s - another owner took over", key)
    return candidate if claimed else None
