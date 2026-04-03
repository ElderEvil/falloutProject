from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.notification import Notification, NotificationPriority, NotificationType
from app.models.room import Room
from app.models.user import User
from app.models.vault import Vault
from app.services.cleanup_service import cleanup_service


@pytest.mark.asyncio
async def test_cleanup_old_incidents(
    async_session: AsyncSession,
    room_with_dwellers: dict[str, object],
) -> None:
    room = cast(Room, room_with_dwellers["room"])

    old_incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=3,
    )
    old_incident.resolve(success=True)
    old_incident.end_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10)
    async_session.add(old_incident)

    recent_incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.RAIDER_ATTACK,
        difficulty=4,
    )
    recent_incident.resolve(success=False)
    recent_incident.end_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    async_session.add(recent_incident)

    active_incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.RADROACH_INFESTATION,
        difficulty=2,
    )
    active_incident.status = IncidentStatus.ACTIVE
    async_session.add(active_incident)

    await async_session.commit()

    deleted_count = await cleanup_service.cleanup_old_incidents(
        async_session,
        retention_days=7,
        batch_size=100,
    )

    assert deleted_count == 1

    remaining = (await async_session.execute(select(Incident))).scalars().all()
    remaining_ids = {incident.id for incident in remaining}

    assert old_incident.id not in remaining_ids
    assert recent_incident.id in remaining_ids
    assert active_incident.id in remaining_ids


@pytest.mark.asyncio
async def test_cleanup_old_notifications(
    async_session: AsyncSession,
    user_with_vault: tuple[User, Vault],
) -> None:
    user, vault = user_with_vault

    old_notification = Notification(
        user_id=user.id,
        vault_id=vault.id,
        notification_type=NotificationType.COMBAT_STARTED,
        priority=NotificationPriority.NORMAL,
        title="Old Notification",
        message="This should be deleted",
        is_read=True,
        is_dismissed=True,
        created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=12),
    )

    recent_notification = Notification(
        user_id=user.id,
        vault_id=vault.id,
        notification_type=NotificationType.COMBAT_STARTED,
        priority=NotificationPriority.NORMAL,
        title="Recent Notification",
        message="This should stay",
        is_read=False,
        is_dismissed=False,
        created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
    )

    async_session.add(old_notification)
    async_session.add(recent_notification)
    await async_session.commit()

    deleted_count = await cleanup_service.cleanup_old_notifications(
        async_session,
        retention_days=7,
        batch_size=100,
    )

    assert deleted_count == 1

    remaining = (await async_session.execute(select(Notification))).scalars().all()
    remaining_ids = {notification.id for notification in remaining}

    assert old_notification.id not in remaining_ids
    assert recent_notification.id in remaining_ids
