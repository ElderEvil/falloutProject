"""Structured-output streaming for chat with a non-streaming fallback."""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from pydantic import UUID4
from pydantic_ai.exceptions import UnexpectedModelBehavior

from app.agents.dweller_chat_agent import (
    DwellerChatDeps,
    compute_happiness_delta,
    derive_reason_code,
    dweller_chat_agent,
    parse_action_suggestion,
)
from app.schemas.chat import ActionSuggestion
from app.schemas.dweller import DwellerReadFull
from app.schemas.happiness import HappinessImpact, HappinessReasonCode
from app.services.chat import agent_runner
from app.services.chat_happiness_service import apply_chat_happiness

logger = logging.getLogger(__name__)


@dataclass
class StreamBundle:
    """Collected structured-stream outcome shared between streaming helpers and persistence."""

    response_text: str = ""
    happiness_impact: HappinessImpact | None = None
    action_suggestion: ActionSuggestion | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    provider: str | None = None
    model: str | None = None
    prompt_id: UUID4 | None = None
    instructions_hash: str | None = None
    instructions_snapshot: str | None = None


async def stream_structured(
    deps: DwellerChatDeps,
    dweller: DwellerReadFull,
    message_text: str,
    bundle: StreamBundle,
    instructions: str,
) -> AsyncGenerator[dict]:
    """Stream structured output tokens and collect the final output metadata into ``bundle``.

    Raises:
        UnexpectedModelBehavior: If the model's structured output fails validation.
    """
    async with (
        deps.db_session.begin_nested(),
        dweller_chat_agent.run_stream(message_text, deps=deps, instructions=instructions) as result,
    ):
        # Structured output snapshots can revise previously emitted text.
        # Tell clients to replace their draft when that happens.
        previous_text = ""
        async for partial in result.stream_output():
            partial_text = partial.response_text
            if partial_text.startswith(previous_text):
                yield {"type": "token", "text": partial_text[len(previous_text) :]}
            elif partial_text != previous_text:
                yield {"type": "token", "text": partial_text, "replace": True}
            previous_text = partial_text

        output = await result.get_output()

        delta = compute_happiness_delta(output.sentiment_score)
        new_dweller_happiness, _ = await apply_chat_happiness(
            db_session=deps.db_session,
            dweller_id=dweller.id,
            delta=delta,
        )

        reason_code_str = derive_reason_code(output.sentiment_score)
        bundle.happiness_impact = HappinessImpact(
            delta=delta,
            reason_code=HappinessReasonCode(reason_code_str),
            reason_text=output.reason_text,
            happiness_after=new_dweller_happiness,
        )

        bundle.action_suggestion = await parse_action_suggestion(output, deps.db_session, dweller)
        (
            bundle.prompt_tokens,
            bundle.completion_tokens,
            bundle.total_tokens,
        ) = agent_runner.extract_usage(result.usage)
        bundle.response_text = output.response_text


async def stream_with_fallback(
    deps: DwellerChatDeps,
    dweller: DwellerReadFull,
    message_text: str,
    bundle: StreamBundle,
    instructions: str,
) -> AsyncGenerator[dict]:
    """Stream structured output, falling back to a non-streaming run on validation failure.

    Yields token events. On ``UnexpectedModelBehavior`` (local providers
    returning invalid structured output mid-stream) retries via the
    retry-capable non-streaming path so action suggestions are preserved.
    The resolved values are written into ``bundle`` for later persistence.
    """
    structured_stream = stream_structured(deps, dweller, message_text, bundle, instructions)
    try:
        try:
            async for event in structured_stream:
                yield event
        except UnexpectedModelBehavior:
            logger.warning(
                "Structured streaming output invalid for dweller %s, retrying via non-streaming run", dweller.id
            )
            result = await agent_runner.run_chat_agent(deps.db_session, dweller, message_text, instructions)
            bundle.response_text = result.response_text
            bundle.happiness_impact = result.happiness_impact
            bundle.action_suggestion = result.action_suggestion
            bundle.prompt_tokens = result.prompt_tokens
            bundle.completion_tokens = result.completion_tokens
            bundle.total_tokens = result.total_tokens
            yield {"type": "token", "text": bundle.response_text, "replace": True}
    finally:
        await structured_stream.aclose()
