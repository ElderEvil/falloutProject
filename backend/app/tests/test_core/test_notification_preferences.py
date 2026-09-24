from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.notification_preferences import (
    NOTIFICATION_CATEGORY_BY_TYPE,
    NotificationCategory,
    should_deliver_notification,
    validate_notification_preferences,
)
from app.crud.user_profile import profile_crud
from app.models.notification import Notification, NotificationType
from app.services.notification_service import NotificationService


def test_every_notification_type_has_a_policy() -> None:
    assert set(NOTIFICATION_CATEGORY_BY_TYPE) == set(NotificationType)


def test_muted_routine_category_is_not_delivered() -> None:
    preferences = {"notifications": {"version": 1, "disabled_categories": ["advancement"]}}
    assert not should_deliver_notification(preferences, NotificationType.LEVEL_UP)
    assert should_deliver_notification(preferences, NotificationType.DWELLER_DIED)


def test_unknown_future_type_defaults_to_enabled() -> None:
    preferences = {"notifications": {"version": 1, "disabled_categories": ["advancement"]}}
    assert should_deliver_notification(preferences, "future_type")  # type: ignore[arg-type]


def test_protected_categories_cannot_be_disabled() -> None:
    with pytest.raises(ValueError, match="cannot be disabled"):
        validate_notification_preferences({"notifications": {"version": 1, "disabled_categories": ["combat_defeat"]}})


@pytest.mark.parametrize("version", [True, False, 1.0, "1", None])
def test_non_integer_versions_are_rejected(version: object) -> None:
    with pytest.raises(ValueError, match="version 1"):
        validate_notification_preferences({"notifications": {"version": version, "disabled_categories": []}})


def test_non_integer_version_defaults_to_enabled() -> None:
    preferences = {"notifications": {"version": True, "disabled_categories": ["advancement"]}}
    assert should_deliver_notification(preferences, NotificationType.LEVEL_UP)


def test_all_selectable_categories_are_known() -> None:
    validate_notification_preferences(
        {"notifications": {"version": 1, "disabled_categories": [category.value for category in NotificationCategory]}}
    )


@pytest.mark.asyncio
async def test_muted_notification_is_not_persisted_or_delivered(
    async_session: AsyncSession, user_with_vault: tuple
) -> None:
    user, vault = user_with_vault
    user_id, vault_id = user.id, vault.id
    profile = await profile_crud.create_for_user(async_session, user_id)
    profile.preferences = {"notifications": {"version": 1, "disabled_categories": ["advancement"]}}
    async_session.add(profile)
    await async_session.commit()

    with patch.object(NotificationService, "_deliver", new_callable=AsyncMock) as deliver:
        notification = await NotificationService.create_and_send(
            async_session,
            user_id=user_id,
            vault_id=vault_id,
            notification_type=NotificationType.LEVEL_UP,
            title="Level up",
            message="A dweller advanced.",
        )

    assert notification is None
    deliver.assert_not_awaited()
    assert (await async_session.execute(select(Notification))).scalars().all() == []
