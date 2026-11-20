"""CRUD for the permanent user-dweller conversation thread."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.chat_message import ChatMessage
from app.models.conversation import Conversation, ConversationBase


class CRUDConversation(CRUDBase[Conversation, ConversationBase, ConversationBase]):
    async def get_by_pair(self, db: AsyncSession, *, user_id: UUID, dweller_id: UUID) -> Conversation | None:
        """The single thread for a (user, dweller) pair, or None."""
        stmt = select(Conversation).where(Conversation.user_id == user_id, Conversation.dweller_id == dweller_id)
        return (await db.execute(stmt)).scalar_one_or_none()

    async def get_or_create(self, db: AsyncSession, *, vault_id: UUID, user_id: UUID, dweller_id: UUID) -> Conversation:
        """Lazy, race-safe thread creation inside the caller's transaction.

        Select first; on miss insert inside a savepoint so a unique-violation from a concurrent
        creator rolls back only the insert, then re-select and return the winner's row.
        """
        existing = await self.get_by_pair(db, user_id=user_id, dweller_id=dweller_id)
        if existing is not None:
            return existing
        conversation = Conversation(vault_id=vault_id, user_id=user_id, dweller_id=dweller_id)
        try:
            async with db.begin_nested():
                db.add(conversation)
                await db.flush()
        except IntegrityError:
            winner = await self.get_by_pair(db, user_id=user_id, dweller_id=dweller_id)
            if winner is None:
                raise
            return winner
        return conversation

    async def reassign_user(
        self, db: AsyncSession, source_user_id: UUID, target_user_id: UUID, *, commit: bool = False
    ) -> int:
        """Move a merged-away account's threads to the target, folding duplicate dweller threads.

        A pair that exists on both sides keeps the target's thread (and its summary); the
        source messages are repointed onto it so the history stays readable.
        """
        source_threads = list(
            (await db.execute(select(Conversation).where(col(Conversation.user_id) == source_user_id))).scalars()
        )
        if not source_threads:
            return 0

        target_threads = {
            thread.dweller_id: thread
            for thread in (
                await db.execute(select(Conversation).where(col(Conversation.user_id) == target_user_id))
            ).scalars()
        }
        for thread in source_threads:
            existing = target_threads.get(thread.dweller_id)
            if existing is None:
                thread.user_id = target_user_id
                db.add(thread)
                target_threads[thread.dweller_id] = thread
                continue
            await db.execute(
                update(ChatMessage)
                .where(col(ChatMessage.conversation_id) == thread.id)
                .values(conversation_id=existing.id)
            )
            existing.message_count += thread.message_count
            if thread.last_message_at and (
                existing.last_message_at is None or thread.last_message_at > existing.last_message_at
            ):
                existing.last_message_at = thread.last_message_at
            db.add(existing)
            await db.delete(thread)

        await db.flush()
        if commit:
            await db.commit()
        return len(source_threads)

    async def touch(
        self, db: AsyncSession, conversation: Conversation, *, at: datetime, message_count: int | None = None
    ) -> Conversation:
        """Record new activity; increments the count unless an explicit total is given."""
        conversation.last_message_at = at
        conversation.message_count = conversation.message_count + 1 if message_count is None else message_count
        db.add(conversation)
        await db.flush()
        return conversation


conversation = CRUDConversation(Conversation)
