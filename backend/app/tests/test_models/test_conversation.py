"""Conversation model: one durable thread per (user, dweller) pair."""

from uuid import uuid7

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.chat_message import chat_message as chat_message_crud
from app.models.chat_message import ChatMessage, ChatMessageCreate
from app.models.conversation import Conversation
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.utils.time import utcnow


async def _pair(async_session: AsyncSession, vault: Vault) -> tuple:
    await async_session.refresh(vault, ["user"])
    return vault.user.id, vault.id


async def test_conversation_defaults_and_uuid7_id(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    user_id, vault_id = await _pair(async_session, vault)
    conversation = Conversation(vault_id=vault_id, user_id=user_id, dweller_id=dweller.id)
    assert conversation.id.version == 7
    assert conversation.message_count == 0
    assert conversation.summary is None
    assert conversation.summary_through_message_id is None
    assert conversation.last_message_at is None
    assert conversation.context is None
    async_session.add(conversation)
    await async_session.flush()
    assert conversation.created_at is not None
    assert conversation.updated_at is not None


async def test_conversation_unique_pair_rejects_duplicate(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    user_id, vault_id = await _pair(async_session, vault)
    async_session.add(Conversation(vault_id=vault_id, user_id=user_id, dweller_id=dweller.id))
    await async_session.commit()
    async_session.add(Conversation(vault_id=vault_id, user_id=user_id, dweller_id=dweller.id))
    with pytest.raises(IntegrityError):
        await async_session.flush()
    await async_session.rollback()


async def test_conversation_allows_same_user_with_other_dweller(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    user_id, vault_id = await _pair(async_session, vault)
    other = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault_id))
    async_session.add(Conversation(vault_id=vault_id, user_id=user_id, dweller_id=dweller.id))
    async_session.add(Conversation(vault_id=vault_id, user_id=user_id, dweller_id=other.id))
    await async_session.flush()


async def test_conversation_context_round_trips_json(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    user_id, vault_id = await _pair(async_session, vault)
    context = {"id": str(uuid7()), "messages": [{"kind": "request", "parts": [{"content": "hi"}]}]}
    conversation = Conversation(
        vault_id=vault_id,
        user_id=user_id,
        dweller_id=dweller.id,
        context=context,
        last_message_at=utcnow(),
        message_count=2,
    )
    async_session.add(conversation)
    await async_session.commit()
    conversation_id = conversation.id
    async_session.expunge_all()
    reloaded = await async_session.get(Conversation, conversation_id)
    if reloaded is None:
        raise AssertionError("conversation row vanished after commit")
    assert reloaded.context == context
    assert reloaded.message_count == 2
    assert reloaded.last_message_at is not None
    assert reloaded.last_message_at.tzinfo is not None


async def test_chat_message_links_to_conversation(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    user_id, vault_id = await _pair(async_session, vault)
    conversation = Conversation(vault_id=vault_id, user_id=user_id, dweller_id=dweller.id)
    async_session.add(conversation)
    await async_session.flush()
    message = await chat_message_crud.create_message(
        async_session,
        obj_in=ChatMessageCreate(
            vault_id=vault_id,
            from_user_id=user_id,
            to_dweller_id=dweller.id,
            message_text="hello",
            conversation_id=conversation.id,
        ),
    )
    assert message.conversation_id == conversation.id
    unlinked = await chat_message_crud.create_message(
        async_session,
        obj_in=ChatMessageCreate(
            vault_id=vault_id, from_user_id=user_id, to_dweller_id=dweller.id, message_text="stateless"
        ),
    )
    assert unlinked.conversation_id is None
    await async_session.commit()
    message_id = message.id
    async_session.expunge_all()
    reloaded = await async_session.get(ChatMessage, message_id)
    if reloaded is None:
        raise AssertionError("message row vanished after commit")
    assert reloaded.conversation_id == conversation.id
