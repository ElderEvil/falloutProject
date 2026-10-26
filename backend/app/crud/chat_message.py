from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, case
from sqlmodel import col, func, or_, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.chat_message import ChatMessage, ChatMessageCreate, ChatMessageRead


class CRUDChatMessage(CRUDBase[ChatMessage, ChatMessageCreate, ChatMessageRead]):
    async def get_conversation(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        dweller_id: UUID | None = None,
        dweller_to_dweller: tuple[UUID, UUID] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ChatMessage]:
        """
        Get conversation history between:
        - User and Dweller (provide user_id and dweller_id)
        - Dweller and Dweller (provide dweller_to_dweller tuple)
        """
        if dweller_to_dweller:
            dweller_1, dweller_2 = dweller_to_dweller
            query = (
                select(ChatMessage)
                .where(
                    or_(
                        # Dweller 1 -> Dweller 2
                        ((ChatMessage.from_dweller_id == dweller_1) & (ChatMessage.to_dweller_id == dweller_2)),
                        # Dweller 2 -> Dweller 1
                        ((ChatMessage.from_dweller_id == dweller_2) & (ChatMessage.to_dweller_id == dweller_1)),
                    )
                )
                .order_by(col(ChatMessage.created_at).asc())
                .offset(offset)
                .limit(limit)
            )
        elif user_id and dweller_id:
            query = (
                select(ChatMessage)
                .where(
                    or_(
                        # User -> Dweller
                        ((ChatMessage.from_user_id == user_id) & (ChatMessage.to_dweller_id == dweller_id)),
                        # Dweller -> User
                        ((ChatMessage.from_dweller_id == dweller_id) & (ChatMessage.to_user_id == user_id)),
                    )
                )
                .order_by(col(ChatMessage.created_at).asc())
                .offset(offset)
                .limit(limit)
            )
        else:
            raise ValueError("Either provide user_id and dweller_id, or dweller_to_dweller tuple")

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_recent_conversations(self, db: AsyncSession, *, vault_id: UUID, limit: int = 10) -> list[ChatMessage]:
        """Get recent chat messages for a vault"""
        query = (
            select(ChatMessage)
            .where(ChatMessage.vault_id == vault_id)
            .order_by(col(ChatMessage.created_at).desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create_message(
        self,
        db: AsyncSession,
        *,
        obj_in: ChatMessageCreate,
    ) -> ChatMessage:
        """Stage a message in the caller's conversation transaction."""
        message = ChatMessage.model_validate(obj_in)
        db.add(message)
        await db.flush()
        return message

    async def count_user_messages_to_dweller(self, db: AsyncSession, *, dweller_id: UUID) -> int:
        """Count messages from any user to a specific dweller."""
        stmt = (
            select(func.count())
            .select_from(ChatMessage)
            .where(
                col(ChatMessage.from_user_id).is_not(None),
                ChatMessage.to_dweller_id == dweller_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one()

    async def count_by_user(self, db_session: AsyncSession, user_id: UUID) -> int:
        """Count messages the user sent or received (the OR cannot duplicate a row)."""
        stmt = (
            select(func.count())
            .select_from(ChatMessage)
            .where(or_(col(ChatMessage.from_user_id) == user_id, col(ChatMessage.to_user_id) == user_id))
        )
        return int((await db_session.execute(stmt)).scalar_one())

    async def reassign_user(
        self, db_session: AsyncSession, source_user_id: UUID, target_user_id: UUID, *, commit: bool = True
    ) -> int:
        """Move the source account to the target in both message directions."""
        from_source = col(ChatMessage.from_user_id) == source_user_id
        to_source = col(ChatMessage.to_user_id) == source_user_id
        result = await db_session.execute(
            update(ChatMessage)
            .where(or_(from_source, to_source))
            .values(
                from_user_id=case((from_source, target_user_id), else_=col(ChatMessage.from_user_id)),
                to_user_id=case((to_source, target_user_id), else_=col(ChatMessage.to_user_id)),
            )
            .execution_options(synchronize_session=False)
        )
        if commit:
            await db_session.commit()
        else:
            await db_session.flush()
        return cast("CursorResult", result).rowcount or 0


chat_message = CRUDChatMessage(ChatMessage)
