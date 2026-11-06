"""Broadcast script renderer - pure function(s), no I/O.

Generates a 1950s-style radio announcer script from vault state data.
Word count target: 120-180 words (excluding sign-off).
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from app.core.enums import NotificationType

# Action alerts belong in the live bell, not a retrospective news broadcast.
_NON_HEADLINE_TYPES = {NotificationType.COMBAT_STARTED.value}


def _pick(options: tuple[str, ...], seed: str) -> str:
    """Deterministically choose a phrase: same seed, same phrase, always."""
    digest = hashlib.sha256(seed.encode()).digest()
    return options[int.from_bytes(digest[:8], "big") % len(options)]


_GREETINGS = (
    ("Greetings, dwellers of {vault} - this is your daily broadcast for {day}, "
    "and we begin with today's vault report."),
    "This is {vault} radio, signing on for {day} with your daily vault report.",
    "Attention, dwellers of {vault}: the daily broadcast for {day} is on the air.",
    "Good day, residents of {vault}. Settle in - your daily report for {day} begins now.",
    "You are listening to the {vault} daily broadcast for {day}. The news starts now.",
)

_CAPS_LINES = (
    ("Your bottle cap reserves stand at {caps:,} - enough to bribe most wastelanders, "
    "or at least a very persistent scoundrel."),
    "Your bottle cap reserves stand at {caps:,} - enough to make even a raider do a double take.",
    "The cap counter reads {caps:,}. The vending machines remain deeply impressed.",
    "Treasury report: {caps:,} bottle caps, and every last one accounted for. Mostly.",
    "Your cap stash holds {caps:,} - enough to keep the jukebox running and the Overseer smiling.",
)

_MORALE_TIERS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (
        90,
        (
            "Vault morale sits at {h}% - a splendid showing!",
            "Morale holds at {h}% - the jukebox plays, the people dance.",
        ),
    ),
    (
        60,
        (
            ("Vault morale sits at a steady {h}% - neither the wasteland nor the week "
            "has broken the spring in anyone's step."),
            "Vault morale rests at a comfortable {h}%. The corridor hums along nicely.",
        ),
    ),
    (
        30,
        (
            ("Vault morale sits at {h}%, though there is room for improvement - "
            "perhaps a concert in the atrium."),
            "Morale reads {h}%, and the atmosphere could use some polish. Organize a dance, perhaps.",
        ),
    ),
    (
        0,
        (
            "Vault morale sits at a troubling {h}%. The counselor's door is open, dwellers.",
            "Morale reads a grim {h}%. Ration the joy, but do not ration hope.",
        ),
    ),
)

_LOW_SUPPLY_FLAVOR: dict[str, tuple[str, ...]] = {
    "power": ("Conserve those bulbs - the generators are wheezing.",),
    "food": ("The mess hall is stretching the stew. Again.",),
    "water": ("Ration the water; the Purifier is on a strict diet.",),
}

_HOUSEKEEPING_LINES = (
    ("Elsewhere in the vault: the corridors are swept, the reactors hum, and the "
    "forecast calls for dust with a chance of radstorms."),
    ("In housekeeping news: the water pipes sang all night, and nobody has yet "
    "asked them to stop."),
    "A reminder from maintenance: if you hear knocking in the walls, do not knock back.",
)

_SIGN_OFFS = (
    ("And so ends another broadcast from {vault}. Stay safe out there, and remember: "
    "peace is our factory."),
    "That is the daily report from {vault}. Warm beds and quiet pipes to you all.",
    ("This is your announcer, closing another day at {vault}. Keep your Vault suit shiny "
    "and your head down."),
    "From all of us at {vault} radio: sleep tight, dwellers, and trust the Overseer.",
    ("The broadcast ends, but the vault endures. From {vault}, good night - whenever "
    "that is for you."),
)


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
    variant_seed: str | None = None,
    _now: datetime | None = None,
) -> tuple[str, str]:
    """Build a daily broadcast (title, script) from vault stats.

    Phrase variants are chosen deterministically from ``variant_seed`` (falling
    back to the vault number and UTC date), so the once-per-day render stays
    stable while different vaults and days hear different broadcasts.

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
        variant_seed: Deterministic seed for phrase variants.
        _now: Override datetime for testing.

    Returns:
        (title, script) tuple. Script is ~120-180 words.
    """
    now = _now or datetime.now(UTC)
    # The vault day rolls over at UTC midnight, but listeners play the broadcast
    # at every local hour, so the greeting stays time-of-day neutral.
    day_str = f"{now.strftime('%B')} {now.day}, {now.year}"
    title = f"Vault Radio News - {day_str}"

    vault_label = f"Vault {vault_number}" if vault_number else "the vault"
    seed_base = variant_seed or f"{vault_number}:{now.date().isoformat()}"
    parts: list[str] = []

    # Opening
    parts.append(
        _pick(_GREETINGS, f"{seed_base}:greeting").format(vault=vault_label, day=day_str)
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

    parts.extend((_pick(_HOUSEKEEPING_LINES, f"{seed_base}:housekeeping"), _pick(_CAPS_LINES, f"{seed_base}:caps").format(caps=caps)))

    morale_threshold, morale_pool = next(
        (threshold, pool) for threshold, pool in _MORALE_TIERS if happiness >= threshold
    )
    parts.extend(
        [
            _pick(morale_pool, f"{seed_base}:morale:{morale_threshold}").format(h=happiness),
            "Let us turn to your essential supplies.",
        ]
    )
    for label, (current, maximum) in [("power", power), ("food", food), ("water", water)]:
        if maximum and maximum > 0:
            ratio = current / maximum
            pct = round(ratio * 100)
            line = f"{label.capitalize()} is at {pct}%."
            if ratio < 0.25:
                line += " " + _pick(
                    _LOW_SUPPLY_FLAVOR[label], f"{seed_base}:{label}:low"
                )
            parts.append(line)
        else:
            parts.append(f"{label.capitalize()} readings are unavailable.")

    # Notifications
    notable = _extract_notable(recent_notifications)
    if notable:
        parts.extend(["Now for today's headlines.", notable])

    # Sign-off
    parts.append(_pick(_SIGN_OFFS, f"{seed_base}:signoff").format(vault=vault_label))

    script = " ".join(parts)
    return (title, script)


_LEVEL_MESSAGE_NAME = re.compile(r"^(?P<name>.+?) reached level \d+", re.IGNORECASE)
_LEVEL_TITLE_NAME = re.compile(r"^(?P<name>.+?) leveled up", re.IGNORECASE)
# Notification messages carry a "[Vault N]" prefix for cross-vault
# disambiguation in the notification center; the broadcast is already
# bound to one vault, so the prefix is noise here.
_VAULT_PREFIX = re.compile(r"^\[Vault \d+\]\s*", re.IGNORECASE)


def _strip_vault_prefix(text: str) -> str:
    return _VAULT_PREFIX.sub("", text)


def _notification_name(notification: dict) -> str:
    for key in ("dweller_name", "name", "dweller_first_name"):
        value = notification.get(key)
        if isinstance(value, str) and value.strip():
            return _strip_vault_prefix(value.strip())
    for key, pattern in (
        ("message", _LEVEL_MESSAGE_NAME),
        ("title", _LEVEL_TITLE_NAME),
    ):
        match = pattern.match(_strip_vault_prefix(str(notification.get(key, ""))))
        if match:
            return _strip_vault_prefix(match.group("name").strip())
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
    level_names = list(
        dict.fromkeys(name for notification in level_notifications if (name := _notification_name(notification)))
    )
    unnamed_level_messages = [
        _strip_vault_prefix(str(notification.get("message", "")))
        for notification in level_notifications
        if not _notification_name(notification) and notification.get("message")
    ]
    lines: list[str] = []
    if level_names:
        if len(level_names) == 1:
            lines.append(f"{level_names[0]} has reached a new level today.")
        else:
            lines.append(f"{', '.join(level_names)} have reached new levels today.")
    if unnamed_level_messages:
        lines.append(f"A resident has reached a new level. {unnamed_level_messages[0][:80].rstrip(' .!')}.")

    others = [
        notification
        for notification in notifications
        if "level" not in str(notification.get("notification_type", "")).lower()
        and str(notification.get("notification_type", "")).lower() not in _NON_HEADLINE_TYPES
    ][:_max]
    for notification in others:
        notif_type = str(notification.get("notification_type", "")).lower()
        message = _strip_vault_prefix(str(notification.get("message", "")))
        name = _notification_name(notification)
        if "dweller" in notif_type and name:
            lines.append(f"{name} - {message[:80].rstrip(' .!')}.")
        elif message:
            lines.append(f"{message[:100].rstrip(' .!')}.")
    return " ".join(lines)
