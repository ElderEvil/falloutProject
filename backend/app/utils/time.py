"""Single clock source for the application.

utcnow returns timezone-aware UTC (datetime.utcnow is deprecated since 3.12) for the
timestamptz contract; UTCDateTime normalizes SQLite storage.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Return value as timezone-aware UTC; naive values (legacy JSON/assigned) are interpreted
    as UTC, aware values converted, not relabelled.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def as_naive_utc(value: datetime) -> datetime:
    """Return ``value`` as a naive UTC datetime for legacy JSON and identity boundaries."""
    return as_utc(value).replace(tzinfo=None)
