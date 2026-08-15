from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from app.models.training import TrainingStatus
from app.schemas.common import SPECIALEnum
from app.schemas.training import TrainingRead


def _make_training(**overrides: object) -> TrainingRead:
    defaults = {
        "id": uuid4(),
        "dweller_id": uuid4(),
        "room_id": uuid4(),
        "vault_id": uuid4(),
        "stat_being_trained": SPECIALEnum.STRENGTH,
        "current_stat_value": 1,
        "target_stat_value": 2,
        "started_at": datetime(2026, 8, 15, 0, 36, 16, 365844),
        "estimated_completion_at": datetime(2026, 8, 15, 0, 36, 16, 365844),
        "completed_at": None,
        "status": TrainingStatus.ACTIVE,
        "created_at": datetime(2026, 8, 15, 0, 36, 16, 365844),
        "updated_at": datetime(2026, 8, 15, 0, 36, 16, 365844),
    }
    defaults.update(overrides)  # type: ignore[arg-type]
    return TrainingRead(**defaults)


def test_training_datetime_serialization_marks_naive_utc_as_utc() -> None:
    timestamp = datetime(2026, 8, 15, 0, 36, 16, 365844)
    training = _make_training(
        started_at=timestamp,
        estimated_completion_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )

    payload = training.model_dump_json()

    assert "2026-08-15T00:36:16.365844Z" in payload


def test_training_datetime_serialization_converts_aware_to_utc() -> None:
    # 14:00 in +02:00 equals 12:00 UTC
    aware = datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    training = _make_training(
        started_at=aware,
        estimated_completion_at=aware,
        created_at=aware,
        updated_at=aware,
    )

    payload = training.model_dump_json()

    assert "2026-08-15T12:00:00Z" in payload


def test_training_datetime_serialization_preserves_utc_timezone() -> None:
    utc_aware = datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC)
    training = _make_training(
        started_at=utc_aware,
        estimated_completion_at=utc_aware,
        created_at=utc_aware,
        updated_at=utc_aware,
    )

    payload = training.model_dump_json()

    assert "2026-08-15T12:00:00Z" in payload


def test_training_datetime_serialization_handles_none() -> None:
    training = _make_training(completed_at=None)

    payload = training.model_dump_json()

    assert '"completed_at":null' in payload
