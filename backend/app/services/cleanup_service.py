from datetime import UTC, datetime, timedelta

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.crud.incident import incident_crud
from app.crud.notification import notification as notification_crud
from app.models.incident import IncidentStatus


class CleanupService:
    async def cleanup_old_incidents(
        self,
        db_session: AsyncSession,
        retention_days: int | None = None,
        batch_size: int | None = None,
    ) -> int:
        resolved_statuses = [IncidentStatus.RESOLVED, IncidentStatus.FAILED]
        retention = retention_days or settings.INCIDENT_RETENTION_DAYS
        batch = batch_size or settings.CLEANUP_BATCH_SIZE
        cutoff_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=retention)

        deleted_count = 0

        while True:
            incidents_to_delete = await incident_crud.get_resolved_before(
                db_session, resolved_statuses, cutoff_date, batch
            )

            if not incidents_to_delete:
                break

            for incident in incidents_to_delete:
                await db_session.delete(incident)
                deleted_count += 1

            await db_session.commit()

        return deleted_count

    async def cleanup_old_notifications(
        self,
        db_session: AsyncSession,
        retention_days: int | None = None,
        batch_size: int | None = None,
    ) -> int:
        retention = retention_days or settings.NOTIFICATION_RETENTION_DAYS
        batch = batch_size or settings.CLEANUP_BATCH_SIZE
        cutoff_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=retention)

        deleted_count = 0

        while True:
            notifications_to_delete = await notification_crud.get_older_than(db_session, cutoff_date, batch)

            if not notifications_to_delete:
                break

            for notification in notifications_to_delete:
                await db_session.delete(notification)
                deleted_count += 1

            await db_session.commit()

        return deleted_count


cleanup_service = CleanupService()
