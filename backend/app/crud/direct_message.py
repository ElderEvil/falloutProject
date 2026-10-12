"""CRUD operations for account-owned direct messages (B1)."""

from collections.abc import Sequence
from datetime import datetime

from pydantic import UUID4
from sqlmodel import and_, col, or_, select, update
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

        Open requests are *deleted* on decline and block, and *cleared* (``is_request`` set
        false) when the pair becomes connected, so a surviving flagged row means unanswered.
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

    async def clear_requests(self, db_session: AsyncSession, *, user_a: UUID4, user_b: UUID4) -> None:
        """Retire open requests in both directions once a pair is connected (accept path).

        Keeps the request messages as ordinary history but drops their flagged
        state, so a pair that is later revoked or blocked-then-unblocked is never
        left with a phantom pending request.
        """
        query = (
            update(DirectMessage)
            .where(
                col(DirectMessage.is_request).is_(True),
                or_(
                    and_(
                        DirectMessage.sender_user_id == user_a,
                        DirectMessage.recipient_user_id == user_b,
                    ),
                    and_(
                        DirectMessage.sender_user_id == user_b,
                        DirectMessage.recipient_user_id == user_a,
                    ),
                ),
            )
            .values(is_request=False)
        )
        await db_session.execute(query)
        await db_session.flush()

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
