"""Output contract for the expedition scenario CLI."""

from types import SimpleNamespace
from uuid import uuid4

from app.cli.expedition_scenario import _print_setup
from app.core.config import settings


def _result(owner_email: str):
    return SimpleNamespace(
        vault=SimpleNamespace(id=uuid4()),
        created_vault=False,
        dweller=SimpleNamespace(display_name="Scout Scenario", level=5, id=uuid4()),
        exploration=SimpleNamespace(id=uuid4(), status=SimpleNamespace(value="active")),
        available_sites=[],
        precleared_site_id=None,
        owner_email=owner_email,
    )


def test_setup_output_uses_actual_owner_without_superuser_hint(capsys):
    _print_setup(_result("another-owner@example.test"))

    output = capsys.readouterr().out
    assert "Login: another-owner@example.test" in output
    assert "superuser" not in output
    assert "FIRST_SUPERUSER_PASSWORD" not in output


def test_setup_output_keeps_superuser_hint_for_configured_owner(capsys):
    _print_setup(_result(settings.FIRST_SUPERUSER_EMAIL))

    assert "FIRST_SUPERUSER_PASSWORD" in capsys.readouterr().out
