from datetime import datetime
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.notification import Notification, NotificationCreate, NotificationUpdate


class CRUDNotification(CRUDBase[Notification, NotificationCreate, NotificationUpdate]):
    async def get_user_notifications(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications for a user"""
        from sqlalchemy import desc

        query = select(Notification).where(Notification.user_id == user_id).where(~Notification.is_dismissed)

        if unread_only:
            query = query.where(~Notification.is_read)

        query = query.order_by(desc(Notification.created_at)).offset(offset).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_unread_count(self, db: AsyncSession, user_id: UUID) -> int:
        """Count unread notifications"""
        query = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .where(~Notification.is_read)
            .where(~Notification.is_dismissed)
        )
        result = await db.execute(query)
        return len(list(result.scalars().all()))

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

    async def mark_all_as_read(self, db: AsyncSession, user_id: UUID) -> int:
        """Mark all notifications as read for a user"""
        query = select(Notification).where(Notification.user_id == user_id).where(~Notification.is_read)
        result = await db.execute(query)
        notifications = result.scalars().all()

        count = 0
        for notification in notifications:
            notification.is_read = True
            notification.read_at = datetime.utcnow()
            db.add(notification)
            count += 1

        await db.commit()
        return count

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
        result = await db_session.execute(query)
        return list(result.scalars().all())


notification = CRUDNotification(Notification)
