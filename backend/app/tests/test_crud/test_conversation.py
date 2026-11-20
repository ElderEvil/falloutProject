"""Conversation CRUD: lazy race-safe get_or_create and touch."""

from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.conversation import CRUDConversation
from app.crud.user import build_user_model
from app.models.chat_message import ChatMessage
from app.models.conversation import Conversation
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.utils.time import utcnow


async def _ids(async_session: AsyncSession, vault: Vault) -> tuple[UUID, UUID]:
    await async_session.refresh(vault, ["user"])
    return vault.user.id, vault.id


async def _count(async_session: AsyncSession) -> int:
    return (await async_session.execute(select(func.count()).select_from(Conversation))).scalar_one()


async def test_get_or_create_creates_then_reuses_one_row(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    user_id, vault_id = await _ids(async_session, vault)
    first = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    assert first.id.version == 7
    assert first.message_count == 0
    second = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    assert second.id == first.id
    await async_session.flush()
    assert await _count(async_session) == 1


async def test_get_or_create_recovers_from_create_race(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Staged race (the repo pattern): the loser's pre-insert SELECT saw nothing, its INSERT
    hits the unique constraint, and it must re-select the winner's row instead of raising.
    """
    user_id, vault_id = await _ids(async_session, vault)
    winner = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    await async_session.flush()

    real_get = CRUDConversation.get_by_pair
    calls = {"n": 0}

    async def stale_none_get(self, db, *, user_id, dweller_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await real_get(self, db, user_id=user_id, dweller_id=dweller_id)

    monkeypatch.setattr(CRUDConversation, "get_by_pair", stale_none_get)
    recovered = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )

    assert calls["n"] == 2  # stale pre-insert view + recovery re-select
    assert recovered.id == winner.id
    # The caller's transaction must stay usable after the savepoint rollback.
    await async_session.flush()
    assert await _count(async_session) == 1


async def test_get_or_create_separates_dweller_pairs(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    user_id, vault_id = await _ids(async_session, vault)
    other = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault_id))
    first = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    second = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=other.id
    )
    assert first.id != second.id
    await async_session.flush()
    assert await _count(async_session) == 2


async def test_touch_bumps_count_and_timestamp(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    user_id, vault_id = await _ids(async_session, vault)
    conversation = await crud.conversation.get_or_create(
        async_session, vault_id=vault_id, user_id=user_id, dweller_id=dweller.id
    )
    at = utcnow()
    touched = await crud.conversation.touch(async_session, conversation, at=at)
    assert touched.message_count == 1
    assert touched.last_message_at == at
    later = utcnow()
    touched = await crud.conversation.touch(async_session, conversation, at=later, message_count=7)
    assert touched.message_count == 7
    assert touched.last_message_at == later
    await async_session.flush()


async def _other_user(session: AsyncSession, suffix: str):
    user = build_user_model(username=f"merge{suffix}", email=f"merge{suffix}@example.com")
    session.add(user)
    await session.commit()
    return user


async def test_reassign_user_moves_a_thread_to_the_surviving_account(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A merged-away account's thread must follow its messages, or continuity is lost."""
    _, vault_id = await _ids(async_session, vault)
    source = await _other_user(async_session, "src")
    target = await _other_user(async_session, "tgt")
    thread = Conversation(vault_id=vault_id, user_id=source.id, dweller_id=dweller.id)
    async_session.add(thread)
    await async_session.commit()
    thread_id = thread.id

    moved = await crud.conversation.reassign_user(async_session, source.id, target.id)

    assert moved == 1
    survivor = await crud.conversation.get_by_pair(async_session, user_id=target.id, dweller_id=dweller.id)
    assert survivor is not None
    assert survivor.id == thread_id


async def test_reassign_user_folds_a_duplicate_dweller_thread_onto_the_targets(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Both sides may hold a thread for the same dweller; messages must not be orphaned."""
    _, vault_id = await _ids(async_session, vault)
    source = await _other_user(async_session, "src2")
    target = await _other_user(async_session, "tgt2")
    target_thread = Conversation(vault_id=vault_id, user_id=target.id, dweller_id=dweller.id, message_count=4)
    source_thread = Conversation(vault_id=vault_id, user_id=source.id, dweller_id=dweller.id, message_count=6)
    async_session.add_all([target_thread, source_thread])
    await async_session.commit()
    target_id, source_id = target_thread.id, source_thread.id
    message = ChatMessage(
        vault_id=vault_id,
        from_user_id=source.id,
        to_dweller_id=dweller.id,
        message_text="hello",
        conversation_id=source_id,
    )
    async_session.add(message)
    await async_session.commit()
    message_id = message.id

    moved = await crud.conversation.reassign_user(async_session, source.id, target.id)

    assert moved == 1
    assert await async_session.get(Conversation, source_id) is None
    survivor = await async_session.get(Conversation, target_id)
    assert survivor is not None
    assert survivor.message_count == 10
    repointed = await async_session.get(ChatMessage, message_id)
    assert repointed is not None
    assert repointed.conversation_id == target_id
