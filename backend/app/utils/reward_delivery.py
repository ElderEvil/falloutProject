"""Transaction helpers for all-or-nothing reward settlement."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

_DEFERRED_REWARD_DELIVERY = "deferred_reward_delivery"


@asynccontextmanager
async def defer_reward_delivery(db_session: AsyncSession) -> AsyncIterator[None]:
    """Defer reward commits and events until the caller settles the transaction."""
    previous = db_session.info.get(_DEFERRED_REWARD_DELIVERY, False)
    db_session.info[_DEFERRED_REWARD_DELIVERY] = True
    try:
        yield
    finally:
        db_session.info[_DEFERRED_REWARD_DELIVERY] = previous


def reward_delivery_is_deferred(db_session: AsyncSession) -> bool:
    return bool(db_session.info.get(_DEFERRED_REWARD_DELIVERY, False))


async def persist_reward_change(db_session: AsyncSession, obj: Any | None = None, *, refresh: bool = False) -> None:
    """Flush deferred reward changes or persist ordinary reward grants."""
    if obj is not None:
        db_session.add(obj)
    if reward_delivery_is_deferred(db_session):
        await db_session.flush()
    else:
        await db_session.commit()
        if refresh and obj is not None:
            await db_session.refresh(obj)
