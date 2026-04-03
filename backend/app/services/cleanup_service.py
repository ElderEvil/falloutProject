from datetime import UTC, datetime, timedelta

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.incident import Incident, IncidentStatus
from app.models.notification import Notification


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
            query = (
                select(Incident)
                .where(col(Incident.status).in_(resolved_statuses))
                .where(col(Incident.end_time).is_not(None))
                .where(col(Incident.end_time) <= cutoff_date)
                .limit(batch)
            )
            result = await db_session.execute(query)
            incidents_to_delete = list(result.scalars().all())

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
            query = select(Notification).where(col(Notification.created_at) <= cutoff_date).limit(batch)
            result = await db_session.execute(query)
            notifications_to_delete = list(result.scalars().all())

            if not notifications_to_delete:
                break

            for notification in notifications_to_delete:
                await db_session.delete(notification)
                deleted_count += 1

            await db_session.commit()

        return deleted_count


cleanup_service = CleanupService()
