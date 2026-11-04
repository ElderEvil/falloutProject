"""Displayed encounter odds must describe the actual die outcomes."""

import pytest

from app.services.exploration import checks


@pytest.mark.parametrize("stat", range(1, 11))
@pytest.mark.parametrize("difficulty", range(1, 6))
def test_displayed_odds_match_all_die_faces(monkeypatch, stat, difficulty):
    successes = 0
    for face in range(1, 21):
        monkeypatch.setattr(checks.random, "randint", lambda _low, _high, face=face: face)
        successes += checks.roll_check(stat, difficulty)
    assert checks.success_odds(stat, difficulty) == pytest.approx(successes / 20)
