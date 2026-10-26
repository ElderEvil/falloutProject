from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, func, update
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.notification import Notification, NotificationCreate, NotificationUpdate


class CRUDNotification(CRUDBase[Notification, NotificationCreate, NotificationUpdate]):
    async def create(
        self, db_session: AsyncSession, obj_in: NotificationCreate, *, commit: bool = True
    ) -> Notification:
        """Create a notification row; commit deferred with the caller when requested.

        The WebSocket/SSE delivery in the service layer always runs after the
        row exists (best-effort), so callers deferring the commit also defer
        delivery timing.
        """
        db_obj = self.model.model_validate(obj_in)
        db_session.add(db_obj)
        if commit:
            await db_session.commit()
        else:
            await db_session.flush()
        await db_session.refresh(db_obj)
        return db_obj

    async def get_user_notifications(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        unread_only: bool = False,
        vault_id: UUID | None = None,
        is_read: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications for a user"""
        from sqlalchemy import desc

        query = select(Notification).where(Notification.user_id == user_id).where(~col(Notification.is_dismissed))

        if vault_id is not None:
            query = query.where(Notification.vault_id == vault_id)
        if is_read is not None:
            query = query.where(col(Notification.is_read) == is_read)

        if unread_only:
            query = query.where(~col(Notification.is_read))

        query = (
            query.order_by(desc(col(Notification.created_at)), desc(col(Notification.id))).offset(offset).limit(limit)
        )
        result = await db.execute(query)  # ty: ignore[deprecated] -- Compatible with tick/test SQLAlchemy sessions.
        return list(result.scalars().all())

    async def count_by_user(self, db_session: AsyncSession, user_id: UUID) -> int:
        """Count every notification owned by a user, including dismissed ones."""
        result = await db_session.execute(
            select(func.count()).select_from(Notification).where(col(Notification.user_id) == user_id)
        )
        return int(result.scalar_one())

    async def reassign_user(
        self, db_session: AsyncSession, source_user_id: UUID, target_user_id: UUID, *, commit: bool = True
    ) -> int:
        """Move every notification from the source account to the target."""
        result = await db_session.execute(
            update(Notification)
            .where(col(Notification.user_id) == source_user_id)
            .values(user_id=target_user_id)
            .execution_options(synchronize_session=False)
        )
        if commit:
            await db_session.commit()
        else:
            await db_session.flush()
        return cast("CursorResult", result).rowcount or 0

    async def get_unread_count(self, db: AsyncSession, user_id: UUID) -> int:
        """Count visible unread notifications without loading the rows."""
        query = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id)
            .where(~col(Notification.is_read))
            .where(~col(Notification.is_dismissed))
        )
        result = await db.execute(query)  # ty: ignore[deprecated] -- Compatible with tick/test SQLAlchemy sessions.
        return int(result.scalar_one())

    async def mark_as_read(self, db: AsyncSession, notification_id: UUID, user_id: UUID) -> Notification | None:
        """Mark notification as read"""
        notification = await self.get(db, id=notification_id)
        if notification and notification.user_id == user_id:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
            return notification
        return None

    async def mark_all_as_read(self, db: AsyncSession, user_id: UUID, *, vault_id: UUID | None = None) -> int:
        """Mark visible unread notifications read, optionally within a single vault."""
        query = (
            update(Notification)
            .where(col(Notification.user_id) == user_id)
            .where(~col(Notification.is_read))
            .where(~col(Notification.is_dismissed))
            .values(is_read=True, read_at=datetime.utcnow())
        )
        if vault_id is not None:
            query = query.where(col(Notification.vault_id) == vault_id)
        result = await db.execute(query)  # ty: ignore[deprecated] -- ORM UPDATE requires execute, not exec.
        await db.commit()
        return cast("CursorResult", result).rowcount or 0

    async def dismiss(self, db: AsyncSession, notification_id: UUID, user_id: UUID) -> Notification | None:
        """Dismiss (soft delete) a notification"""
        notification = await self.get(db, id=notification_id)
        if notification and notification.user_id == user_id:
            notification.is_dismissed = True
            db.add(notification)
            await db.commit()
            await db.refresh(notification)
            return notification
        return None

    async def get_older_than(self, db_session: AsyncSession, cutoff: datetime, limit: int) -> list[Notification]:
        """Notifications created at or before the cutoff, oldest batch first."""
        query = (
            select(Notification)
            .where(col(Notification.created_at) <= cutoff)
            .order_by(col(Notification.created_at).asc())
            .limit(limit)
        )
        result = await db_session.execute(query)  # ty: ignore[deprecated] -- Compatible with SQLAlchemy sessions.
        return list(result.scalars().all())

    async def latest_for_vault(self, db: AsyncSession, vault_id: UUID, notification_type) -> datetime | None:
        result = await db.execute(  # ty: ignore[deprecated] -- Compatible with SQLAlchemy sessions.
            select(func.max(Notification.created_at)).where(
                Notification.vault_id == vault_id, Notification.notification_type == notification_type
            )
        )
        return result.scalar_one_or_none()


notification = CRUDNotification(Notification)
