"""Persistence for chat interactions: LLM usage rows, chat messages, and place unlocks."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.chat_message import chat_message as chat_message_crud
from app.crud.llm_interaction import llm_interaction as llm_interaction_crud
from app.models import User
from app.models.chat_message import ChatMessageCreate
from app.schemas.chat import UnlockedPlace
from app.schemas.dweller import DwellerReadFull
from app.schemas.llm_interaction import LLMInteractionCreate
from app.services.chat import notifications
from app.services.chat.models import StreamBundle

logger = logging.getLogger(__name__)


async def persist_chat(
    *,
    db_session: AsyncSession,
    user: User,
    dweller: DwellerReadFull,
    message_text: str,
    bundle: StreamBundle,
) -> tuple[UUID4, list[UnlockedPlace]]:
    """Persist the LLM interaction and chat messages for a completed response."""
    llm_int_create = LLMInteractionCreate(
        parameters=message_text,
        response=bundle.response_text,
        usage="chat_with_dweller",
        user_id=user.id,
        prompt_tokens=bundle.prompt_tokens,
        completion_tokens=bundle.completion_tokens,
        total_tokens=bundle.total_tokens,
        provider=bundle.provider,
        model=bundle.model,
        prompt_id=bundle.prompt_id,
        instructions_hash=bundle.instructions_hash,
        instructions_snapshot=bundle.instructions_snapshot,
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
    unlocked_places = await notifications.maybe_unlock_places(db_session, dweller)

    return dweller_message.id, unlocked_places
