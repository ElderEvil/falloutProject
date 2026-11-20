"""Assembly and upkeep of the cross-day conversation thread.

One thread per (user, dweller) pair carries four things into a reply: the model-facing
conversation state (trimmed to a window), the summary of everything trimmed out, the
dweller's durable first-person memories, and a digest of what measurably changed in the
vault since the last exchange. Every part is optional and every failure degrades to the
previous stateless behaviour.
"""

import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic_ai.conversation import Conversation
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.conversation import conversation as conversation_crud
from app.crud.dweller_memory import dweller_memory as dweller_memory_crud
from app.models.chat_message import ChatMessage
from app.models.conversation import Conversation as ConversationRow
from app.models.dweller import Dweller
from app.models.dweller_memory import DwellerMemory
from app.services.chat.awareness import build_awareness_digest
from app.services.chat.context import load_context, plan_prune
from app.services.chat.memory import DwellerLike, extract_memories
from app.services.chat.summary import maybe_summarize
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

#: Strong references to background upkeep, so the loop cannot collect a task mid-flight.
_background_tasks: set[asyncio.Task[None]] = set()


class _HasId(Protocol):
    id: UUID


class ContinuityDweller(_HasId, Protocol):
    """The slice of a dweller continuation reads: an id and the vault it belongs to."""

    vault: Any


async def open_thread(db: AsyncSession, *, user_id: UUID, dweller: ContinuityDweller) -> ConversationRow:
    """The permanent thread for this pair, created on first contact."""
    return await conversation_crud.get_or_create(
        db,
        vault_id=dweller.vault.id,
        user_id=user_id,
        dweller_id=dweller.id,
    )


async def load_memories(db: AsyncSession, *, dweller_id: UUID, limit: int) -> list[DwellerMemory]:
    """Newest memories first, bounded by the prompt budget."""
    if limit <= 0:
        return []
    return await dweller_memory_crud.list_for_dweller(db, dweller_id=dweller_id, limit=limit)


def _gap_line(last_message_at: datetime | None) -> str:
    """Turn the silence into something the dweller can act on, in plain language."""
    if last_message_at is None:
        return ""
    elapsed = (utcnow() - last_message_at).total_seconds()
    if elapsed < 3600:
        return ""
    hours = elapsed / 3600
    if hours < 24:
        spoken = f"{int(hours)} hours"
    else:
        days = int(hours // 24)
        spoken = "a day" if days == 1 else f"{days} days"
    return f"It has been {spoken} since the Overseer last spoke to you."


async def begin_exchange(
    db: AsyncSession, *, user_id: UUID, dweller: ContinuityDweller, instructions: str
) -> tuple[str, Conversation, ConversationRow]:
    """Open the pair's thread and fold its continuity into the prompt's instructions.

    The text, streaming and voice paths all start an exchange this way, so none of them can
    quietly drift into answering as if it were the first message.
    """
    thread = await open_thread(db, user_id=user_id, dweller=dweller)
    conversation, continuity = await build_continuation(db, thread=thread, dweller=dweller)
    merged = "\n\n".join(block for block in (instructions, continuity) if block)
    return merged, conversation, thread


async def complete_exchange(db: AsyncSession, *, thread: ConversationRow, state: dict | None) -> UUID:
    """Store the state the run produced and return the thread id.

    The id is returned now because the caller commits afterwards, and a commit expires the
    instance it came from.
    """
    await save_context(db, thread, state=state)
    return thread.id


async def build_continuation(
    db: AsyncSession,
    *,
    thread: ConversationRow,
    dweller: ContinuityDweller,
) -> tuple[Conversation, str]:
    """Return the trimmed model conversation plus the extra instruction blocks.

    Any failure returns a fresh conversation and no blocks: the reply then behaves exactly
    as it did before this feature existed.
    """
    config = game_config.chat
    # load_context already returns a fresh conversation for missing or corrupt state, so
    # an enclosing handler here could only swallow a real bug into a silent stateless reply.
    _, trimmed = plan_prune(
        load_context(thread.context), keep=config.history_messages, budget=config.history_token_budget
    )

    # Savepoint: a failed read would otherwise abort the caller's transaction, so the
    # "reply with what loaded" promise would fail at the first write instead.
    try:
        async with db.begin_nested():
            memories = await load_memories(db, dweller_id=dweller.id, limit=config.memory_prompt_limit)
            digest = await build_awareness_digest(
                db,
                vault_id=dweller.vault.id,
                since=thread.last_message_at,
                max_lines=config.awareness_max_lines,
            )
    except Exception:
        logger.warning(
            "Continuity context incomplete for dweller %s; replying with what loaded", dweller.id, exc_info=True
        )
        memories, digest = [], []

    blocks = [f"Earlier in this conversation: {thread.summary}"] if thread.summary else []
    if memories:
        remembered = "\n".join(f"- {memory.fact}" for memory in memories)
        blocks.append(f"What you remember about yourself:\n{remembered}")
    if digest:
        blocks.append("What changed in the vault since you last spoke:\n" + "\n".join(f"- {line}" for line in digest))
    gap = _gap_line(thread.last_message_at)
    if gap:
        blocks.append(gap)
    return trimmed, "\n\n".join(blocks)


async def save_context(db: AsyncSession, thread: ConversationRow, *, state: dict | None) -> None:
    """Store the state the agent returned, inside the caller's transaction.

    A failed flush has already poisoned that transaction, so there is nothing to recover
    here: the caller's own error path handles it.
    """
    if not state:
        return
    thread.context = state
    db.add(thread)
    await db.flush()


def _carried_messages(thread: ConversationRow) -> int:
    """How many messages the last prompt carried, which is what the stored state holds.

    Trimming is bounded by count *and* token budget, so the count alone would leave
    budget-trimmed turns neither in the window nor in the summary.
    """
    try:
        return len(load_context(thread.context).messages)
    except Exception:
        return game_config.chat.history_messages


def _unsummarised(rows: Sequence[ChatMessage], through_message_id: UUID | None) -> list[ChatMessage]:
    """Rows after the summary cursor, or all of them when the cursor is missing."""
    if through_message_id is None:
        return list(rows)
    for index, row in enumerate(rows):
        if row.id == through_message_id:
            return list(rows[index + 1 :])
    return list(rows)


async def after_exchange(db: AsyncSession, *, thread: ConversationRow, dweller: DwellerLike) -> None:
    """Fold aged messages into the summary and record what the exchange revealed.

    Runs after the reply is committed and persisted, so a failure costs the next turn
    nothing but a stale summary or a missed memory.
    """
    try:
        rows = await chat_message_crud.list_for_conversation(db, conversation_id=thread.id)
        if not rows:
            return
        aged = rows[: max(len(rows) - _carried_messages(thread), 0)]
        dropped = _unsummarised(aged, thread.summary_through_message_id)
        if dropped:
            await maybe_summarize(db, thread, dropped=dropped)
        # The exchange is both halves: memory extraction reads what the Overseer said too.
        exchange = rows[-2:]
        existing = await load_memories(db, dweller_id=dweller.id, limit=game_config.chat.memory_max_per_dweller)
        await extract_memories(db, dweller=dweller, exchange=exchange, existing=existing)
        await db.commit()
    except Exception:
        logger.warning("Post-exchange continuity work failed for dweller %s", dweller.id, exc_info=True)


def schedule_exchange_finish(thread_id: UUID) -> None:
    """Queue the post-exchange work without holding the reply open."""
    task = asyncio.create_task(finish_exchange(thread_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def finish_exchange(thread_id: UUID) -> None:
    """Run the post-exchange work on its own session, after the request transaction closed.

    Called with ``asyncio.create_task`` so the reply is not held hostage by a summary or an
    extraction call. Any failure is logged and changes nothing.
    """
    from app.db.session import async_session_maker

    try:
        async with async_session_maker() as db:
            thread = await db.get(ConversationRow, thread_id)
            if thread is None:
                return
            dweller = await db.get(Dweller, thread.dweller_id)
            if dweller is None:
                return
            await after_exchange(db, thread=thread, dweller=dweller)
    except Exception:
        logger.warning("Background continuity work failed for thread %s", thread_id, exc_info=True)
