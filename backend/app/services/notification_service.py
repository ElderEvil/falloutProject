import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.notification import notification as notification_crud
from app.models.notification import NotificationCreate, NotificationPriority, NotificationType
from app.services.stream_manager import sse_manager
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and sending notifications."""

    @staticmethod
    async def _get_vault_prefix(db: AsyncSession, vault_id: UUID | None) -> str:
        """Get vault number prefix for notification messages."""
        if not vault_id:
            return ""

        from app.crud import vault as crud_vault

        vault = await crud_vault.get(db, vault_id)
        if vault and vault.number:
            return f"[Vault {vault.number}] "
        return ""

    @staticmethod
    async def create_and_send(
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
        commit: bool = True,
    ):
        """Create a notification and send it via WebSocket."""
        vault_prefix = await NotificationService._get_vault_prefix(db, vault_id)
        prefixed_message = f"{vault_prefix}{message}"

        notification = await notification_crud.create(
            db,
            obj_in=NotificationCreate(
                user_id=user_id,
                vault_id=vault_id,
                from_dweller_id=from_dweller_id,
                notification_type=notification_type,
                priority=priority,
                title=title,
                message=prefixed_message,
                meta_data=meta_data,
            ),
            commit=commit,
        )

        logger.info(
            f"Created notification {notification.id}: type={notification_type}, "
            f"priority={priority}, user={user_id}, vault={vault_id}"
        )

        payload = {
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
        }

        if commit:
            await NotificationService._deliver(user_id, payload)
        else:
            # Delivery deferred to the outer transaction: the caller must drain
            # via deliver_deferred_notifications() after its commit, or discard
            # the pendings on rollback (mirrors defer_reward_delivery).
            pending = db.info.setdefault("deferred_notification_deliveries", [])
            pending.append((user_id, payload))

        return notification

    @staticmethod
    async def _deliver(user_id: UUID, payload: dict[str, Any]) -> None:
        """Push one notification payload over WebSocket and SSE (best-effort, never raises)."""
        try:
            await manager.send_personal_message(payload, user_id=user_id)
        except Exception:
            logger.exception(f"Failed to send notification {payload['notification']['id']} to user {user_id}")
            # Best-effort delivery: persistence should succeed even if WS send fails.

        try:
            await sse_manager.publish(
                user_id,
                "notifications",
                payload,
            )
        except Exception:
            logger.exception(f"Failed to send SSE notification {payload['notification']['id']} to user {user_id}")
            # Best-effort delivery: persistence should succeed even if SSE send fails.

    @staticmethod
    def discard_deferred_notifications(db: AsyncSession) -> None:
        """Drop queued deliveries for a transaction that rolled back."""
        db.info.pop("deferred_notification_deliveries", None)

    @staticmethod
    async def deliver_deferred_notifications(db: AsyncSession) -> None:
        """Send notifications parked by create_and_send(commit=False) after the caller committed."""
        pending = db.info.pop("deferred_notification_deliveries", [])
        for user_id, payload in pending:
            await NotificationService._deliver(user_id, payload)

    @staticmethod
    async def notify_owner(
        db: AsyncSession,
        vault_id: UUID | None,
        *,
        sender: Callable[[UUID], Awaitable[Any]],
        context: str,
    ) -> None:
        """Best-effort: resolve ``vault_id``'s owner and run ``sender(user_id)``.

        No-ops when the vault is missing or unowned, and logs (never raises) on
        delivery failure so a broken notification cannot fail the gameplay
        action that triggered it.
        """
        if not vault_id:
            return
        from app.crud import vault as crud_vault

        try:
            vault = await crud_vault.get(db, vault_id)
            if not vault or not vault.user_id:
                return
            await sender(vault.user_id)
        except Exception:
            logger.exception("Failed to notify vault owner (%s)", context)

    # Convenience methods for common notification types

    @staticmethod
    async def notify_exploration_update(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        event_description: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user about exploration event."""
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
    async def notify_exploration_complete(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that exploration is complete."""
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
    async def notify_level_up(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        new_level: int,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that a dweller leveled up."""
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
    async def notify_training_complete(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        stat_name: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that training is complete."""
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
    async def notify_baby_born(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        mother_id: UUID,
        mother_name: str,
        baby_name: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that a baby was born."""
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
    async def notify_resource_low(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        resource_name: str,
        current_amount: int,
        max_amount: int,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that a resource is running low."""
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
    async def notify_combat_victory(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        enemy_name: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user about combat victory."""
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
        """Notify user that a new dweller arrived via radio."""
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

    @staticmethod
    async def notify_dweller_died(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        dweller_id: UUID,
        dweller_name: str,
        cause: str,
        meta_data: dict[str, Any] | None = None,
        commit: bool = True,
    ):
        """Notify user that a dweller has died."""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            from_dweller_id=dweller_id,
            notification_type=NotificationType.DWELLER_DIED,
            priority=NotificationPriority.URGENT,
            title="Dweller Lost",
            message=f"{dweller_name} has died. Cause: {cause}",
            meta_data=meta_data,
            commit=commit,
        )

    @staticmethod
    async def notify_quest_completed(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        quest_title: str,
        rewards: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that a quest has been completed."""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            notification_type=NotificationType.QUEST_COMPLETE,
            priority=NotificationPriority.HIGH,
            title="Quest Completed!",
            message=f"'{quest_title}' completed! Rewards: {rewards}",
            meta_data=meta_data,
        )

    @staticmethod
    async def notify_objective_completed(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        objective_challenge: str,
        reward: str,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user that an objective has been completed."""
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            notification_type=NotificationType.ACHIEVEMENT_UNLOCKED,
            priority=NotificationPriority.NORMAL,
            title="Objective Complete!",
            message=f"'{objective_challenge}' completed! Reward: {reward}",
            meta_data=meta_data,
        )

    @staticmethod
    async def notify_objective_progress(
        db: AsyncSession,
        user_id: UUID,
        vault_id: UUID,
        objective_challenge: str,
        progress: int,
        total: int,
        meta_data: dict[str, Any] | None = None,
    ):
        """Notify user about objective progress milestone (50% or 90%)."""
        percent = int((progress / total) * 100)
        return await NotificationService.create_and_send(
            db,
            user_id=user_id,
            vault_id=vault_id,
            notification_type=NotificationType.ACHIEVEMENT_UNLOCKED,
            priority=NotificationPriority.INFO,
            title=f"Objective {percent}% Complete",
            message=f"'{objective_challenge}': {progress}/{total} ({percent}%)",
            meta_data=meta_data,
        )


# Global service instance
notification_service = NotificationService()
