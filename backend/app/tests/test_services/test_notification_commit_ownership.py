"""Commit-ownership characterization for notification read/dismiss flows.

CRUD mutates + flushes only; ``NotificationService`` owns the transaction
boundary. These tests pin that split so a future refactor cannot silently move
the commit back into the persistence layer (or drop it entirely).
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.notification import notification as notification_crud
from app.services.notification_service import notification_service


@pytest.mark.asyncio
class TestNotificationCommitOwnership:
    async def test_mark_read_commits_when_changed(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        notification = MagicMock()
        with patch(
            "app.services.notification_service.notification_crud.mark_as_read",
            new=AsyncMock(return_value=notification),
        ):
            result = await notification_service.mark_read(db, notification_id=uuid4(), user_id=uuid4())

        assert result is notification
        db.commit.assert_awaited_once()

    async def test_mark_read_skips_commit_when_not_found(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        with patch(
            "app.services.notification_service.notification_crud.mark_as_read",
            new=AsyncMock(return_value=None),
        ):
            result = await notification_service.mark_read(db, notification_id=uuid4(), user_id=uuid4())

        assert result is None
        db.commit.assert_not_awaited()

    async def test_mark_all_read_commits_only_when_rows_changed(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        with patch(
            "app.services.notification_service.notification_crud.mark_all_as_read",
            new=AsyncMock(return_value=3),
        ):
            assert await notification_service.mark_all_read(db, user_id=uuid4()) == 3
        db.commit.assert_awaited_once()

        db.reset_mock()
        with patch(
            "app.services.notification_service.notification_crud.mark_all_as_read",
            new=AsyncMock(return_value=0),
        ):
            assert await notification_service.mark_all_read(db, user_id=uuid4()) == 0
        db.commit.assert_not_awaited()

    async def test_dismiss_commits_when_changed(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        notification = MagicMock()
        with patch(
            "app.services.notification_service.notification_crud.dismiss",
            new=AsyncMock(return_value=notification),
        ):
            result = await notification_service.dismiss(db, notification_id=uuid4(), user_id=uuid4())

        assert result is notification
        db.commit.assert_awaited_once()

    async def test_crud_mark_as_read_flushes_without_committing(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        owner = uuid4()
        notification = MagicMock(user_id=owner)
        with patch.object(notification_crud, "get", new=AsyncMock(return_value=notification)):
            result = await notification_crud.mark_as_read(db, notification_id=uuid4(), user_id=owner)

        assert result is notification
        assert notification.is_read is True
        db.flush.assert_awaited_once()
        db.commit.assert_not_awaited()

    async def test_crud_dismiss_flushes_without_committing(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        owner = uuid4()
        notification = MagicMock(user_id=owner)
        with patch.object(notification_crud, "get", new=AsyncMock(return_value=notification)):
            result = await notification_crud.dismiss(db, notification_id=uuid4(), user_id=owner)

        assert result is notification
        assert notification.is_dismissed is True
        db.flush.assert_awaited_once()
        db.commit.assert_not_awaited()

    async def test_crud_mark_as_read_ignores_other_users(self) -> None:
        db = AsyncMock(spec=AsyncSession)
        notification = MagicMock(user_id=uuid4())
        with patch.object(notification_crud, "get", new=AsyncMock(return_value=notification)):
            result = await notification_crud.mark_as_read(db, notification_id=uuid4(), user_id=uuid4())

        assert result is None
        db.flush.assert_not_awaited()
        db.commit.assert_not_awaited()
