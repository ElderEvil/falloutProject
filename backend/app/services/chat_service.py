"""Service for handling chat operations between users and dwellers.

ChatService is the composition root: it owns request validation and orchestration
and delegates agent execution, streaming, persistence, and side-effects to the
focused collaborators in :mod:`app.services.chat`.
"""

import logging
from collections.abc import AsyncIterator

from pydantic import UUID4
from pydantic_ai.exceptions import ModelHTTPError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.dweller_chat_agent import DwellerChatDeps
from app.crud.dweller import dweller as dweller_crud
from app.crud.vault import vault as vault_crud
from app.models import Dweller, User, Vault
from app.schemas.chat import ActionSuggestion, DwellerChatResponse, UnlockedPlace
from app.schemas.dweller import DwellerReadFull
from app.schemas.happiness import HappinessImpact
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
        dweller = await dweller_crud.get_full_info(db_session, dweller_id)
        if not dweller:
            raise ResourceNotFoundException(model=Dweller, identifier=dweller_id)

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
                "unlocked_places": [place.model_dump(mode="json") for place in unlocked_places],
            }

        except AccessDeniedException as e:
            yield {"type": "error", "detail": str(e.detail)}
            return
        except AIProviderCreditsExhaustedException as e:
            logger.warning("Streaming chat response stopped: provider credits exhausted")
            yield {"type": "error", "detail": str(e.detail)}
            return
        except ModelHTTPError as e:
            logger.exception("Streaming chat response failed")
            yield {"type": "error", "detail": extract_provider_reason(e)}
        except Exception as e:
            logger.exception("Streaming chat response failed")
            if isinstance(e, (ValueError, QuotaExceededException)):
                yield {"type": "error", "detail": str(e)}
            else:
                yield {"type": "error", "detail": "An unexpected error occurred during chat"}

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


# Singleton instance
chat_service = ChatService()
