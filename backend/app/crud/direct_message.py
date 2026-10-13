"""CRUD operations for account-owned direct messages (B1)."""

from collections.abc import Sequence
from datetime import datetime
from typing import NamedTuple

from pydantic import UUID4
from sqlalchemy import case, func
from sqlalchemy import select as sa_select
from sqlmodel import and_, col, or_, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.direct_message import DirectMessage


class ConversationSummaryRow(NamedTuple):
    """One conversation head: newest message plus its unread/pending aggregates."""

    last_message: DirectMessage
    unread_count: int
    has_pending_request: bool


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

    async def get_last_between(
        self, db_session: AsyncSession, *, sender: UUID4, recipient: UUID4
    ) -> DirectMessage | None:
        """Newest message in one direction; lets a lost create race return its row."""
        query = (
            select(DirectMessage)
            .where(
                DirectMessage.sender_user_id == sender,
                DirectMessage.recipient_user_id == recipient,
            )
            .order_by(col(DirectMessage.created_at).desc())
            .limit(1)
        )
        result = await db_session.execute(query)
        return result.scalars().first()

    async def list_conversations_for_user(
        self, db_session: AsyncSession, user_id: UUID4, *, limit: int = 50
    ) -> Sequence[ConversationSummaryRow]:
        """Up to ``limit`` most-recent conversations, aggregated in the database.

        Groups by counterpart and keeps only the newest message per counterpart,
        with that counterpart's unread count and open-request flag, so a user's
        full history is never loaded into Python.
        """
        counterpart = case(
            (col(DirectMessage.sender_user_id) == user_id, col(DirectMessage.recipient_user_id)),
            else_=col(DirectMessage.sender_user_id),
        )
        incoming = col(DirectMessage.recipient_user_id) == user_id
        ranked = (
            sa_select(
                col(DirectMessage.id).label("message_id"),
                col(DirectMessage.created_at).label("created_at"),
                counterpart.label("counterpart"),
                func.sum(case((incoming & col(DirectMessage.read_at).is_(None), 1), else_=0))
                .over(partition_by=counterpart)
                .label("unread_count"),
                func.max(case((incoming & col(DirectMessage.is_request).is_(True), 1), else_=0))
                .over(partition_by=counterpart)
                .label("has_pending_request"),
                func.row_number()
                .over(partition_by=counterpart, order_by=col(DirectMessage.created_at).desc())
                .label("rn"),
            )
            .where(or_(DirectMessage.sender_user_id == user_id, DirectMessage.recipient_user_id == user_id))
            .subquery()
        )
        heads = (
            await db_session.execute(
                select(ranked.c.message_id, ranked.c.unread_count, ranked.c.has_pending_request)
                .where(ranked.c.rn == 1)
                .order_by(ranked.c.created_at.desc())
                .limit(limit)
            )
        ).all()
        if not heads:
            return []
        message_ids = [row.message_id for row in heads]
        messages = (
            (await db_session.execute(select(DirectMessage).where(col(DirectMessage.id).in_(message_ids))))
            .scalars()
            .all()
        )
        by_id = {message.id: message for message in messages}
        return [
            ConversationSummaryRow(by_id[row.message_id], int(row.unread_count), bool(row.has_pending_request))
            for row in heads
            if row.message_id in by_id
        ]

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

    async def mark_thread_read(
        self, db_session: AsyncSession, *, recipient: UUID4, message_ids: Sequence[UUID4]
    ) -> None:
        """Mark only the given incoming messages as read (never the whole thread)."""
        if not message_ids:
            return
        query = select(DirectMessage).where(
            DirectMessage.recipient_user_id == recipient,
            col(DirectMessage.id).in_(list(message_ids)),
            col(DirectMessage.read_at).is_(None),
        )
        result = await db_session.execute(query)
        now = datetime.utcnow()
        for message in result.scalars().all():
            message.read_at = now
            db_session.add(message)
        await db_session.flush()


direct_message = CRUDDirectMessage(DirectMessage)
