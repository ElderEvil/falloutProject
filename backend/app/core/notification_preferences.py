"""Versioned, server-enforced notification delivery preferences."""

from enum import StrEnum
from typing import Any

from app.models.notification import NotificationType

NOTIFICATION_PREFERENCES_KEY = "notifications"
NOTIFICATION_PREFERENCES_VERSION = 1


class NotificationCategory(StrEnum):
    EXPLORATION_UPDATES = "exploration_updates"
    ARRIVALS_AND_COMPLETIONS = "arrivals_and_completions"
    ADVANCEMENT = "advancement"
    SOCIAL_ACTIVITY = "social_activity"
    CRAFTING = "crafting"
    VAULT_ACTIVITY = "vault_activity"


NOTIFICATION_CATEGORY_BY_TYPE: dict[NotificationType, NotificationCategory | None] = {
    NotificationType.EXPLORATION_UPDATE: NotificationCategory.EXPLORATION_UPDATES,
    NotificationType.EXPLORATION_COMPLETE: NotificationCategory.ARRIVALS_AND_COMPLETIONS,
    NotificationType.LEVEL_UP: NotificationCategory.ADVANCEMENT,
    NotificationType.TRAINING_COMPLETE: NotificationCategory.ADVANCEMENT,
    NotificationType.TRAINING_STARTED: NotificationCategory.ADVANCEMENT,
    NotificationType.CRAFTING_COMPLETE: NotificationCategory.CRAFTING,
    NotificationType.RELATIONSHIP_FORMED: NotificationCategory.SOCIAL_ACTIVITY,
    NotificationType.PREGNANCY_DETECTED: NotificationCategory.SOCIAL_ACTIVITY,
    NotificationType.BABY_BORN: NotificationCategory.SOCIAL_ACTIVITY,
    NotificationType.RADIO_NEW_DWELLER: NotificationCategory.VAULT_ACTIVITY,
    NotificationType.RADIO_AUTO_SWITCHED_TO_HAPPINESS: NotificationCategory.VAULT_ACTIVITY,
    NotificationType.LOCATION_CLEARED: NotificationCategory.ARRIVALS_AND_COMPLETIONS,
    NotificationType.LOCATION_READY: NotificationCategory.EXPLORATION_UPDATES,
    # These are intentionally always enabled: they are urgent, actionable, or
    # progression-critical. Unknown future types also default to enabled.
    NotificationType.COMBAT_STARTED: None,
    NotificationType.COMBAT_VICTORY: None,
    NotificationType.COMBAT_DEFEAT: None,
    NotificationType.DWELLER_INJURED: None,
    NotificationType.DWELLER_DIED: None,
    NotificationType.DWELLER_EXIT_REQUESTED: None,
    NotificationType.HAZARD_TEAM_JOINED: None,
    NotificationType.RESOURCE_LOW: None,
    NotificationType.RESOURCE_CRITICAL: None,
    NotificationType.POWER_OUTAGE: None,
    NotificationType.QUEST_COMPLETE: NotificationCategory.ARRIVALS_AND_COMPLETIONS,
    NotificationType.ACHIEVEMENT_UNLOCKED: None,
    NotificationType.MAP_REGISTRATION_FAILED: None,
}


def validate_notification_preferences(preferences: dict[str, Any]) -> None:
    """Reject malformed or protected-category notification preference changes."""
    settings = preferences.get(NOTIFICATION_PREFERENCES_KEY)
    if settings is None:
        return
    if not isinstance(settings, dict):
        raise ValueError("Notification preferences must be an object")  # ruff: ignore[type-check-without-type-error] - maps to a 422 response
    if type(settings.get("version")) is not int or settings["version"] != NOTIFICATION_PREFERENCES_VERSION:
        raise ValueError("Notification preferences must use version 1")
    disabled_categories = settings.get("disabled_categories", [])
    if not isinstance(disabled_categories, list) or not all(
        isinstance(category, str) for category in disabled_categories
    ):
        raise ValueError("Disabled notification categories must be a list of strings")
    if len(disabled_categories) != len(set(disabled_categories)):
        raise ValueError("Disabled notification categories must not contain duplicates")
    unknown = set(disabled_categories) - set(NotificationCategory)
    if unknown:
        raise ValueError(f"Notification categories cannot be disabled: {', '.join(sorted(unknown))}")


def should_deliver_notification(preferences: dict[str, Any] | None, notification_type: NotificationType) -> bool:
    """Return whether a notification should persist and fan out for this player."""
    category = NOTIFICATION_CATEGORY_BY_TYPE.get(notification_type)
    if category is None or not isinstance(preferences, dict):
        return True
    settings = preferences.get(NOTIFICATION_PREFERENCES_KEY)
    if (
        not isinstance(settings, dict)
        or type(settings.get("version")) is not int
        or settings.get("version") != NOTIFICATION_PREFERENCES_VERSION
    ):
        return True
    disabled_categories = settings.get("disabled_categories")
    return not isinstance(disabled_categories, list) or category not in disabled_categories
