import pytest
from sqlmodel import select

from app import crud
from app.models.notification import Notification, NotificationType
from app.schemas.dweller import DwellerCreate
from app.services.notification_service import NotificationService
from app.tests.factory.dwellers import create_random_common_dweller


@pytest.mark.asyncio
async def test_room_unlock_summary_at_population_threshold(async_session, vault):
    while await crud.dweller.count_alive_in_vault(async_session, vault.id) < 15:
        await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(**create_random_common_dweller(), vault_id=vault.id),
        )
    await async_session.commit()

    await NotificationService.notify_room_unlocks(async_session, vault.user_id, vault.id)
    await async_session.commit()

    rows = (
        (
            await async_session.execute(
                select(Notification).where(Notification.notification_type == NotificationType.ROOM_UNLOCKED)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert "Response Station" in rows[0].message
