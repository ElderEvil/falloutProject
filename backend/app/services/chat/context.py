"""Persistence and windowing for the model-facing pydantic-ai conversation.

The library's :class:`pydantic_ai.conversation.Conversation` carries messages *and* running usage,
the conversation id and deferred tool requests, so it is stored as-is instead of rebuilding a
message history from ``ChatMessage`` rows. A conversation row keeps the serialised form in JSONB.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from pydantic_ai.conversation import Conversation, ConversationTypeAdapter
from pydantic_ai.messages import ModelMessage, ModelResponse

logger = logging.getLogger(__name__)

#: Rough token estimate used to bound the prompt: characters per token.
CHARS_PER_TOKEN = 4


def load_context(raw: Any) -> Conversation:
    """Deserialise the stored state; a missing/corrupt value starts a fresh conversation."""
    if not raw:
        return Conversation()
    if isinstance(raw, (str, bytes)):
        payload: str | bytes = raw
    else:
        try:
            payload = json.dumps(raw)
        except TypeError, ValueError:
            logger.warning("Stored conversation context is not JSON-serialisable; starting fresh")
            return Conversation()
    try:
        return ConversationTypeAdapter.validate_json(payload)
    except Exception:
        logger.warning("Stored conversation context could not be restored; starting fresh", exc_info=True)
        return Conversation()


def dump_context(conversation: Conversation) -> dict:
    """Serialise the conversation into a JSONB-friendly dict."""
    return json.loads(ConversationTypeAdapter.dump_json(conversation))


def message_chars(message: ModelMessage) -> int:
    """Approximate the prompt cost of one message in characters.

    Only textual content is counted: strings on any part, multimodal string items and tool-call
    arguments. A part holding binary content contributes nothing rather than a meaningless length.
    """
    total = 0
    for part in getattr(message, "parts", ()):
        content = getattr(part, "content", None)
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, Sequence) and not isinstance(content, (bytes, bytearray)):
            total += sum(len(item) for item in content if isinstance(item, str))
        args_as_json = getattr(part, "args_as_json_str", None)
        if callable(args_as_json):
            total += len(args_as_json())
    return total


def plan_prune(
    conversation: Conversation,
    *,
    keep: int,
    budget: int,
) -> tuple[list[ModelMessage], Conversation]:
    """Split off the oldest messages that no longer fit; return (dropped, trimmed copy).

    Drops from the front until both the ``keep`` message count and the ``len(content) // 4`` token
    ``budget`` hold, never touching the newest message. The window always holds whole turns, so
    ``keep`` below two still carries a request with its reply. The trimmed copy keeps ``usage``,
    ``conversation_id``, ``deferred_tool_requests`` and ``revision``; ``new_message_index`` is
    cleared because the history it points into has been rewritten. The original is left intact.
    """
    messages = list(conversation.messages)
    min_keep = max(keep, 2)
    chars = [message_chars(message) for message in messages]
    total_chars = sum(chars)

    dropped = 0
    while len(messages) - dropped > min_keep or total_chars // CHARS_PER_TOKEN > budget:
        if len(messages) - dropped <= 1:
            break
        total_chars -= chars[dropped]
        dropped += 1

    if dropped == 0:
        return [], conversation
    # Keep turns atomic: a window that opens with a reply whose request was dropped is
    # half a turn. Drop that reply too unless it is the newest message.
    if isinstance(messages[dropped], ModelResponse) and len(messages) - dropped > 1:
        dropped += 1
    return messages[:dropped], replace(conversation, messages=messages[dropped:], new_message_index=None)
