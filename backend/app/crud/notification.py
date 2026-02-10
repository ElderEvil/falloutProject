from datetime import datetime
from uuid import UUID

from sqlalchemy import delete
from sqlmodel import select
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
        query = select(Notification).where(Notification.user_id == user_id).where(Notification.is_dismissed == False)

        if unread_only:
            query = query.where(Notification.is_read == False)

        query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_unread_count(self, db: AsyncSession, user_id: UUID) -> int:
        """Count unread notifications"""
        query = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.is_read == False)
            .where(Notification.is_dismissed == False)
        )
        result = await db.execute(query)
        return len(list(result.scalars().all()))

    async def delete_by_vault(self, db: AsyncSession, vault_id: UUID) -> int:
        """Delete all notifications for a vault (hard delete)"""
        query = delete(Notification).where(Notification.vault_id == vault_id)
        result = await db.execute(query)
        await db.commit()
        return result.rowcount

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
        query = select(Notification).where(Notification.user_id == user_id).where(Notification.is_read == False)
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


notification = CRUDNotification(Notification)
