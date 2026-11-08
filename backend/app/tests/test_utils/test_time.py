from datetime import UTC, datetime, timedelta

from app.utils.time import utcnow


class TestUtcNow:
    def test_returns_naive_datetime_for_the_legacy_storage_contract(self):
        assert utcnow().tzinfo is None

    def test_wall_clock_is_utc_not_local(self):
        reference = datetime.now(UTC).replace(tzinfo=None)
        assert abs((utcnow() - reference).total_seconds()) < 5

    def test_is_monotonic_enough_for_deadlines(self):
        earlier = utcnow()
        later = utcnow()
        assert later >= earlier
        assert (later - earlier) < timedelta(seconds=5)
