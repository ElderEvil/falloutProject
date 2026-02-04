"""Service for handling chat operations between users and dwellers."""

import json
import logging

from openai import AsyncOpenAI
from pydantic import UUID4
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
from app.models import User
from app.models.chat_message import ChatMessageCreate
from app.models.objective import ObjectiveBase
from app.schemas.chat import ActionSuggestion, DwellerChatResponse, NoAction
from app.schemas.common import ObjectiveKindEnum
from app.schemas.dweller import DwellerReadFull
from app.schemas.happiness import HappinessImpact, HappinessReasonCode
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.chat_happiness_service import apply_chat_happiness
from app.services.conversation_service import conversation_service
from app.services.open_ai import get_ai_service

logger = logging.getLogger(__name__)


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
            ValueError: If dweller not found
        """
        # Get dweller with full info
        dweller = await dweller_crud.get_full_info(db_session, dweller_id)
        if not dweller:
            raise ValueError("Dweller not found")

        # Run agent and get response
        response_message, happiness_impact, action_suggestion = await self._run_chat_agent(
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

        # Build and return response
        return DwellerChatResponse(
            response=response_message,
            dweller_message_id=dweller_message.id,
            happiness_impact=happiness_impact,
            action_suggestion=action_suggestion,
        )

    async def _run_chat_agent(
        self,
        db_session: AsyncSession,
        dweller: DwellerReadFull,
        message_text: str,
    ) -> tuple[str, HappinessImpact | None, ActionSuggestion]:
        """Run the chat agent and process the response.

        Args:
            db_session: Database session
            dweller: Dweller to chat with
            message_text: Text message from user

        Returns:
            Tuple of (response_message, happiness_impact, action_suggestion)
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
                score=output.sentiment_score * 20,  # Scale -5..+5 to -100..+100
                delta=delta,
                reason_code=HappinessReasonCode(reason_code_str),
                reason_text=output.reason_text,
                happiness_after=new_dweller_happiness,
            )

            # Parse action suggestion from agent output
            action_suggestion = await parse_action_suggestion(output, db_session, dweller)

            return response_message, happiness_impact, action_suggestion

        except Exception:
            # Fallback: neutral happiness + no_action on agent failure
            logger.exception("Dweller chat agent failed, using fallback")

            # Fall back to basic chat completion
            ai_service = get_ai_service()
            dweller_prompt = conversation_service._build_dweller_prompt(dweller, for_audio=False)
            response_message = await ai_service.chat_completion(
                [
                    {"role": "system", "content": dweller_prompt.strip()},
                    {"role": "user", "content": message_text},
                ]
            )

            # Neutral fallback - no happiness change
            happiness_impact = HappinessImpact(
                score=0,
                delta=0,
                reason_code=HappinessReasonCode.CHAT_NEUTRAL,
                reason_text="Chat processed without sentiment analysis",
                happiness_after=dweller.happiness,
            )
            action_suggestion = NoAction(reason="Unable to analyze conversation for suggestions")

            return response_message, happiness_impact, action_suggestion


# Singleton instance
chat_service = ChatService()
