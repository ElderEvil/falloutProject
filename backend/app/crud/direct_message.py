"""CRUD operations for account-owned direct messages (B1)."""

from collections.abc import Sequence
from datetime import datetime

from pydantic import UUID4
from sqlmodel import and_, col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.direct_message import DirectMessage


class CRUDDirectMessage(CRUDBase[DirectMessage, None, None]):
    async def create_message(
        self,
        db_session: AsyncSession,
        *,
        sender_user_id: UUID4,
        recipient_user_id: UUID4,
        body: str,
        is_request: bool = False,
    ) -> DirectMessage:
        """Stage a message; the caller owns the transaction commit."""
        message = DirectMessage(
            sender_user_id=sender_user_id,
            recipient_user_id=recipient_user_id,
            body=body,
            is_request=is_request,
        )
        db_session.add(message)
        await db_session.flush()
        await db_session.refresh(message)
        return message

    async def get_thread(
        self,
        db_session: AsyncSession,
        *,
        user_a: UUID4,
        user_b: UUID4,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[DirectMessage]:
        """The chronological thread between two users, oldest first."""
        query = (
            select(DirectMessage)
            .where(
                or_(
                    and_(DirectMessage.sender_user_id == user_a, DirectMessage.recipient_user_id == user_b),
                    and_(DirectMessage.sender_user_id == user_b, DirectMessage.recipient_user_id == user_a),
                )
            )
            .order_by(col(DirectMessage.created_at).asc())
            .offset(offset)
            .limit(limit)
        )
        result = await db_session.execute(query)
        return result.scalars().all()

    async def has_open_request(self, db_session: AsyncSession, *, sender: UUID4, recipient: UUID4) -> bool:
        """True while the sender has a request the recipient has not answered.

        Requests are deleted on decline/block and the pair becomes connected on
        accept, so any existing is_request row for an unanswered pair is open.
        """
        query = (
            select(DirectMessage.id)
            .where(
                DirectMessage.sender_user_id == sender,
                DirectMessage.recipient_user_id == recipient,
                col(DirectMessage.is_request).is_(True),
            )
            .limit(1)
        )
        result = await db_session.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_for_user(self, db_session: AsyncSession, user_id: UUID4) -> Sequence[DirectMessage]:
        """Every message the user sent or received, oldest first."""
        query = (
            select(DirectMessage)
            .where(or_(DirectMessage.sender_user_id == user_id, DirectMessage.recipient_user_id == user_id))
            .order_by(col(DirectMessage.created_at).asc())
        )
        result = await db_session.execute(query)
        return result.scalars().all()

    async def delete_requests_from(self, db_session: AsyncSession, *, sender: UUID4, recipient: UUID4) -> int:
        """Discard open requests (decline path); returns how many were removed."""
        query = select(DirectMessage).where(
            DirectMessage.sender_user_id == sender,
            DirectMessage.recipient_user_id == recipient,
            col(DirectMessage.is_request).is_(True),
        )
        result = await db_session.execute(query)
        messages = result.scalars().all()
        for message in messages:
            await db_session.delete(message)
        await db_session.flush()
        return len(messages)

    async def mark_thread_read(self, db_session: AsyncSession, *, recipient: UUID4, sender: UUID4) -> None:
        """Mark incoming messages in a thread as read (recipient side only)."""
        query = select(DirectMessage).where(
            DirectMessage.recipient_user_id == recipient,
            DirectMessage.sender_user_id == sender,
            col(DirectMessage.read_at).is_(None),
        )
        result = await db_session.execute(query)
        now = datetime.utcnow()
        for message in result.scalars().all():
            message.read_at = now
            db_session.add(message)
        await db_session.flush()


direct_message = CRUDDirectMessage(DirectMessage)
