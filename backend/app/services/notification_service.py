from typing import Any
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.notification import notification as notification_crud
from app.models.notification import NotificationCreate, NotificationPriority, NotificationType
from app.services.websocket_manager import manager


class NotificationService:
    """Service for creating and sending notifications"""

    @staticmethod
    async def create_and_send(  # noqa: PLR0913
        db: AsyncSession,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        *,
        vault_id: UUID | None = None,
        from_dweller_id: UUID | None = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        meta_data: dict[str, Any] | None = None,
    ):
        """Create a notification and send it via WebSocket"""
        # Create notification in database
        notification = await notification_crud.create(
            db,
            obj_in=NotificationCreate(
                user_id=user_id,
                vault_id=vault_id,
                from_dweller_id=from_dweller_id,
                notification_type=notification_type,
                priority=priority,
                title=title,
                message=message,
                meta_data=meta_data,
            ),
        )

        # Send via WebSocket
        await manager.send_personal_message(
            {
                "type": "notification",
                "notification": {
                    "id": str(notification.id),
                    "notification_type": notification.notification_type,
                    "priority": notification.priority,
                    "title": notification.title,
                    "message": notification.message,
                    "meta_data": notification.meta_data,
                    "created_at": notification.created_at.isoformat(),
                },
            },
            user_id=user_id,
        )

        return notification

    # Convenience methods for common notification types

    @staticmethod
    async def notify_exploration_update(  # noqa: PLR0913
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        event_description: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user about exploration event"""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            from_dweller_id=dweller_id,
            notification_type=NotificationType.EXPLORATION_UPDATE,
            priority=NotificationPriority.NORMAL,
            title=f"{dweller_name} - Exploration Update",
            message=event_description,
            meta_data=meta_data,
        )

    @staticmethod
    async def notify_exploration_complete(  # noqa: PLR0913
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that exploration is complete"""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            from_dweller_id=dweller_id,
            notification_type=NotificationType.EXPLORATION_COMPLETE,
            priority=NotificationPriority.NORMAL,
            title=f"{dweller_name} Returned",
            message=f"{dweller_name} has returned from the wasteland!",
            meta_data=meta_data,
        )

    @staticmethod
    async def notify_level_up(  # noqa: PLR0913
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        new_level: int,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that a dweller leveled up"""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            from_dweller_id=dweller_id,
            notification_type=NotificationType.LEVEL_UP,
            priority=NotificationPriority.HIGH,
            title=f"{dweller_name} Leveled Up!",
            message=f"{dweller_name} reached level {new_level}!",
            meta_data=meta_data,
        )

    @staticmethod
    async def notify_training_complete(  # noqa: PLR0913
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        stat_name: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that training is complete"""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            from_dweller_id=dweller_id,
            notification_type=NotificationType.TRAINING_COMPLETE,
            priority=NotificationPriority.NORMAL,
            title=f"{dweller_name} - Training Complete",
            message=f"{dweller_name} finished training {stat_name}!",
            meta_data=meta_data,
        )

    @staticmethod
    async def notify_baby_born(  # noqa: PLR0913
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        mother_id: UUID,
        mother_name: str,
        baby_name: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that a baby was born"""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            from_dweller_id=mother_id,
            notification_type=NotificationType.BABY_BORN,
            priority=NotificationPriority.HIGH,
            title="New Arrival!",
            message=f"{mother_name} gave birth to {baby_name}!",
            meta_data=meta_data,
        )

    @staticmethod
    async def notify_resource_low(  # noqa: PLR0913
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        resource_name: str,
        current_amount: int,
        max_amount: int,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that a resource is running low"""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            notification_type=NotificationType.RESOURCE_LOW,
            priority=NotificationPriority.HIGH,
            title=f"Low {resource_name}!",
            message=f"{resource_name} is running low: {current_amount}/{max_amount}",
            meta_data=meta_data,
        )

    @staticmethod
    async def notify_combat_victory(  # noqa: PLR0913
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        enemy_name: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user about combat victory"""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            from_dweller_id=dweller_id,
            notification_type=NotificationType.COMBAT_VICTORY,
            priority=NotificationPriority.NORMAL,
            title=f"{dweller_name} - Victory!",
            message=f"{dweller_name} defeated {enemy_name}!",
            meta_data=meta_data,
        )

    @staticmethod
    async def notify_radio_new_dweller(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_name: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that a new dweller arrived via radio"""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            notification_type=NotificationType.RADIO_NEW_DWELLER,
            priority=NotificationPriority.HIGH,
            title="New Dweller Arrived!",
            message=f"{dweller_name} heard your radio broadcast and joined the vault!",
            meta_data=meta_data,
        )


# Global service instance
notification_service = NotificationService()
