from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.arena_match_event import ArenaMatchEvent
from app.services.combat.arena_service import ArenaService


def test_event_snapshot_preserves_the_instant_of_an_aware_timestamp():
    created_at = datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    event = ArenaMatchEvent(room_id=uuid4(), round_seq=1, kind="hit", message="hit", created_at=created_at)

    assert ArenaService._event_snapshot(event)["created_at"] == "2026-01-01T12:00:00+00:00"
