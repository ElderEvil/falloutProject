"""Chat context: persist, restore and trim pydantic-ai conversation state."""

import json

from pydantic_ai.conversation import Conversation
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.tools import DeferredToolRequests
from pydantic_ai.usage import RunUsage

from app.services.chat.context import dump_context, load_context, plan_prune


def _turn(prompt: str, reply: str) -> list:
    return [
        ModelRequest(parts=[UserPromptPart(content=prompt)]),
        ModelResponse(parts=[TextPart(content=reply)]),
    ]


def _conversation(turns: int, *, prompt: str = "hello", reply: str = "hi") -> Conversation:
    messages = []
    for _ in range(turns):
        messages.extend(_turn(prompt, reply))
    return Conversation(messages=messages)


def test_load_context_of_none_starts_a_fresh_conversation() -> None:
    conversation = load_context(None)

    assert conversation.messages == []
    assert conversation.conversation_id
    assert conversation.usage.total_tokens == 0


def test_load_context_of_empty_dict_starts_a_fresh_conversation() -> None:
    assert load_context({}).messages == []


def test_corrupt_context_degrades_to_a_fresh_conversation() -> None:
    assert load_context({"messages": "not-a-list"}).messages == []
    assert load_context({"messages": [{"no_such_field": True}]}).messages == []


def test_dump_then_load_round_trips_messages_usage_and_id() -> None:
    original = Conversation(
        messages=_turn("Where is the water chip?", "Gone. Ask the Overseer."),
        usage=RunUsage(input_tokens=42, output_tokens=7, requests=2),
    )

    dumped = dump_context(original)
    restored = load_context(json.loads(json.dumps(dumped)))

    assert isinstance(dumped, dict)
    assert len(restored.messages) == 2
    assert restored.conversation_id == original.conversation_id
    assert restored.usage.input_tokens == 42
    assert restored.usage.output_tokens == 7
    assert restored.usage.requests == 2


def test_plan_prune_returns_the_original_when_it_fits() -> None:
    conversation = _conversation(3)

    dropped, trimmed = plan_prune(conversation, keep=10, budget=10_000)

    assert dropped == []
    assert trimmed.messages == conversation.messages


def test_plan_prune_drops_oldest_first_and_keeps_the_newest_message() -> None:
    conversation = _conversation(6)

    dropped, trimmed = plan_prune(conversation, keep=4, budget=10_000)

    assert dropped == conversation.messages[:8]
    assert trimmed.messages == conversation.messages[8:]
    assert trimmed.messages[-1] is conversation.messages[-1]


def test_plan_prune_respects_the_token_budget() -> None:
    conversation = _conversation(8, prompt="x" * 400, reply="y" * 400)

    dropped, trimmed = plan_prune(conversation, keep=16, budget=500)

    kept_chars = sum(
        len(part.content)
        for message in trimmed.messages
        for part in message.parts
        if isinstance(part, (UserPromptPart, TextPart))
    )
    assert kept_chars // 4 <= 500
    assert dropped
    assert trimmed.messages[-1] is conversation.messages[-1]


def test_plan_prune_never_drops_the_newest_message_even_over_budget() -> None:
    conversation = Conversation(messages=_turn("x" * 4000, "y" * 4000)[:1])

    dropped, trimmed = plan_prune(conversation, keep=1, budget=1)

    assert dropped == []
    assert trimmed.messages == conversation.messages


def test_plan_prune_may_drop_the_older_half_of_the_last_turn() -> None:
    conversation = _conversation(1, prompt="x" * 4000, reply="y" * 4000)

    dropped, trimmed = plan_prune(conversation, keep=1, budget=1)

    assert dropped == [conversation.messages[0]]
    assert trimmed.messages == [conversation.messages[1]]


def test_plan_prune_keeps_turns_atomic_by_dropping_a_stray_reply() -> None:
    conversation = _conversation(2)

    dropped, trimmed = plan_prune(conversation, keep=3, budget=10_000)

    assert len(dropped) == 2
    assert isinstance(trimmed.messages[0], ModelRequest)
    assert trimmed.messages == conversation.messages[2:]


def test_plan_prune_preserves_identity_usage_and_deferred_requests() -> None:
    deferred = DeferredToolRequests(metadata={"call-1": {"note": "pending"}})
    conversation = Conversation(
        messages=_conversation(6).messages,
        usage=RunUsage(input_tokens=99, output_tokens=11),
        deferred_tool_requests=deferred,
        revision="rev-7",
    )

    dropped, trimmed = plan_prune(conversation, keep=2, budget=10_000)

    assert dropped
    assert trimmed is not conversation
    assert trimmed.conversation_id == conversation.conversation_id
    assert trimmed.usage.input_tokens == 99
    assert trimmed.usage.output_tokens == 11
    assert trimmed.deferred_tool_requests is deferred
    assert trimmed.revision == "rev-7"
    # The caller keeps the untrimmed object for anything it still needs.
    assert len(conversation.messages) == 12


def test_plan_prune_treats_a_non_positive_keep_as_one() -> None:
    conversation = _conversation(3)

    dropped, trimmed = plan_prune(conversation, keep=0, budget=10_000)

    assert len(trimmed.messages) == 1
    assert len(dropped) == len(conversation.messages) - 1
