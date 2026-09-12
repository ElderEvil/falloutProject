"""Tests for backfill CLI commands."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

from app.cli.main import cli

runner = CliRunner()

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture
def mock_backfill():
    with patch(
        "app.cli.backfills.room_service.backfill_merge_rooms_for_vault",
        new_callable=AsyncMock,
    ) as mocked:
        yield mocked


def test_merge_rooms_help():
    result = runner.invoke(cli, ["backfill", "merge-rooms", "--help"])
    assert result.exit_code == 0
    plain_output = ANSI_ESCAPE.sub("", result.output)
    assert "--vault" in plain_output
    assert "--all-active" in plain_output
    assert "--apply" in plain_output


def test_merge_rooms_dry_run_default(mock_backfill):
    vault_id = uuid4()
    mock_backfill.return_value = {"merged": 2}

    result = runner.invoke(cli, ["backfill", "merge-rooms", "--vault", str(vault_id)])

    assert result.exit_code == 0
    mock_backfill.assert_awaited_once()
    call_args = mock_backfill.call_args
    assert call_args.args[1] == vault_id
    assert call_args.kwargs["dry_run"] is True
    assert "merged=2" in result.output
    assert "Dry run" in result.output


def test_merge_rooms_apply(mock_backfill):
    vault_id = uuid4()
    mock_backfill.return_value = {"merged": 2}

    result = runner.invoke(cli, ["backfill", "merge-rooms", "--vault", str(vault_id), "--apply"])

    assert result.exit_code == 0
    mock_backfill.assert_awaited_once()
    call_kwargs = mock_backfill.call_args.kwargs
    assert call_kwargs["dry_run"] is False
    assert "Applied." in result.output


def test_merge_rooms_all_active(mock_backfill):
    mock_backfill.return_value = {"merged": 0}

    with patch(
        "app.cli.backfills.async_session_maker",
    ) as mock_session_maker:
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [uuid4()]
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.execute = AsyncMock(return_value=execute_result)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(cli, ["backfill", "merge-rooms", "--all-active"])

    assert result.exit_code == 0
    mock_backfill.assert_awaited_once()


def test_merge_rooms_requires_vault_or_all_active():
    result = runner.invoke(cli, ["backfill", "merge-rooms"])
    assert result.exit_code != 0
    assert "Pass --vault" in result.output or "--vault" in result.output


def test_merge_rooms_rejects_invalid_vault_uuid():
    result = runner.invoke(cli, ["backfill", "merge-rooms", "--vault", "not-a-uuid"])
    assert result.exit_code != 0
    assert "Invalid vault UUID" in result.output
