"""Chat orchestration service."""

import logging
from collections.abc import AsyncGenerator

from pydantic import UUID4
from pydantic_ai.exceptions import ModelHTTPError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.dweller_chat_agent import DwellerChatDeps
from app.crud.chat_message import chat_message as chat_message_crud
from app.models import User
from app.models.chat_message import ChatMessage
from app.schemas.chat import (
    ActionSuggestion,
    ChatStreamDone,
    ChatStreamError,
    ChatStreamEvent,
    DwellerChatResponse,
    UnlockedPlace,
)
from app.schemas.dweller import DwellerReadFull
from app.schemas.happiness import HappinessImpact
from app.services.access_service import get_accessible_dweller, verify_dweller_access
from app.services.chat.agent_runner import (
    extract_provider_reason,
    run_chat_agent,
)
from app.services.chat.notifications import send_chat_notification, unlock_places_after_conversation
from app.services.chat.persistence import persist_chat
from app.services.chat.streaming import StreamBundle, stream_with_fallback
from app.services.prompt_service import get_instructions, get_provider_model_snapshot
from app.services.quota_service import quota_service
from app.utils.exceptions import (
    AccessDeniedException,
    AIProviderCreditsExhaustedException,
    QuotaExceededException,
    ResourceNotFoundException,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat-related business logic."""

    async def process_text_message(
        self,
        db_session: AsyncSession,
        user: User,
        dweller_id: UUID4,
        message_text: str,
    ) -> DwellerChatResponse:
        """Validate quota, generate a reply, and persist the conversation."""
        async with db_session.begin_nested():
            dweller = await get_accessible_dweller(dweller_id, user, db_session)

            quota_result = await quota_service.check_quota(user.id, db_session)
            quota_result.ensure_allowed()

            instructions, prompt_id, instructions_hash = await get_instructions(db_session, "chat")
            provider, model = await get_provider_model_snapshot(db_session)

            result = await run_chat_agent(
                db_session=db_session,
                dweller=dweller,
                message_text=message_text,
                instructions=instructions,
            )

            bundle = StreamBundle(
                response_text=result.response_text,
                happiness_impact=result.happiness_impact,
                action_suggestion=result.action_suggestion,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                total_tokens=result.total_tokens,
                provider=provider,
                model=model,
                prompt_id=prompt_id,
                instructions_hash=instructions_hash,
                instructions_snapshot=instructions,
            )
            dweller_message_id, unlocked_places = await persist_chat(
                db_session=db_session,
                user=user,
                dweller=dweller,
                message_text=message_text,
                bundle=bundle,
            )

        await db_session.commit()

        return DwellerChatResponse(
            response=result.response_text,
            dweller_message_id=dweller_message_id,
            happiness_impact=result.happiness_impact,
            action_suggestion=result.action_suggestion,
            unlocked_places=unlocked_places,
        )

    async def stream_response(
        self,
        db_session: AsyncSession,
        user: User,
        dweller_id: UUID4,
        message_text: str,
    ) -> AsyncGenerator[ChatStreamEvent]:
        """Yield typed token, completion, or error events for one dweller response."""
        try:
            async with db_session.begin_nested():
                dweller = await get_accessible_dweller(dweller_id, user, db_session)

                quota_result = await quota_service.check_quota(user.id, db_session)
                quota_result.ensure_allowed()

                instructions, prompt_id, instructions_hash = await get_instructions(db_session, "chat")
                provider, model = await get_provider_model_snapshot(db_session)

                deps = DwellerChatDeps(
                    db_session=db_session,
                    dweller=dweller,
                    vault_id=dweller.vault.id,
                )

                bundle = StreamBundle(
                    provider=provider,
                    model=model,
                    prompt_id=prompt_id,
                    instructions_hash=instructions_hash,
                    instructions_snapshot=instructions,
                )
                async for event in stream_with_fallback(deps, dweller, message_text, bundle, instructions):
                    yield event

                dweller_message_id, unlocked_places = await persist_chat(
                    db_session=db_session,
                    user=user,
                    dweller=dweller,
                    message_text=message_text,
                    bundle=bundle,
                )

            await db_session.commit()

            yield ChatStreamDone(
                dweller_message_id=dweller_message_id,
                response_text=bundle.response_text,
                happiness_impact=bundle.happiness_impact,
                action_suggestion=bundle.action_suggestion,
                unlocked_places=unlocked_places,
            )

        except (AccessDeniedException, ResourceNotFoundException) as e:
            yield ChatStreamError(detail=str(e.detail))
            return
        except AIProviderCreditsExhaustedException as e:
            logger.warning("Streaming chat response stopped: provider credits exhausted")
            yield ChatStreamError(detail=str(e.detail))
            return
        except ModelHTTPError as e:
            logger.exception("Streaming chat response failed")
            yield ChatStreamError(detail=extract_provider_reason(e))
        except Exception as e:
            logger.exception("Streaming chat response failed")
            if isinstance(e, (ValueError, QuotaExceededException)):
                yield ChatStreamError(detail=str(e))
            else:
                yield ChatStreamError(detail="An unexpected error occurred during chat")

    async def send_chat_notification(
        self,
        user_id: UUID4,
        dweller_id: UUID4,
        dweller_message_id: UUID4,
        happiness_impact: HappinessImpact | None,
        action_suggestion: ActionSuggestion | None,
    ) -> None:
        """Send WebSocket notifications for happiness updates and action suggestions. Non-fatal."""
        await send_chat_notification(
            user_id=user_id,
            dweller_id=dweller_id,
            dweller_message_id=dweller_message_id,
            happiness_impact=happiness_impact,
            action_suggestion=action_suggestion,
        )

    async def unlock_places_after_conversation(
        self, db_session: AsyncSession, dweller: DwellerReadFull
    ) -> list[UnlockedPlace]:
        """Apply the shared post-message discovery rule for non-text chat flows."""
        return await unlock_places_after_conversation(db_session, dweller)

    async def get_history(
        self,
        db_session: AsyncSession,
        user: User,
        dweller_id: UUID4,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ChatMessage]:
        await verify_dweller_access(dweller_id, user, db_session)
        return await chat_message_crud.get_conversation(
            db_session,
            user_id=user.id,
            dweller_id=dweller_id,
            limit=limit,
            offset=offset,
        )


# Singleton instance
chat_service = ChatService()
