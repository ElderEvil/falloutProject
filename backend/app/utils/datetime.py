"""Shared datetime helpers for naive-UTC timestamps."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current UTC time as a naive datetime."""
    return datetime.now(UTC).replace(tzinfo=None)
