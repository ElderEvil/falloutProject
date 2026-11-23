from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from app.cli.main import cli
from app.core.config import settings
from app.services.account_merge_service import MergePreview
from app.utils.exceptions import ResourceConflictException

runner = CliRunner()

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture
def preview() -> MergePreview:
    return MergePreview(
        source_id=uuid4(),
        source_username="old_user",
        source_email="old@example.com",
        target_id=uuid4(),
        target_username="new_user",
        target_email="new@example.com",
        moved_counts={"vaults": 2, "notifications": 3},
        vault_numbers=[4, 9],
        duplicate_vault_numbers=[9],
        oauth_conflicts=["google"],
        tokens_this_month={"source": 120, "target": 80},
        result_email="new@example.com",
        result_username="new_user",
    )


@contextmanager
def _patched_cli(preview_value: MergePreview | None = None, side_effect: Exception | None = None):
    session = AsyncMock()
    with (
        patch("app.cli.main.async_session_maker") as session_maker,
        patch("app.cli.main.merge_users", new_callable=AsyncMock) as merge_mock,
    ):
        session_maker.return_value.__aenter__ = AsyncMock(return_value=session)
        session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        merge_mock.return_value = preview_value
        merge_mock.side_effect = side_effect
        yield merge_mock


def _invoke(*extra: str):
    return runner.invoke(cli, ["merge-users", "--source", "old@example.com", "--target", "new@example.com", *extra])


def test_merge_users_help_lists_options():
    result = runner.invoke(cli, ["merge-users", "--help"])

    assert result.exit_code == 0
    plain_output = ANSI_ESCAPE.sub("", result.output)
    for option in ("--source", "--target", "--actor", "--reason", "--apply", "--dry-run"):
        assert option in plain_output


@pytest.mark.parametrize(
    ("extra", "actor"),
    [((), str(settings.FIRST_SUPERUSER_EMAIL)), (("--actor", "admin@example.com", "--dry-run"), "admin@example.com")],
)
def test_merge_users_defaults_to_dry_run(preview, extra, actor):
    with _patched_cli(preview) as merge_mock, patch("app.cli.main.Redis.from_url") as from_url:
        result = _invoke(*extra)

    assert result.exit_code == 0, result.output
    merge_mock.assert_awaited_once()
    call = merge_mock.call_args
    assert call.args[1:] == ("old@example.com", "new@example.com")
    assert call.kwargs["dry_run"] is True
    assert call.kwargs["redis_client"] is None
    assert call.kwargs["actor"] == actor
    from_url.assert_not_called()
    assert "Dry run" in result.output
    if not extra:
        assert call.kwargs["reason"] == "dry-run preview"
        assert "old_user" in result.output
        assert "new_user" in result.output
        # Moved counts print in sorted key order.
        assert result.output.index("notifications:") < result.output.index("vaults:")
        assert "Vault numbers: 4, 9" in result.output
        assert "Duplicate vault numbers: 9" in result.output
        assert "OAuth conflicts: google" in result.output
        assert "Tokens this month: source=120 target=80" in result.output


@pytest.mark.parametrize("close_error", [False, True])
def test_merge_users_apply_persists_and_closes_redis(preview, close_error):
    audit_id = uuid4()
    applied = replace(preview, applied=True, audit_id=audit_id)
    redis = MagicMock()
    redis.aclose = AsyncMock(side_effect=RuntimeError("close failed") if close_error else None)

    with (
        _patched_cli(applied) as merge_mock,
        patch("app.cli.main.Redis.from_url", return_value=redis) as from_url,
    ):
        result = _invoke("--apply", "--reason", "duplicate account")

    assert result.exit_code == 0, result.output
    call = merge_mock.call_args
    assert call.kwargs["dry_run"] is False
    assert call.kwargs["reason"] == "duplicate account"
    assert call.kwargs["redis_client"] is redis
    from_url.assert_called_once_with(settings.redis_url, decode_responses=True)
    redis.aclose.assert_awaited_once()
    assert f"Audit: {audit_id}" in result.output
    assert "Applied." in result.output
    if close_error:
        assert "merge-users failed" not in result.output


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (("--apply",), "--apply requires a non-empty --reason"),
        (("--apply", "--dry-run", "--reason", "duplicate account"), "cannot be used together"),
    ],
)
def test_merge_users_rejects_invalid_apply_combinations(extra, message):
    with _patched_cli() as merge_mock:
        result = _invoke(*extra)

    assert result.exit_code == 1
    assert message in result.output
    merge_mock.assert_not_awaited()


def test_merge_users_reports_already_merged(preview):
    audit_id = uuid4()
    already_merged = replace(preview, already_merged=True, audit_id=audit_id)

    with _patched_cli(already_merged):
        result = _invoke()

    assert result.exit_code == 0, result.output
    assert f"Already merged (audit {audit_id})." in result.output


def test_merge_users_prints_domain_error():
    with _patched_cli(side_effect=ResourceConflictException("Source account was already merged.")):
        result = _invoke()

    assert result.exit_code == 1
    assert "Error: Source account was already merged." in result.output
