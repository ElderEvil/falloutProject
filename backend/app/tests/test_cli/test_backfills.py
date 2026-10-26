"""Tests for backfill CLI commands."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

from app.cli.main import cli
from app.services.dweller_name_backfill_service import ActiveVaultBackfillResult

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
        execute_result.scalars.return_value.all.return_value = [MagicMock(id=uuid4(), is_deleted=False)]
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
        execute_result.scalars.return_value.all.return_value = [MagicMock(id=uuid4(), is_deleted=False)]
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


def test_dweller_name_backfill_help():
    result = runner.invoke(cli, ["backfill", "backfill-dweller-names", "--help"])

    assert result.exit_code == 0
    plain_output = ANSI_ESCAPE.sub("", result.output)
    assert "--vault" in plain_output
    assert "--all-active" in plain_output
    assert "--apply" in plain_output


def _dweller_name_summary() -> dict:
    return {
        "scanned": 1,
        "renamed": 1,
        "skipped_curated": 0,
        "skipped_already_shaped": 0,
        "skipped_other_synth": 0,
        "samples": ["Michael Smith -> Grog"],
    }


def test_dweller_name_backfill_dry_run_default():
    vault_id = uuid4()
    patcher = _patch_session(_mock_session_lookup(MagicMock(id=vault_id, is_deleted=False)))

    with patch(
        "app.cli.backfills.dweller_name_backfill_service.backfill_names_for_vault",
        new_callable=AsyncMock,
        return_value=_dweller_name_summary(),
    ) as mocked:
        try:
            result = runner.invoke(cli, ["backfill", "backfill-dweller-names", "--vault", str(vault_id)])
        finally:
            patcher.stop()

    assert result.exit_code == 0
    assert mocked.call_args.kwargs["dry_run"] is True
    assert "renamed=1" in result.output
    assert "Michael Smith -> Grog" in result.output
    assert "Dry run" in result.output


def test_dweller_name_backfill_apply():
    vault_id = uuid4()
    patcher = _patch_session(_mock_session_lookup(MagicMock(id=vault_id, is_deleted=False)))

    with patch(
        "app.cli.backfills.dweller_name_backfill_service.backfill_names_for_vault",
        new_callable=AsyncMock,
        return_value=_dweller_name_summary(),
    ) as mocked:
        try:
            result = runner.invoke(cli, ["backfill", "backfill-dweller-names", "--vault", str(vault_id), "--apply"])
        finally:
            patcher.stop()

    assert result.exit_code == 0
    assert mocked.call_args.kwargs["dry_run"] is False
    assert "Applied." in result.output


def test_dweller_name_backfill_all_active():
    with patch(
        "app.cli.backfills.dweller_name_backfill_service.backfill_names_for_active_vaults",
        new_callable=AsyncMock,
        return_value=ActiveVaultBackfillResult(summaries={}, omitted=0),
    ) as mocked:
        result = runner.invoke(cli, ["backfill", "backfill-dweller-names", "--all-active"])

    assert result.exit_code == 0
    mocked.assert_awaited_once()
    assert mocked.call_args.kwargs["max_vaults"] is None


def test_dweller_name_backfill_reports_vault_cap():
    with patch(
        "app.cli.backfills.dweller_name_backfill_service.backfill_names_for_active_vaults",
        new_callable=AsyncMock,
        return_value=ActiveVaultBackfillResult(summaries={}, omitted=3),
    ) as mocked:
        result = runner.invoke(
            cli,
            ["backfill", "backfill-dweller-names", "--all-active", "--max-vaults", "2"],
        )

    assert result.exit_code == 0
    assert mocked.call_args.kwargs["max_vaults"] == 2
    assert "3 active vault(s) left unprocessed because --max-vaults=2" in result.output


def test_dweller_name_backfill_rejects_zero_vault_cap():
    result = runner.invoke(
        cli,
        ["backfill", "backfill-dweller-names", "--all-active", "--max-vaults", "0"],
    )

    assert result.exit_code != 0
    assert "at least 1" in result.output


def test_dweller_name_backfill_requires_scope():
    result = runner.invoke(cli, ["backfill", "backfill-dweller-names"])

    assert result.exit_code != 0
    assert "Either --vault or --all-active" in result.output
