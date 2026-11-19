from datetime import datetime

from app.utils.time import as_naive_utc, as_utc


def _format_utc_datetime(value: datetime) -> str:
    """Format a single datetime as a UTC ``Z``-suffixed ISO-8601 string."""
    return as_utc(value).isoformat().replace("+00:00", "Z")


def serialize_utc_datetime(value: datetime) -> str:
    """Serialize a required datetime as an ISO-8601 UTC string ending in Z; tz-naive values
    are treated as UTC (the app stores naive UTC).
    """
    return _format_utc_datetime(value)


def serialize_optional_utc_datetime(value: datetime | None) -> str | None:
    """Serialize an optional datetime as an unambiguous UTC string."""
    if value is None:
        return None
    return _format_utc_datetime(value)


def serialize_naive_utc_datetime(value: datetime) -> str:
    """Serialize as a bare naive-UTC ISO-8601 string (legacy JSON payload format); aware
    values are converted to UTC before dropping tzinfo.
    """
    return as_naive_utc(value).isoformat()
