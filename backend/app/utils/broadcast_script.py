"""Broadcast script renderer - pure function(s), no I/O.

Generates a 1950s-style radio announcer script from vault state data.
Word count target: 120-180 words (excluding sign-off).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime


def build_daily_script(
    population: int,
    population_max: int,
    caps: int,
    happiness: int,
    power: tuple[int, int],  # (current, max)
    food: tuple[int, int],
    water: tuple[int, int],
    recent_notifications: list[dict],
    gender_counts: list[tuple[str, int]] | None = None,
    vault_number: int | None = None,
    _now: datetime | None = None,
) -> tuple[str, str]:
    """Build a daily broadcast (title, script) from vault stats.

    Args:
        population: Current number of dwellers.
        population_max: Max capacity.
        caps: Bottle cap count.
        happiness: Vault happiness percentage.
        power: (current, max) power units.
        food: (current, max) food units.
        water: (current, max) water units.
        recent_notifications: Up to 3 notable notifications to weave in.
        vault_number: Optional vault number for sign-off.
        _now: Override datetime for testing.

    Returns:
        (title, script) tuple. Script is ~120-180 words.
    """
    now = _now or datetime.now(UTC)
    day_str = now.strftime("%B %d, %Y")
    title = f"Vault Radio News - {day_str}"

    parts: list[str] = []

    # Opening
    parts.append(
        f"Good evening, this is your evening broadcast from Vault {vault_number or 'the vault'} "
        f"on the {day_str}. We begin with today's vault report."
    )

    # Population
    if population_max and population_max > 0:
        parts.append(
            f"Your vault is home to {population} brave souls, "
            f"squeezing comfortably - or so it seems - within a capacity of {population_max}."
        )
    else:
        parts.append(f"The vault is home to {population} residents today.")

    # Gender split (from dweller data embedded in notifications)
    if gender_counts:
        genders = ", ".join(f"{cnt} {g}" for g, cnt in gender_counts)
        parts.append(f"That breaks down to {genders}.")

    parts.extend(
        [
            (
                f"Your bottle cap reserves stand at {caps:,} - enough to bribe most wastelanders, "
                f"or at least a very persistent scoundrel."
            ),
            (
                f"Vault morale sits at {happiness}%"
                f"{' - a splendid showing!' if happiness >= 80 else ', though there is room for improvement.'}"
            ),
        ]
    )

    # Resources
    parts.append("Let us turn to your essential supplies.")
    for label, (current, maximum) in [("power", power), ("food", food), ("water", water)]:
        if maximum and maximum > 0:
            ratio = current / maximum
            pct = round(ratio * 100)
            parts.append(f"{label.capitalize()} is at {pct}% ({current} of {maximum}).")
        else:
            parts.append(f"{label.capitalize()} stands at {current}.")

    # Notifications
    notable = _extract_notable(recent_notifications)
    if notable:
        parts.extend(["Now for today's headlines.", notable])

    # Sign-off
    sign_off = (
        f"And so ends another broadcast from Vault {vault_number or 'the vault'}. "
        f"Stay safe out there, and remember: peace is our factory."
    )
    parts.append(sign_off)

    script = " ".join(parts)
    return (title, script)


_LEVEL_MESSAGE_NAME = re.compile(r"^(?P<name>.+?) reached level \d+", re.IGNORECASE)
_LEVEL_TITLE_NAME = re.compile(r"^(?P<name>.+?) leveled up", re.IGNORECASE)


def _notification_name(notification: dict) -> str:
    for key in ("dweller_name", "name", "dweller_first_name"):
        value = notification.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key, pattern in (
        ("message", _LEVEL_MESSAGE_NAME),
        ("title", _LEVEL_TITLE_NAME),
    ):
        match = pattern.match(str(notification.get(key, "")))
        if match:
            return match.group("name").strip()
    return ""


def _extract_notable(notifications: list[dict], *, _max: int = 3) -> str:
    """Extract notable notifications, batching level-ups under each dweller's own name."""
    if not notifications:
        return ""

    level_notifications = [
        notification
        for notification in notifications
        if "level" in str(notification.get("notification_type", "")).lower()
    ]
    level_names = [name for notification in level_notifications if (name := _notification_name(notification))]
    unnamed_level_messages = [
        str(notification.get("message", ""))
        for notification in level_notifications
        if not _notification_name(notification) and notification.get("message")
    ]
    lines: list[str] = []
    if level_names:
        if len(level_names) == 1:
            lines.append(f"{level_names[0]} has reached a new level tonight.")
        else:
            lines.append(f"{', '.join(level_names)} have reached new levels tonight.")
    if unnamed_level_messages:
        lines.append(f"A resident has reached a new level. {unnamed_level_messages[0][:80]}.")

    others = [
        notification
        for notification in notifications
        if "level" not in str(notification.get("notification_type", "")).lower()
    ][:_max]
    for notification in others:
        notif_type = str(notification.get("notification_type", "")).lower()
        message = str(notification.get("message", ""))
        name = _notification_name(notification)
        if "dweller" in notif_type and name:
            lines.append(f"{name} - {message[:80]}.")
        elif message:
            lines.append(f"{message[:100]}.")
    return " ".join(lines)
