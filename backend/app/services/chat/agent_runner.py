"""Chat agent execution: structured runs, fallback runs, and provider-failure classification."""

import logging

from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.usage import RunUsage
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.dweller_chat_agent import (
    DwellerChatDeps,
    DwellerChatOutput,
    compute_happiness_delta,
    derive_reason_code,
    dweller_chat_agent,
    parse_action_suggestion,
)
from app.models.base import SPECIALModel
from app.schemas.chat import NoAction
from app.schemas.dweller import DwellerReadFull
from app.schemas.happiness import HappinessImpact, HappinessReasonCode
from app.services.ai_service import get_ai_service
from app.services.chat.models import AgentChatResult
from app.services.chat_happiness_service import apply_chat_happiness
from app.utils.exceptions import AIProviderCreditsExhaustedException

logger = logging.getLogger(__name__)


def extract_usage(usage: RunUsage | None) -> tuple[int | None, int | None, int | None]:
    """Return null counts when provider usage metadata is absent or malformed."""
    if usage is None:
        return None, None, None
    try:
        return usage.input_tokens, usage.output_tokens, usage.total_tokens
    except Exception:
        logger.exception("Failed to extract usage info from agent result")
        return None, None, None


def build_dweller_prompt(dweller: DwellerReadFull, *, for_audio: bool = False) -> str:
    """Build the fallback prompt shared by text and voice chat."""
    special_stats = SPECIALModel.format_special_stats(dweller)
    vault_stats = (
        f" Average happiness: {dweller.vault.happiness}/100"
        f" Power: {dweller.vault.power}/{dweller.vault.power_max}"
        f" Food: {dweller.vault.food}/{dweller.vault.food_max}"
        f" Water: {dweller.vault.water}/{dweller.vault.water_max}"
    )
    audio_instruction = (
        "\nKeep responses concise (under 150 words) since this will be converted to audio." if for_audio else ""
    )
    return f"""
        You are a Vault-Tec Dweller named {dweller.first_name} {dweller.last_name} in a post-apocalyptic world.
        You are {dweller.gender.value} {dweller.age_group.value.title()} of level {dweller.level}.
        You are considered a {dweller.rarity.value} rarity dweller.
        You are in a vault {dweller.vault.number} with a group of other dwellers.
        You are in the {dweller.room.name if dweller.room else "a"} room of the vault.
        Your outfit is {dweller.outfit.name if dweller.outfit else "Vault Suit"}.
        Your weapon is {dweller.weapon.name if dweller.weapon else "Fist"}.
        You have {dweller.stimpack} Stimpacks and {dweller.radaway} Radaways.
        Your health is {dweller.health}/{dweller.max_health}.
        Your happiness level is {dweller.happiness}/100. Don't mention this, just act accordingly.
        Your SPECIAL stats are: {special_stats}. Don't mention them until asked, use this information for acting.
        In case user asks about vault - here is the information: {vault_stats}. Say it in a natural way.
        Try to be in character and be in line with the Fallout universe.{audio_instruction}
        """


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


async def run_chat_agent(
    db_session: AsyncSession,
    dweller: DwellerReadFull,
    message_text: str,
    instructions: str | None = None,
    *,
    for_audio: bool = False,
) -> AgentChatResult:
    """Run the chat agent and process the response, falling back on provider failure."""
    deps = DwellerChatDeps(
        db_session=db_session,
        dweller=dweller,
        vault_id=dweller.vault.id,
    )

    try:
        async with db_session.begin_nested():
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
            prompt_tokens, completion_tokens, total_tokens = extract_usage(result.usage)
    except ModelHTTPError as error:
        if provider_credits_are_exhausted(error):
            raise AIProviderCreditsExhaustedException(detail=extract_provider_reason(error)) from error
        logger.exception("Dweller chat agent failed, using fallback")
        return await run_fallback_chat_agent(dweller, message_text, instructions, for_audio=for_audio)
    except Exception:
        logger.exception("Dweller chat agent failed, using fallback")
        return await run_fallback_chat_agent(dweller, message_text, instructions, for_audio=for_audio)
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
    *,
    for_audio: bool = False,
) -> AgentChatResult:
    """Return a basic chat completion when structured agent processing fails."""
    ai_service = get_ai_service()
    dweller_prompt = build_dweller_prompt(dweller, for_audio=for_audio)
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
            reason_text="Voice chat processed without sentiment analysis"
            if for_audio
            else "Chat processed without sentiment analysis",
            happiness_after=dweller.happiness,
        ),
        action_suggestion=NoAction(reason="Unable to analyze conversation for suggestions"),
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
    )
