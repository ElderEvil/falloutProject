from datetime import datetime

from app.utils.time import as_naive_utc, as_utc


def _format_utc_datetime(value: datetime) -> str:
    """Format a single datetime as a UTC ``Z``-suffixed ISO-8601 string."""
    return as_utc(value).isoformat().replace("+00:00", "Z")


def serialize_utc_datetime(value: datetime) -> str:
    """Serialize a required datetime as an unambiguous UTC string.

    The application stores timestamps as naive UTC, so this helper treats
    tz-naive values as UTC and converts tz-aware values to UTC before
    emitting an ISO-8601 string ending with ``Z``.
    """
    return _format_utc_datetime(value)


def serialize_optional_utc_datetime(value: datetime | None) -> str | None:
    """Serialize an optional datetime as an unambiguous UTC string."""
    if value is None:
        return None
    return _format_utc_datetime(value)


def serialize_naive_utc_datetime(value: datetime) -> str:
    """Serialize a datetime as a bare ISO-8601 string in naive UTC.

    Preserves the legacy JSON payload format while converting an aware value to
    the UTC instant before dropping ``tzinfo``.
    """
    return as_naive_utc(value).isoformat()
