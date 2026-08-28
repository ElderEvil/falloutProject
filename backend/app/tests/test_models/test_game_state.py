"""Game-state model tests."""

from app.models.game_state import GameStateBase
from app.utils.datetime import utc_now


def test_game_state_defaults_use_shared_utc_clock() -> None:
    assert GameStateBase.model_fields["last_tick_time"].default_factory is utc_now
    assert GameStateBase.model_fields["last_activity_time"].default_factory is utc_now
