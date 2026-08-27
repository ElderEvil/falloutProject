"""Service for handling chat operations between users and dwellers."""

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI
from pydantic import UUID4
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import ModelHTTPError, UnexpectedModelBehavior
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.dweller_chat_agent import (
    DwellerChatDeps,
    DwellerChatOutput,
    compute_happiness_delta,
    derive_reason_code,
    dweller_chat_agent,
    parse_action_suggestion,
)
from app.core.config import settings
from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.dweller import dweller as dweller_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.crud.vault import vault as vault_crud
from app.models import Dweller, User, Vault
from app.models.chat_message import ChatMessageCreate
from app.models.objective import ObjectiveBase
from app.schemas.chat import ActionSuggestion, DwellerChatResponse, NoAction
from app.schemas.common import ObjectiveKindEnum
from app.schemas.dweller import DwellerReadFull
from app.schemas.happiness import HappinessImpact, HappinessReasonCode
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.ai_service import get_ai_service
from app.services.chat_happiness_service import apply_chat_happiness
from app.services.conversation_service import conversation_service
from app.services.quota_service import QuotaCheckResult, quota_service
from app.services.websocket_manager import manager
from app.utils.exceptions import (
    AccessDeniedException,
    AIProviderCreditsExhaustedException,
    QuotaExceededException,
    ResourceNotFoundException,
)

logger = logging.getLogger(__name__)


@dataclass
class _StreamBundle:
    """Collected structured-stream outcome shared between the streaming helper and stream_response."""

    response_text: str = ""
    happiness_impact: HappinessImpact | None = None
    action_suggestion: ActionSuggestion | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatService:
    """Service for chat-related business logic."""

    async def generate_objectives(
        self,
        objective_kind: ObjectiveKindEnum,
        objective_count: int = 3,
    ) -> list[ObjectiveBase]:
        """Generate game objectives using AI.

        Args:
            objective_kind: Type of objectives to generate
            objective_count: Number of objectives to generate

        Returns:
            List of generated objectives

        Raises:
            ValueError: If AI response is empty or invalid
        """
        instructions = """
        You are an assistant for Vault-Tec Overseer who is in charge of assigning objectives to vault dwellers.
        Objectives and rewards should be in line with the Fallout universe.
        Respond with JSON object containing the generated objectives and rewards.
        Make sure to include various rewards such as caps, lunchboxes, Mr. Handy, and Nuka-Cola Quantum.
        There must be 1 lunchbox/quantum/mr. handy reward maximum per set of objectives.

        Example request: {"objective_kind": "Any", "objective_count": 4}
        Example response:
        [
            {
                "challenge": "Assign 3 dwellers in the right room",
                "reward": "25 caps"
            },
            {
                "challenge": "Collect 100 food",
                "reward": "50 caps"
            },
            {
                "challenge": "Craft 5 outfits",
                "reward": "Nuka-Cola Quantum"
            },
            {
                "challenge": "Kill 100 creatures in the Wasteland",
                "reward": "	1 lunchbox"
            }
        ]
        """

        async_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await async_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": f"Give {objective_count} {objective_kind} objectives"},
            ],
        )
        generated_objectives = response.choices[0].message.content
        if not generated_objectives:
            raise ValueError("Empty response from AI")

        generated_objectives_json = json.loads(generated_objectives)
        return [ObjectiveBase(**obj) for obj in generated_objectives_json]

    async def process_text_message(
        self,
        db_session: AsyncSession,
        user: User,
        dweller_id: UUID4,
        message_text: str,
    ) -> DwellerChatResponse:
        """Process a text chat message from user to dweller.

        Args:
            db_session: Database session
            user: Current authenticated user
            dweller_id: UUID of the dweller to chat with
            message_text: Text message from user

        Returns:
            Chat response with dweller's reply, happiness impact, and action suggestion

        Raises:
            ResourceNotFoundException: If dweller not found
        """
        # Get dweller with full info
        dweller = await dweller_crud.get_full_info(db_session, dweller_id)
        if not dweller:
            raise ResourceNotFoundException(model=Dweller, identifier=dweller_id)

        # Check quota before running chat agent
        quota_result = await quota_service.check_quota(user.id, db_session)

        # Build headers for quota info
        quota_headers = {
            "X-Quota-Remaining": str(quota_result.remaining),
        }
        if quota_result.warning:
            quota_headers["X-Quota-Warning"] = "true"

        # If quota exceeded, raise exception with headers
        if not quota_result.allowed:
            detail = f"Monthly token quota exceeded. You have used {quota_result.used} of {quota_result.limit} tokens."
            raise QuotaExceededException(detail=detail, headers=quota_headers)

        # Run agent and get response
        (
            response_message,
            happiness_impact,
            action_suggestion,
            prompt_tokens,
            completion_tokens,
            total_tokens,
        ) = await self._run_chat_agent(
            db_session=db_session,
            dweller=dweller,
            message_text=message_text,
        )

        # Save LLM interaction statistics
        llm_int_create = LLMInteractionCreate(
            parameters=message_text,
            response=response_message,
            usage="chat_with_dweller",
            user_id=user.id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        llm_interaction = await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        # Save user message to chat history
        await chat_message_crud.create_message(
            db_session,
            obj_in=ChatMessageCreate(
                vault_id=dweller.vault.id,
                from_user_id=user.id,
                to_dweller_id=dweller.id,
                message_text=message_text,
            ),
        )

        # Save dweller response to chat history
        chat_create_data = ChatMessageCreate(
            vault_id=dweller.vault.id,
            from_dweller_id=dweller.id,
            to_user_id=user.id,
            message_text=response_message,
            llm_interaction_id=llm_interaction.id,
        )

        if happiness_impact:
            chat_create_data.happiness_delta = happiness_impact.delta
            chat_create_data.happiness_reason = happiness_impact.reason_text

        dweller_message = await chat_message_crud.create_message(
            db_session,
            obj_in=chat_create_data,
        )

        # Unlock the dweller's map places after 3+ user messages (best-effort)
        await self._maybe_unlock_places(db_session, dweller)

        # Build and return response
        return DwellerChatResponse(
            response=response_message,
            dweller_message_id=dweller_message.id,
            happiness_impact=happiness_impact,
            action_suggestion=action_suggestion,
        )

    async def stream_response(
        self,
        db_session: AsyncSession,
        user: User,
        dweller_id: UUID4,
        message_text: str,
    ) -> AsyncIterator[dict]:
        """Stream a chat response from dweller token-by-token.

        Args:
            db_session: Database session
            user: Current authenticated user
            dweller_id: UUID of the dweller to chat with
            message_text: Text message from user

        Yields:
            Dicts with type "token" for each token, then type "done" with metadata,
            or type "error" on failure.
        """
        try:
            dweller = await dweller_crud.get_full_info(db_session, dweller_id)
            self._validate_dweller_exists(dweller, dweller_id)

            # Ownership check: dweller's vault must belong to the current user
            self._ensure_dweller_has_vault(dweller)
            vault = await vault_crud.get(db_session, dweller.vault.id)
            self._validate_dweller_ownership(dweller, vault, user)

            quota_result = await quota_service.check_quota(user.id, db_session)

            quota_headers = {
                "X-Quota-Remaining": str(quota_result.remaining),
            }
            if quota_result.warning:
                quota_headers["X-Quota-Warning"] = "true"

            self._validate_quota_allowed(quota_result, quota_headers)

            deps = DwellerChatDeps(
                db_session=db_session,
                dweller=dweller,
                vault_id=dweller.vault.id,
            )

            bundle = _StreamBundle()
            async for event in self._stream_with_fallback(deps, dweller, message_text, bundle):
                yield event

            dweller_message_id = await self._persist_chat(
                db_session=db_session,
                user=user,
                dweller=dweller,
                message_text=message_text,
                bundle=bundle,
            )

            yield {
                "type": "done",
                "dweller_message_id": str(dweller_message_id),
                "response_text": bundle.response_text,
                "happiness_impact": bundle.happiness_impact.model_dump(mode="json")
                if bundle.happiness_impact
                else None,
                "action_suggestion": bundle.action_suggestion.model_dump(mode="json")
                if bundle.action_suggestion
                else None,
            }

        except AccessDeniedException as e:
            yield {"type": "error", "detail": str(e.detail)}
            return
        except ModelHTTPError as e:
            logger.exception("Streaming chat response failed")
            yield {"type": "error", "detail": self._extract_provider_reason(e)}
        except Exception as e:
            logger.exception("Streaming chat response failed")
            if isinstance(e, (ValueError, QuotaExceededException)):
                yield {"type": "error", "detail": str(e)}
            else:
                yield {"type": "error", "detail": "An unexpected error occurred during chat"}

    async def _stream_structured(
        self,
        deps: DwellerChatDeps,
        dweller: DwellerReadFull,
        message_text: str,
        bundle: _StreamBundle,
    ) -> AsyncIterator[dict]:
        """Stream structured output tokens and collect the final output metadata into ``bundle``.

        Raises:
            UnexpectedModelBehavior: If the model's structured output fails validation.
        """
        async with dweller_chat_agent.run_stream(message_text, deps=deps) as result:
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

            output: DwellerChatOutput = await result.get_output()

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
            ) = self._extract_usage(result)
            bundle.response_text = output.response_text

    async def _stream_with_fallback(
        self,
        deps: DwellerChatDeps,
        dweller: DwellerReadFull,
        message_text: str,
        bundle: _StreamBundle,
    ) -> AsyncIterator[dict]:
        """Stream structured output, falling back to a non-streaming run on validation failure.

        Yields token events. On ``UnexpectedModelBehavior`` (local providers
        returning invalid structured output mid-stream) retries via the
        retry-capable non-streaming path so action suggestions are preserved.
        The resolved values are written into ``bundle`` for later persistence.
        """
        try:
            async for event in self._stream_structured(deps, dweller, message_text, bundle):
                yield event
        except UnexpectedModelBehavior:
            logger.warning(
                "Structured streaming output invalid for dweller %s, retrying via non-streaming run", dweller.id
            )
            (
                bundle.response_text,
                bundle.happiness_impact,
                bundle.action_suggestion,
                bundle.prompt_tokens,
                bundle.completion_tokens,
                bundle.total_tokens,
            ) = await self._run_chat_agent(deps.db_session, dweller, message_text)
            yield {"type": "token", "text": bundle.response_text, "replace": True}

    async def _persist_chat(
        self,
        *,
        db_session: AsyncSession,
        user: User,
        dweller: DwellerReadFull,
        message_text: str,
        bundle: _StreamBundle,
    ) -> UUID4:
        """Persist the LLM interaction and chat messages for a completed response."""
        llm_int_create = LLMInteractionCreate(
            parameters=message_text,
            response=bundle.response_text,
            usage="chat_with_dweller",
            user_id=user.id,
            prompt_tokens=bundle.prompt_tokens,
            completion_tokens=bundle.completion_tokens,
            total_tokens=bundle.total_tokens,
        )
        llm_interaction = await llm_interaction_crud.create(
            db_session,
            obj_in=llm_int_create,
        )

        await chat_message_crud.create_message(
            db_session,
            obj_in=ChatMessageCreate(
                vault_id=dweller.vault.id,
                from_user_id=user.id,
                to_dweller_id=dweller.id,
                message_text=message_text,
            ),
        )

        chat_create_data = ChatMessageCreate(
            vault_id=dweller.vault.id,
            from_dweller_id=dweller.id,
            to_user_id=user.id,
            message_text=bundle.response_text,
            llm_interaction_id=llm_interaction.id,
        )

        if bundle.happiness_impact:
            chat_create_data.happiness_delta = bundle.happiness_impact.delta
            chat_create_data.happiness_reason = bundle.happiness_impact.reason_text

        dweller_message = await chat_message_crud.create_message(
            db_session,
            obj_in=chat_create_data,
        )

        # Unlock the dweller's map places after 3+ user messages (best-effort)
        await self._maybe_unlock_places(db_session, dweller)

        return dweller_message.id

    @staticmethod
    def _extract_usage(result: AgentRunResult[DwellerChatOutput]) -> tuple[int | None, int | None, int | None]:
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

    @staticmethod
    async def send_chat_notification(
        user_id: UUID4,
        dweller_id: UUID4,
        dweller_message_id: UUID4,
        happiness_impact: HappinessImpact | None,
        action_suggestion: ActionSuggestion | None,
    ) -> None:
        """Send WebSocket notifications for happiness updates and action suggestions. Non-fatal."""
        try:
            if happiness_impact:
                await manager.send_chat_message(
                    {
                        "type": "happiness_update",
                        "happiness_impact": happiness_impact.model_dump(mode="json"),
                        "message_id": str(dweller_message_id),
                    },
                    user_id=user_id,
                    dweller_id=dweller_id,
                )

            if action_suggestion and action_suggestion.action_type != "no_action":
                await manager.send_chat_message(
                    {
                        "type": "action_suggestion",
                        "action_suggestion": action_suggestion.model_dump(mode="json"),
                        "message_id": str(dweller_message_id),
                    },
                    user_id=user_id,
                    dweller_id=dweller_id,
                )
        except Exception:
            logger.exception("Failed to send WebSocket notification, continuing with REST response")

    async def _run_chat_agent(
        self,
        db_session: AsyncSession,
        dweller: DwellerReadFull,
        message_text: str,
    ) -> tuple[str, HappinessImpact | None, ActionSuggestion, int | None, int | None, int | None]:
        """Run the chat agent and process the response.

        Args:
            db_session: Database session
            dweller: Dweller to chat with
            message_text: Text message from user

        Returns:
            Tuple of (response_message, happiness_impact, action_suggestion,
                     prompt_tokens, completion_tokens, total_tokens)
        """
        # Prepare agent dependencies
        deps = DwellerChatDeps(
            db_session=db_session,
            dweller=dweller,
            vault_id=dweller.vault.id,
        )

        try:
            # Run PydanticAI agent with structured output
            result = await dweller_chat_agent.run(message_text, deps=deps)
            output: DwellerChatOutput = result.output

            response_message = output.response_text
            prompt_tokens, completion_tokens, total_tokens = self._extract_usage(result)

            # Compute happiness delta from sentiment score
            delta = compute_happiness_delta(output.sentiment_score)

            # Apply happiness change to dweller and vault
            new_dweller_happiness, _ = await apply_chat_happiness(
                db_session=db_session,
                dweller_id=dweller.id,
                delta=delta,
            )

            # Build happiness impact response
            reason_code_str = derive_reason_code(output.sentiment_score)
            happiness_impact = HappinessImpact(
                delta=delta,
                reason_code=HappinessReasonCode(reason_code_str),
                reason_text=output.reason_text,
                happiness_after=new_dweller_happiness,
            )

            # Parse action suggestion from agent output
            action_suggestion = await parse_action_suggestion(output, db_session, dweller)

        except ModelHTTPError as error:
            if self._provider_credits_are_exhausted(error):
                raise AIProviderCreditsExhaustedException(detail=self._extract_provider_reason(error)) from error
            logger.exception("Dweller chat agent failed, using fallback")
            return await self._run_fallback_chat_agent(dweller, message_text)
        except Exception:
            logger.exception("Dweller chat agent failed, using fallback")
            return await self._run_fallback_chat_agent(dweller, message_text)
        else:
            return response_message, happiness_impact, action_suggestion, prompt_tokens, completion_tokens, total_tokens

    async def _run_fallback_chat_agent(
        self,
        dweller: DwellerReadFull,
        message_text: str,
    ) -> tuple[str, HappinessImpact, ActionSuggestion, int | None, int | None, int | None]:
        """Return a basic chat completion when structured agent processing fails."""
        ai_service = get_ai_service()
        dweller_prompt = conversation_service._build_dweller_prompt(dweller, for_audio=False)

        try:
            result = await ai_service.chat_completion_with_usage(
                [
                    {"role": "system", "content": dweller_prompt.strip()},
                    {"role": "user", "content": message_text},
                ]
            )
        except ModelHTTPError as error:
            if self._provider_credits_are_exhausted(error):
                raise AIProviderCreditsExhaustedException(detail=self._extract_provider_reason(error)) from error
            raise

        happiness_impact = HappinessImpact(
            delta=0,
            reason_code=HappinessReasonCode.CHAT_NEUTRAL,
            reason_text="Chat processed without sentiment analysis",
            happiness_after=dweller.happiness,
        )
        action_suggestion = NoAction(reason="Unable to analyze conversation for suggestions")

        return (
            result.text,
            happiness_impact,
            action_suggestion,
            result.prompt_tokens,
            result.completion_tokens,
            result.total_tokens,
        )

    @staticmethod
    def _provider_credits_are_exhausted(error: ModelHTTPError) -> bool:
        """Return whether a provider error specifically reports an exhausted credits balance."""
        return (
            error.status_code == 429
            and isinstance(error.body, dict)
            and error.body.get("code") == "credit_balance_exhausted"
        )

    @staticmethod
    def _extract_provider_reason(error: ModelHTTPError) -> str:
        """Extract a human-readable reason from a ModelHTTPError without leaking secrets."""
        body = error.body
        if isinstance(body, dict):
            message = body.get("message")
            if isinstance(message, str) and message:
                return message
        return f"AI provider request failed (HTTP {error.status_code})"

    async def _maybe_unlock_places(self, db_session: AsyncSession, dweller: DwellerReadFull) -> None:
        """Unlock the dweller's associated places after 3+ user messages (best-effort)."""
        from app.crud.chat_message import chat_message as chat_crud
        from app.crud.wasteland_location import wasteland_location as wl_crud

        try:
            user_msg_count = await chat_crud.count_user_messages_to_dweller(db_session, dweller_id=dweller.id)
            if user_msg_count >= 3:
                updated = await wl_crud.unlock_places_for_dweller(db_session, dweller_id=dweller.id)
                if updated:
                    logger.info("Unlocked places for dweller %s after %d user messages", dweller.id, user_msg_count)
        except Exception:
            await db_session.rollback()
            logger.exception("Failed to unlock places for dweller %s, continuing", dweller.id)

    @staticmethod
    def _validate_dweller_exists(dweller: "DwellerReadFull | None", _dweller_id: UUID4) -> None:
        """Validate that a dweller exists, raising ValueError if not."""
        if not dweller:
            raise ValueError(f"Dweller {_dweller_id} not found")

    @staticmethod
    def _ensure_dweller_has_vault(dweller: "DwellerReadFull") -> None:
        """Ensure the dweller has a vault, raising AccessDeniedException if not."""
        if not dweller.vault:
            raise AccessDeniedException(detail="Dweller does not belong to the current user")

    @staticmethod
    def _validate_dweller_ownership(dweller: "DwellerReadFull", vault: "Vault | None", user: "User") -> None:
        """Validate that a dweller belongs to the given user, raising AccessDeniedException if not."""
        if not dweller.vault:
            raise AccessDeniedException(detail="Dweller does not belong to the current user")
        if not vault or vault.user_id != user.id:
            raise AccessDeniedException(detail="Dweller does not belong to the current user")

    @staticmethod
    def _validate_quota_allowed(quota_result: "QuotaCheckResult", quota_headers: dict[str, str]) -> None:
        """Validate that the user has remaining quota, raising QuotaExceededException if not."""
        if not quota_result.allowed:
            detail = f"Monthly token quota exceeded. You have used {quota_result.used} of {quota_result.limit} tokens."
            raise QuotaExceededException(detail=detail, headers=quota_headers)


# Singleton instance
chat_service = ChatService()
