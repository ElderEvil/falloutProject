"""Single clock source for the application.

``datetime.utcnow()`` is deprecated since Python 3.12 and is scheduled for removal.
Every producer now goes through :func:`utcnow`, so the eventual switch to
timezone-aware UTC is one edit rather than 384 call sites.

Transitional contract: until the 3.0 ``timestamp -> timestamptz`` migration lands,
columns are still ``timestamp without time zone`` and the database contract is
naive-but-UTC. :func:`utcnow` therefore returns a naive datetime whose wall clock
is UTC. When the columns become aware this function drops the ``replace(tzinfo=None)``
and the storage layer converts.
"""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime (legacy storage contract)."""
    return datetime.now(UTC).replace(tzinfo=None)


def as_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    Naive values follow the legacy storage contract and are interpreted as UTC;
    aware values are converted to UTC rather than relabelled.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def as_naive_utc(value: datetime) -> datetime:
    """Return ``value`` as a naive UTC datetime (legacy storage contract)."""
    return as_utc(value).replace(tzinfo=None)
