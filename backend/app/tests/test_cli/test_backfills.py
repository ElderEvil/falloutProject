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


def _mock_session_lookup(vault: MagicMock | None) -> AsyncMock:
    """Session whose first vault lookup returns the given vault (or nothing)."""
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = vault
    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _patch_session(session: AsyncMock):
    patcher = patch("app.cli.backfills.async_session_maker")
    mock_session_maker = patcher.start()
    mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=session)
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
    return patcher


def test_merge_rooms_dry_run_default(mock_backfill):
    vault_id = uuid4()
    mock_backfill.return_value = {"merged": 2}
    patcher = _patch_session(_mock_session_lookup(MagicMock(id=vault_id, is_deleted=False)))

    try:
        result = runner.invoke(cli, ["backfill", "merge-rooms", "--vault", str(vault_id)])
    finally:
        patcher.stop()

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
    patcher = _patch_session(_mock_session_lookup(MagicMock(id=vault_id, is_deleted=False)))

    try:
        result = runner.invoke(cli, ["backfill", "merge-rooms", "--vault", str(vault_id), "--apply"])
    finally:
        patcher.stop()

    assert result.exit_code == 0
    mock_backfill.assert_awaited_once()
    call_kwargs = mock_backfill.call_args.kwargs
    assert call_kwargs["dry_run"] is False
    assert "Applied." in result.output


def test_merge_rooms_rejects_missing_or_deleted_vault(mock_backfill):
    """A vault that is missing or soft-deleted is rejected instead of silently processed."""
    vault_id = uuid4()
    patcher = _patch_session(_mock_session_lookup(None))

    try:
        result = runner.invoke(cli, ["backfill", "merge-rooms", "--vault", str(vault_id)])
    finally:
        patcher.stop()

    assert result.exit_code != 0
    assert "not found or deleted" in result.output
    mock_backfill.assert_not_awaited()


def test_layout_rejects_missing_or_deleted_vault():
    vault_id = uuid4()
    patcher = _patch_session(_mock_session_lookup(None))

    try:
        result = runner.invoke(
            cli,
            ["backfill", "backfill-vault-layout", "--vault", str(vault_id)],
        )
    finally:
        patcher.stop()

    assert result.exit_code != 0
    assert "not found or deleted" in result.output


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


def test_merge_rooms_all_active_excludes_deleted_vaults(mock_backfill):
    mock_backfill.return_value = {"merged": 0}

    with patch("app.cli.backfills.async_session_maker") as mock_session_maker:
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [uuid4()]
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=execute_result)
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(cli, ["backfill", "merge-rooms", "--all-active"])

    assert result.exit_code == 0
    assert "is_deleted" in str(mock_session.execute.call_args.args[0])


def test_layout_apply_refuses_invalid_layout():
    vault_id = uuid4()
    invalid_summary = {
        "rooms": 2,
        "moved": 1,
        "elevators_to_add": 0,
        "overlaps": 1,
        "floating": 0,
        "floor_width_ok": True,
    }

    with (
        patch(
            "app.services.vault_layout_backfill_service.vault_layout_backfill_service.relayout",
            new_callable=AsyncMock,
            return_value=invalid_summary,
        ),
        patch("app.cli.backfills.async_session_maker") as mock_session_maker,
    ):
        mock_session = _mock_session_lookup(MagicMock(id=vault_id, is_deleted=False))
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        result = runner.invoke(
            cli,
            ["backfill", "backfill-vault-layout", "--vault", str(vault_id), "--apply"],
        )

    assert result.exit_code != 0
    assert "invalid layouts" in result.output
    mock_session.commit.assert_not_awaited()
    mock_session.rollback.assert_awaited()


def test_merge_rooms_requires_vault_or_all_active():
    result = runner.invoke(cli, ["backfill", "merge-rooms"])
    assert result.exit_code != 0
    assert "Pass --vault" in result.output or "--vault" in result.output


def test_merge_rooms_rejects_invalid_vault_uuid():
    result = runner.invoke(cli, ["backfill", "merge-rooms", "--vault", "not-a-uuid"])
    assert result.exit_code != 0
    assert "Invalid vault UUID" in result.output
