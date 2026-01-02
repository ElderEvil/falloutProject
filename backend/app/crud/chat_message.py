from uuid import UUID

from sqlmodel import or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.chat_message import ChatMessage, ChatMessageCreate, ChatMessageRead


class CRUDChatMessage(CRUDBase[ChatMessage, ChatMessageCreate, ChatMessageRead]):
    async def get_conversation(  # noqa: PLR0913
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
                .order_by(ChatMessage.created_at.asc())
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
                .order_by(ChatMessage.created_at.asc())
                .offset(offset)
                .limit(limit)
            )
        else:
            raise ValueError("Either provide user_id and dweller_id, or dweller_to_dweller tuple")  # noqa: EM101, TRY003

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_recent_conversations(self, db: AsyncSession, *, vault_id: UUID, limit: int = 10) -> list[ChatMessage]:
        """Get recent chat messages for a vault"""
        query = (
            select(ChatMessage)
            .where(ChatMessage.vault_id == vault_id)
            .order_by(ChatMessage.created_at.desc())
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
        """Create a new chat message"""
        return await self.create(db, obj_in=obj_in)


chat_message = CRUDChatMessage(ChatMessage)
