from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.notification import Notification, NotificationPriority, NotificationType
from app.models.room import Room
from app.models.team import Team, TeamMember
from app.models.user import User
from app.models.vault import Vault
from app.services.cleanup_service import cleanup_service


@pytest.mark.asyncio
async def test_cleanup_old_incidents(
    async_session: AsyncSession,
    room_with_dwellers: dict[str, object],
) -> None:
    room = cast("Room", room_with_dwellers["room"])

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
        read_retention_days=7,
        unread_retention_days=30,
        batch_size=100,
    )

    assert deleted_count == 1

    remaining = (await async_session.execute(select(Notification))).scalars().all()
    remaining_ids = {notification.id for notification in remaining}

    assert old_notification.id not in remaining_ids
    assert recent_notification.id in remaining_ids


def _notification(
    user: User, vault: Vault, *, created_days_ago: int, is_read: bool, is_dismissed: bool
) -> Notification:
    return Notification(
        user_id=user.id,
        vault_id=vault.id,
        notification_type=NotificationType.COMBAT_STARTED,
        priority=NotificationPriority.NORMAL,
        title="Retention fixture",
        message="retention",
        is_read=is_read,
        is_dismissed=is_dismissed,
        created_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=created_days_ago),
    )


@pytest.mark.asyncio
async def test_cleanup_notifications_respects_read_unread_and_dismissed_retention(
    async_session: AsyncSession,
    user_with_vault: tuple[User, Vault],
) -> None:
    """Read/dismissed rows use the short window; untouched unread rows use the long one."""
    user, vault = user_with_vault

    old_read = _notification(user, vault, created_days_ago=40, is_read=True, is_dismissed=False)
    old_dismissed_unread = _notification(user, vault, created_days_ago=40, is_read=False, is_dismissed=True)
    old_unread_kept = _notification(user, vault, created_days_ago=40, is_read=False, is_dismissed=False)
    old_unread_expired = _notification(user, vault, created_days_ago=100, is_read=False, is_dismissed=False)
    recent_read_kept = _notification(user, vault, created_days_ago=10, is_read=True, is_dismissed=False)
    recent_dismissed_kept = _notification(user, vault, created_days_ago=10, is_read=False, is_dismissed=True)
    async_session.add_all(
        [
            old_read,
            old_dismissed_unread,
            old_unread_kept,
            old_unread_expired,
            recent_read_kept,
            recent_dismissed_kept,
        ]
    )
    await async_session.commit()

    deleted_count = await cleanup_service.cleanup_old_notifications(
        async_session,
        read_retention_days=30,
        unread_retention_days=90,
        batch_size=100,
    )

    assert deleted_count == 3
    remaining_ids = {row.id for row in (await async_session.execute(select(Notification))).scalars().all()}
    assert remaining_ids == {old_unread_kept.id, recent_read_kept.id, recent_dismissed_kept.id}


@pytest.mark.asyncio
async def test_cleanup_notifications_batches_expired_rows(
    async_session: AsyncSession,
    user_with_vault: tuple[User, Vault],
) -> None:
    """The CRUD limit bounds each pass and the service loops until the backlog is gone."""
    user, vault = user_with_vault
    expired = [_notification(user, vault, created_days_ago=40, is_read=True, is_dismissed=False) for _ in range(5)]
    async_session.add_all(expired)
    await async_session.commit()

    now = datetime.now(UTC).replace(tzinfo=None)
    first_batch = await crud.notification.get_expired_batch(
        async_session,
        read_cutoff=now - timedelta(days=30),
        unread_cutoff=now - timedelta(days=90),
        limit=2,
    )
    assert len(first_batch) == 2

    deleted_count = await cleanup_service.cleanup_old_notifications(
        async_session,
        read_retention_days=30,
        unread_retention_days=90,
        batch_size=2,
    )

    assert deleted_count == 5
    assert (await async_session.execute(select(Notification))).scalars().all() == []


@pytest.mark.asyncio
async def test_cleanup_prunes_the_incidents_responder_team(
    async_session: AsyncSession,
    room_with_dwellers: dict[str, object],
) -> None:
    """Deleting an incident cascades to its roster, so incident teams cannot accumulate."""
    room = cast("Room", room_with_dwellers["room"])
    dwellers = cast("list", room_with_dwellers["dwellers"])

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.FIRE,
        difficulty=3,
    )
    await crud.team_crud.add_incident_team_members(
        async_session, incident.id, room.vault_id, [dweller.id for dweller in dwellers]
    )
    incident.resolve(success=True)
    incident.end_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10)
    async_session.add(incident)
    await async_session.commit()

    team = await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id)
    assert team is not None
    team_id = team.id
    member_ids = {member.id for member in team.members}
    assert member_ids

    assert await cleanup_service.cleanup_old_incidents(async_session, retention_days=7, batch_size=100) == 1

    assert (await async_session.execute(select(Team).where(Team.id == team_id))).scalars().all() == []
    remaining_members = (
        (await async_session.execute(select(TeamMember).where(col(TeamMember.id).in_(member_ids)))).scalars().all()
    )
    assert remaining_members == []
