from datetime import UTC, datetime, timedelta, timezone

from app.utils.time import as_naive_utc, as_utc, utcnow


class TestAsUtc:
    def test_naive_values_are_interpreted_as_utc(self):
        assert as_utc(datetime(2026, 1, 1, 12, 0)) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def test_aware_values_are_converted_instead_of_relabelled(self):
        offset_value = datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))

        assert as_utc(offset_value) == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class TestAsNaiveUtc:
    def test_naive_values_are_unchanged(self):
        assert as_naive_utc(datetime(2026, 1, 1, 12, 0)) == datetime(2026, 1, 1, 12, 0)

    def test_aware_values_are_converted_before_dropping_tzinfo(self):
        offset_value = datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))

        assert as_naive_utc(offset_value) == datetime(2026, 1, 1, 12, 0)


class TestUtcNow:
    def test_returns_aware_utc_datetime(self):
        assert utcnow().tzinfo is UTC

    def test_wall_clock_is_utc_not_local(self):
        reference = datetime.now(UTC)
        assert abs((utcnow() - reference).total_seconds()) < 5

    def test_is_monotonic_enough_for_deadlines(self):
        earlier = utcnow()
        later = utcnow()
        assert later >= earlier
        assert (later - earlier) < timedelta(seconds=5)
