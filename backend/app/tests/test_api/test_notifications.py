"""API regression tests for the notification authorization fix (AUDIT.md P0).

The public ``POST /notifications`` route accepted a client-supplied
``NotificationCreate`` (including ``user_id``) behind only
``CurrentActiveUser``, so any signed-in player could persist notifications for
another user. The route is removed: server-side callers create notifications
exclusively through ``NotificationService.create_and_send()``. These tests pin
the forbidden paths (regular user rejected, no recipient selection) and the
permitted paths (read endpoints unchanged, service path still works).
"""

from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.crud.notification import notification as notification_crud
from app.models.notification import NotificationCreate, NotificationType
from app.schemas.user import UserCreate
from app.services.notification_service import NotificationService


def _notification_payload(user_id) -> dict:
    """A body shaped like the old NotificationCreate the route used to accept."""
    return {
        "user_id": str(user_id),
        "notification_type": NotificationType.LEVEL_UP.value,
        "priority": "normal",
        "title": "Test notification",
        "message": "test message",
    }


async def _normal_user(async_session: AsyncSession):
    """The user behind the normal_user_token_headers fixture."""
    return await crud.user.get_by_email(async_session, email=settings.EMAIL_TEST_USER)


async def test_regular_user_cannot_create_notification(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """A regular authenticated user can no longer POST a notification."""
    user = await _normal_user(async_session)

    response = await async_client.post(
        "/notifications/",
        headers=normal_user_token_headers,
        json=_notification_payload(user.id),
    )

    assert response.status_code == 405
    rows = await notification_crud.get_user_notifications(async_session, user_id=user.id)
    assert rows == []


async def test_cannot_create_notification_for_another_user(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Selecting another user as the recipient is impossible: the route is gone."""
    target = await crud.user.create(
        async_session,
        obj_in=UserCreate(username="target_user", email="target@example.com", password="testpass123"),
    )

    response = await async_client.post(
        "/notifications/",
        headers=normal_user_token_headers,
        json=_notification_payload(target.id),
    )

    assert response.status_code == 405
    rows = await notification_crud.get_user_notifications(async_session, user_id=target.id)
    assert rows == []


async def test_get_notifications_still_works(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """GET /notifications/ remains the permitted read path for the current user."""
    user = await _normal_user(async_session)
    await notification_crud.create(
        async_session,
        obj_in=NotificationCreate(
            user_id=user.id,
            notification_type=NotificationType.LEVEL_UP,
            title="Level Up",
            message="You reached level 2!",
        ),
    )

    response = await async_client.get("/notifications/", headers=normal_user_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["user_id"] == str(user.id)


async def test_unread_count_still_works(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """GET /notifications/unread-count remains permitted."""
    user = await _normal_user(async_session)
    await notification_crud.create(
        async_session,
        obj_in=NotificationCreate(
            user_id=user.id,
            notification_type=NotificationType.LEVEL_UP,
            title="Level Up",
            message="You reached level 2!",
        ),
    )

    response = await async_client.get("/notifications/unread-count", headers=normal_user_token_headers)

    assert response.status_code == 200
    assert response.json()["count"] == 1


async def test_mark_as_read_still_works(
    async_client: AsyncClient,
    async_session: AsyncSession,
    normal_user_token_headers: dict[str, str],
) -> None:
    """PATCH /notifications/{id}/read remains permitted for the owner."""
    user = await _normal_user(async_session)
    notification = await notification_crud.create(
        async_session,
        obj_in=NotificationCreate(
            user_id=user.id,
            notification_type=NotificationType.LEVEL_UP,
            title="Level Up",
            message="You reached level 2!",
        ),
    )

    response = await async_client.patch(
        f"/notifications/{notification.id}/read",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["is_read"] is True


async def test_create_and_send_is_the_permitted_path(async_session: AsyncSession) -> None:
    """Server-side callers keep working: create_and_send persists for the target user."""
    user = await crud.user.create(
        async_session,
        obj_in=UserCreate(username="service_target", email="service_target@example.com", password="testpass123"),
    )

    with (
        patch("app.services.notification_service.manager") as mock_ws,
        patch("app.services.notification_service.sse_manager") as mock_sse,
    ):
        notification = await NotificationService.create_and_send(
            async_session,
            user_id=user.id,
            notification_type=NotificationType.LEVEL_UP,
            title="Level Up",
            message="You reached level 2!",
        )

    assert notification.user_id == user.id
    mock_ws.send_personal_message.assert_called_once()
    mock_sse.publish.assert_called_once()

    rows = await notification_crud.get_user_notifications(async_session, user_id=user.id)
    assert any(row.id == notification.id for row in rows)
