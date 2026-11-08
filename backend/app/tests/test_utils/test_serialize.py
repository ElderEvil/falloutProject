from datetime import datetime, timedelta, timezone

from app.utils.serialize import serialize_naive_utc_datetime, serialize_utc_datetime


def test_naive_utc_serializer_keeps_the_legacy_bare_format():
    assert serialize_naive_utc_datetime(datetime(2026, 1, 1, 12, 0)) == "2026-01-01T12:00:00"


def test_naive_utc_serializer_converts_offsets_before_dropping_tzinfo():
    offset_value = datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))

    assert serialize_naive_utc_datetime(offset_value) == "2026-01-01T12:00:00"


def test_aware_utc_serializer_converts_offsets_before_emitting_z():
    offset_value = datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))

    assert serialize_utc_datetime(offset_value) == "2026-01-01T12:00:00Z"
