"""Tests for the trivia scenario CLI profiles and help contract."""

import re

import pytest
from typer.testing import CliRunner

from app.cli.main import cli
from app.cli.trivia_scenario import PROFILES, resolve_profile

runner = CliRunner()
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def test_profiles_cover_demo_balanced_and_hard():
    assert PROFILES == {"demo": (10, 7), "balanced": (5, 4), "hard": (3, 3)}


def test_balanced_profile_is_the_default_scout():
    assert resolve_profile("balanced", None, None) == (5, 4)


def test_explicit_scout_overrides_win_over_the_profile():
    assert resolve_profile("balanced", 8, 6) == (8, 6)


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError, match="Unknown profile"):
        resolve_profile("nightmare", None, None)


def test_setup_help_lists_profiles():
    result = runner.invoke(cli, ["trivia-scenario", "setup", "--help"])
    assert result.exit_code == 0
    output = ANSI_ESCAPE.sub("", result.output)
    assert "--profile" in output
    assert "balanced" in output
