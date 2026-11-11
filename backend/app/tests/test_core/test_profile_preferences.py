import pytest

from app.core.profile_preferences import validate_profile_preferences
from app.schemas.user_profile import ProfileUpdate


def test_setup_preference_accepts_a_complete_record() -> None:
    validate_profile_preferences({"setup": {"version": 1, "completed": True, "skipped": False}})


def test_setup_preference_accepts_a_record_without_skipped() -> None:
    validate_profile_preferences({"setup": {"version": 1, "completed": True}})


@pytest.mark.parametrize(
    "setup",
    [
        "done",
        {},
        {"version": 2, "completed": True},
        {"version": 1},
        {"version": 1, "completed": "yes"},
        {"version": 1, "completed": True, "skipped": "no"},
    ],
)
def test_setup_preference_rejects_malformed_records(setup: object) -> None:
    with pytest.raises(ValueError, match="Setup"):
        validate_profile_preferences({"setup": setup})


def test_profile_update_accepts_setup_preferences() -> None:
    update = ProfileUpdate(preferences={"setup": {"version": 1, "completed": True}})
    assert update.preferences == {"setup": {"version": 1, "completed": True}}
