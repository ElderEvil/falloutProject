from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from app.core.enums import PregnancyStatusEnum
from app.models.pregnancy import Pregnancy
from app.utils.time import utcnow


def _pregnancy(due_at: datetime, *, conceived_at: datetime | None = None) -> Pregnancy:
    return Pregnancy(
        mother_id=uuid4(),
        father_id=uuid4(),
        conceived_at=conceived_at or (utcnow() - timedelta(hours=1)),
        due_at=due_at,
        status=PregnancyStatusEnum.PREGNANT,
    )


def test_is_due_compares_instants_not_wall_clocks():
    # Past instant shown 2h ahead vs future instant shown 5h behind: offsets must not fool the check.
    past_at = (datetime.now(UTC) - timedelta(minutes=90)).astimezone(timezone(timedelta(hours=2)))
    assert _pregnancy(past_at).is_due is True
    future_at = (datetime.now(UTC) + timedelta(minutes=90)).astimezone(timezone(timedelta(hours=-5)))
    assert _pregnancy(future_at).is_due is False


def test_progress_and_remaining_accept_aware_timestamps():
    conceived_at = (datetime.now(UTC) - timedelta(hours=5)).astimezone(timezone(timedelta(hours=2)))
    due_at = (datetime.now(UTC) + timedelta(hours=5)).astimezone(timezone(timedelta(hours=2)))
    pregnancy = _pregnancy(due_at, conceived_at=conceived_at)
    assert 45 <= pregnancy.progress_percentage <= 55
    assert 4.9 * 3600 <= pregnancy.time_remaining_seconds <= 5.1 * 3600
