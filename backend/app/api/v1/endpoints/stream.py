import asyncio
import logging
from collections.abc import AsyncIterable, AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.vault import Vault
from app.schemas.chat import ChatMessage
from app.services.chat_service import chat_service
from app.services.stream_manager import sse_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Send a heartbeat comment every 30 s of inactivity so nginx / Cloudflare /
# browsers detect a dead connection within ~30 s instead of waiting minutes.
_HEARTBEAT_INTERVAL = 30


async def _with_heartbeat(
    stream: AsyncIterable[dict[str, Any]],
    interval: int = _HEARTBEAT_INTERVAL,
) -> AsyncIterator[dict[str, Any] | None]:
    """Interleave heartbeat sentinels into an SSE event stream.

    Yields items from the underlying stream as-is.  If no item arrives
    within *interval* seconds, yields ``None`` instead.  The caller
    converts ``None`` to ``ServerSentEvent(comment="heartbeat")``.

    When the underlying stream is exhausted the wrapper stops without
    yielding a final ``None``.
    """
    it = stream.__aiter__()
    while True:
        try:
            data = await asyncio.wait_for(it.__anext__(), timeout=interval)
            yield data
        except TimeoutError:
            yield None
        except StopAsyncIteration:
            return




@router.get("/stream/notifications", response_class=EventSourceResponse)
async def stream_notifications(
    current_user: CurrentUser,
    request: Request,
) -> AsyncIterable[ServerSentEvent]:
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
) -> AsyncIterable[ServerSentEvent]:
    async for data in _with_heartbeat(sse_manager.subscribe(vault.id, "game_ticks")):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="tick")


@router.post("/stream/chat/{dweller_id}", response_class=EventSourceResponse)
async def stream_chat(
    dweller_id: UUID4,
    current_user: CurrentUser,
    message: ChatMessage,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    request: Request,
) -> AsyncIterable[ServerSentEvent]:
    try:
        async for token_text in chat_service.stream_response(db_session, current_user, dweller_id, message.message):
            if await request.is_disconnected():
                break
            yield ServerSentEvent(data=token_text, event="token")
        yield ServerSentEvent(raw_data="[DONE]", event="done")
    except Exception:
        logger.exception("Chat SSE stream failed")
        yield ServerSentEvent(data="Internal streaming error", event="error")


@router.get("/stream/exploration/{vault_id}", response_class=EventSourceResponse)
async def stream_exploration(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    request: Request,
) -> AsyncIterable[ServerSentEvent]:
    async for data in _with_heartbeat(sse_manager.subscribe(vault.id, "exploration")):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="exploration")
