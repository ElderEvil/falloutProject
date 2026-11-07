"""Versioned account-level preferences with server-visible behaviour."""

from typing import Any

from app.core.notification_preferences import validate_notification_preferences

SETUP_PREFERENCES_KEY = "setup"
SETUP_PREFERENCES_VERSION = 1


def validate_profile_preferences(preferences: dict[str, Any]) -> None:
    """Reject malformed preference payloads before they are persisted."""
    validate_notification_preferences(preferences)
    setup = preferences.get(SETUP_PREFERENCES_KEY)
    if setup is None:
        return
    if not isinstance(setup, dict):
        raise ValueError("Setup preferences must be an object")  # ruff: ignore[type-check-without-type-error] - maps to a 422 response
    if type(setup.get("version")) is not int or setup["version"] != SETUP_PREFERENCES_VERSION:
        raise ValueError("Setup preferences must use version 1")
    if type(setup.get("completed")) is not bool:
        raise ValueError("Setup preferences must include a boolean completed flag")
    if "skipped" in setup and type(setup["skipped"]) is not bool:
        raise ValueError("Setup skipped must be a boolean")
