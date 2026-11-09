"""Single clock source for the application.

``datetime.utcnow()`` is deprecated since Python 3.12. Every producer goes
through :func:`utcnow`, which returns timezone-aware UTC for the 3.0
``timestamptz`` contract. Stored timestamps are aware UTC on PostgreSQL; the
:class:`app.utils.types.UTCDateTime` decorator normalizes SQLite storage.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    Naive values are legacy JSON or assigned values and are interpreted as UTC;
    aware values are converted to UTC rather than relabelled.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def as_naive_utc(value: datetime) -> datetime:
    """Return ``value`` as a naive UTC datetime for legacy JSON and identity boundaries."""
    return as_utc(value).replace(tzinfo=None)
