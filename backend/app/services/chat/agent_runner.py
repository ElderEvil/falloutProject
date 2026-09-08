"""Chat agent execution: structured runs, fallback runs, and provider-failure classification."""

import logging
from dataclasses import dataclass

from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import ModelHTTPError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.dweller_chat_agent import (
    DwellerChatDeps,
    DwellerChatOutput,
    compute_happiness_delta,
    derive_reason_code,
    dweller_chat_agent,
    parse_action_suggestion,
)
from app.schemas.chat import ActionSuggestion, NoAction
from app.schemas.dweller import DwellerReadFull
from app.schemas.happiness import HappinessImpact, HappinessReasonCode
from app.services.ai_service import get_ai_service
from app.services.chat_happiness_service import apply_chat_happiness
from app.services.conversation_service import conversation_service
from app.utils.exceptions import AIProviderCreditsExhaustedException

logger = logging.getLogger(__name__)


@dataclass
class AgentChatResult:
    """Outcome of one chat-agent run (structured or fallback)."""

    response_text: str
    happiness_impact: HappinessImpact
    action_suggestion: ActionSuggestion
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


def provider_credits_are_exhausted(error: ModelHTTPError) -> bool:
    """Return whether a provider error specifically reports an exhausted credits balance."""
    return (
        error.status_code == 429
        and isinstance(error.body, dict)
        and error.body.get("code") == "credit_balance_exhausted"
    )


def extract_provider_reason(error: ModelHTTPError) -> str:
    """Extract a human-readable reason from a ModelHTTPError without leaking secrets."""
    body = error.body
    if isinstance(body, dict):
        message = body.get("message")
        if isinstance(message, str) and message:
            return message
    return f"AI provider request failed (HTTP {error.status_code})"


def extract_usage(result: AgentRunResult[DwellerChatOutput]) -> tuple[int | None, int | None, int | None]:
    """Extract token usage from an agent run result.

    Returns:
        Tuple of (prompt_tokens, completion_tokens, total_tokens)
    """
    try:
        usage = result.usage()
        token_counts = usage.input_tokens, usage.output_tokens, usage.total_tokens
    except Exception:
        logger.exception("Failed to extract usage info from agent result")
        return None, None, None
    else:
        return token_counts


async def run_chat_agent(
    db_session: AsyncSession,
    dweller: DwellerReadFull,
    message_text: str,
    instructions: str | None = None,
) -> AgentChatResult:
    """Run the chat agent and process the response, falling back on provider failure."""
    deps = DwellerChatDeps(
        db_session=db_session,
        dweller=dweller,
        vault_id=dweller.vault.id,
    )

    try:
        result = await dweller_chat_agent.run(message_text, deps=deps, instructions=instructions)
        output: DwellerChatOutput = result.output

        delta = compute_happiness_delta(output.sentiment_score)
        new_dweller_happiness, _ = await apply_chat_happiness(
            db_session=db_session,
            dweller_id=dweller.id,
            delta=delta,
        )
        reason_code_str = derive_reason_code(output.sentiment_score)
        happiness_impact = HappinessImpact(
            delta=delta,
            reason_code=HappinessReasonCode(reason_code_str),
            reason_text=output.reason_text,
            happiness_after=new_dweller_happiness,
        )
        action_suggestion = await parse_action_suggestion(output, db_session, dweller)
        prompt_tokens, completion_tokens, total_tokens = extract_usage(result)
    except ModelHTTPError as error:
        if provider_credits_are_exhausted(error):
            raise AIProviderCreditsExhaustedException(detail=extract_provider_reason(error)) from error
        logger.exception("Dweller chat agent failed, using fallback")
        await db_session.rollback()
        return await run_fallback_chat_agent(dweller, message_text, instructions)
    except Exception:
        logger.exception("Dweller chat agent failed, using fallback")
        await db_session.rollback()
        return await run_fallback_chat_agent(dweller, message_text, instructions)
    return AgentChatResult(
        response_text=output.response_text,
        happiness_impact=happiness_impact,
        action_suggestion=action_suggestion,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


async def run_fallback_chat_agent(
    dweller: DwellerReadFull,
    message_text: str,
    instructions: str | None = None,
) -> AgentChatResult:
    """Return a basic chat completion when structured agent processing fails."""
    ai_service = get_ai_service()
    dweller_prompt = conversation_service._build_dweller_prompt(dweller, for_audio=False)
    system_instructions = "\n\n".join(filter(None, (instructions, dweller_prompt.strip())))

    try:
        result = await ai_service.chat_completion_with_usage(
            [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": message_text},
            ]
        )
    except ModelHTTPError as error:
        if provider_credits_are_exhausted(error):
            raise AIProviderCreditsExhaustedException(detail=extract_provider_reason(error)) from error
        raise

    return AgentChatResult(
        response_text=result.text,
        happiness_impact=HappinessImpact(
            delta=0,
            reason_code=HappinessReasonCode.CHAT_NEUTRAL,
            reason_text="Chat processed without sentiment analysis",
            happiness_after=dweller.happiness,
        ),
        action_suggestion=NoAction(reason="Unable to analyze conversation for suggestions"),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
    )
