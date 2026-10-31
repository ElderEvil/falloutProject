"""SSE stream endpoints."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterable, AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy.exc import InterfaceError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentUser, DBSession, get_user_vault_or_403
from app.core.config import settings
from app.core.game_config import game_config
from app.core.stream_manager import sse_manager
from app.models.vault import Vault

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_closed_connection_error(error: BaseException) -> bool:
    detail = f"{error} {getattr(error, 'orig', '')}".lower()
    return "connection is closed" in detail


def _log_close_failure(task: asyncio.Task[None]) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is None:
        return
    if _is_closed_connection_error(error):
        logger.warning("Stream session connection closed during teardown")
    else:
        logger.error("Failed to close stream DB session: %s", error)


async def _close_session(db_session: AsyncSession) -> None:
    task = asyncio.create_task(db_session.close())
    try:
        await asyncio.shield(task)
    except InterfaceError as error:
        if _is_closed_connection_error(error):
            logger.warning("Stream session connection already closed")
            return
        raise
    except asyncio.CancelledError:
        task.add_done_callback(_log_close_failure)
        raise


async def _with_heartbeat(
    stream: AsyncIterable[dict[str, Any]],
    interval: int = settings.SSE_HEARTBEAT_INTERVAL,
) -> AsyncIterator[dict[str, Any] | None]:
    """Interleave heartbeat sentinels into an SSE event stream.

    Uses ``asyncio.wait`` instead of ``asyncio.wait_for`` so the
    underlying ``__anext__`` task is **never cancelled** — the subscriber
    stays alive across heartbeat timeouts.

    Yields:
        Event data dicts from the stream, or None sentinel for heartbeat intervals.
    """
    it = stream.__aiter__()
    task: asyncio.Future | None = None
    try:
        while True:
            if task is None:
                task = asyncio.ensure_future(it.__anext__())
            done, _pending = await asyncio.wait([task], timeout=interval)
            if done:
                try:
                    data = task.result()
                    yield data
                    task = None
                except StopAsyncIteration:
                    return
            else:
                yield None
    finally:
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


@router.get("/stream/notifications", response_class=EventSourceResponse)
async def stream_notifications(
    current_user: CurrentUser,
    request: Request,
    db_session: DBSession,
) -> AsyncIterable[ServerSentEvent]:
    """SSE endpoint for real-time notification events.

    Yields:
        Server-sent events with notification data or heartbeat comments.
    """
    await _close_session(db_session)
    async for data in _with_heartbeat(sse_manager.subscribe(current_user.id, "notifications")):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="notification")


@router.get("/stream/game/{vault_id}/ticks", response_class=EventSourceResponse)
async def stream_game_ticks(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    request: Request,
    db_session: DBSession,
) -> AsyncIterable[ServerSentEvent]:
    """SSE endpoint for real-time game tick events.

    Yields:
        Server-sent events with game tick data or heartbeat comments.
    """
    await _close_session(db_session)
    # Use game tick interval as heartbeat — no point heartbeating faster
    # than the actual data cadence.
    stream = sse_manager.subscribe(vault.id, "game_ticks")
    async for data in _with_heartbeat(stream, interval=game_config.game_loop.tick_interval):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="tick")


@router.get("/stream/exploration/{vault_id}", response_class=EventSourceResponse)
async def stream_exploration(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    request: Request,
    db_session: DBSession,
) -> AsyncIterable[ServerSentEvent]:
    """SSE endpoint for real-time exploration events.

    Yields:
        Server-sent events with exploration data or heartbeat comments.
    """
    await _close_session(db_session)
    async for data in _with_heartbeat(sse_manager.subscribe(vault.id, "exploration")):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="exploration")


@router.get("/stream/incidents/{vault_id}", response_class=EventSourceResponse)
async def stream_incidents(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    request: Request,
    db_session: DBSession,
) -> AsyncIterable[ServerSentEvent]:
    """SSE endpoint for real-time incident events.

    Yields:
        Server-sent events with incident data or heartbeat comments.
    """
    await _close_session(db_session)
    async for data in _with_heartbeat(sse_manager.subscribe(vault.id, "incidents")):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="incident")
