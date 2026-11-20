"""Summary service: fold messages that are about to be pruned into the thread summary.

A summary must exist before its source messages leave the model-facing context, so the caller
hands over exactly the messages ``plan_prune`` dropped. Any failure keeps the previous summary and
never raises into the chat path.
"""

import logging
from collections.abc import Awaitable, Callable, Sequence

from pydantic_ai import Agent
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.chat_message import ChatMessage
from app.models.conversation import Conversation
from app.services.ai_service import get_model

logger = logging.getLogger(__name__)

#: Prompt-in, summary-out. Tests pass a stub so no provider call is made.
Summarizer = Callable[[str], Awaitable[str]]


def _speaker(message: ChatMessage) -> str:
    return "Overseer" if message.from_user_id is not None else "Dweller"


def build_summary_prompt(
    existing_summary: str | None,
    messages: Sequence[ChatMessage],
    *,
    max_chars: int | None = None,
) -> str:
    """Build the rewrite prompt for the running summary plus the messages being folded in."""
    limit = game_config.chat.summary_max_chars if max_chars is None else max_chars
    previous = existing_summary.strip() if existing_summary and existing_summary.strip() else "No summary yet."
    transcript = "\n".join(f"{_speaker(message)}: {message.message_text}" for message in messages)
    return (
        "Rewrite the running summary of a long conversation between the Overseer (the player) "
        "and one vault dweller.\n"
        f"Rules: write in the third person, in at most {limit} characters. Keep every name, "
        "promises, losses and unresolved threads. Drop pleasantries and small talk.\n"
        "Return only the new summary, with no preamble.\n"
        f"<summary>{previous}</summary>\n"
        "<transcript>\n"
        f"{transcript}\n"
        "</transcript>"
    )


def _unsummarised(conversation: Conversation, dropped: Sequence[ChatMessage]) -> list[ChatMessage]:
    """The part of ``dropped`` the stored summary does not cover yet."""
    through = conversation.summary_through_message_id
    if through is None:
        return list(dropped)
    ids = [message.id for message in dropped]
    if through in ids:
        return list(dropped[ids.index(through) + 1 :])
    # A summary already reached further back: everything being dropped now is new.
    return list(dropped)


async def _summarize_with_default_model(prompt: str) -> str:
    model = get_model()
    if model is None:
        raise RuntimeError("No AI model is configured for conversation summaries")
    result = await Agent(model).run(prompt)
    return str(result.output)


async def maybe_summarize(
    db: AsyncSession,
    conversation: Conversation,
    *,
    dropped: Sequence[ChatMessage],
    model: Summarizer | None = None,
) -> Conversation:
    """Rewrite the summary when ``dropped`` messages are about to leave the context.

    ``dropped`` is the oldest batch ``plan_prune`` removed, oldest first. Messages the stored
    summary already covers are skipped. A model failure, a blank answer or a failed write leaves
    the stored summary untouched and returns the conversation unchanged.
    """
    if not dropped:
        return conversation
    pending = _unsummarised(conversation, dropped)
    if not pending:
        return conversation

    max_chars = game_config.chat.summary_max_chars
    prompt = build_summary_prompt(conversation.summary, pending, max_chars=max_chars)
    summarizer = model or _summarize_with_default_model
    try:
        text = (await summarizer(prompt)).strip()
    except Exception:
        logger.warning("Conversation summary failed; keeping the previous summary", exc_info=True)
        return conversation
    if not text:
        return conversation

    previous_summary = conversation.summary
    previous_through = conversation.summary_through_message_id
    conversation.summary = text[:max_chars]
    conversation.summary_through_message_id = pending[-1].id
    try:
        db.add(conversation)
        await db.flush()
    except Exception:
        conversation.summary = previous_summary
        conversation.summary_through_message_id = previous_through
        logger.warning("Conversation summary could not be stored; keeping the previous summary", exc_info=True)
    return conversation
