from __future__ import annotations

import re
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from app.cli.main import cli
from app.services.dweller_name_backfill_service import ActiveVaultBackfillResult

runner = CliRunner()

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
MERGE_ROOMS = "app.cli.backfills.room_service.backfill_merge_rooms_for_vault"
NAMES_FOR_VAULT = "app.cli.backfills.dweller_name_backfill_service.backfill_names_for_vault"
NAMES_FOR_ACTIVE = "app.cli.backfills.dweller_name_backfill_service.backfill_names_for_active_vaults"


@pytest.fixture
def mock_backfill():
    with patch(MERGE_ROOMS, new_callable=AsyncMock) as mocked:
        yield mocked


def _session(vault: MagicMock | None = None, active: list | None = None) -> AsyncMock:
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = vault
    execute_result.scalars.return_value.all.return_value = active if active is not None else []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@contextmanager
def _patched_session(session: AsyncMock):
    with patch("app.cli.backfills.async_session_maker") as maker:
        maker.return_value.__aenter__ = AsyncMock(return_value=session)
        maker.return_value.__aexit__ = AsyncMock(return_value=False)
        yield


def _live_vault() -> MagicMock:
    return MagicMock(id=uuid4(), is_deleted=False)


def test_merge_rooms_help():
    result = runner.invoke(cli, ["backfill", "merge-rooms", "--help"])
    assert result.exit_code == 0
    plain_output = ANSI_ESCAPE.sub("", result.output)
    assert "--vault" in plain_output
    assert "--all-active" in plain_output
    assert "--apply" in plain_output


@pytest.mark.parametrize("apply", [False, True])
def test_merge_rooms_dry_run_default_and_apply(mock_backfill, apply):
    vault_id = uuid4()
    mock_backfill.return_value = {"merged": 2}
    args = ["backfill", "merge-rooms", "--vault", str(vault_id)] + (["--apply"] if apply else [])

    with _patched_session(_session(MagicMock(id=vault_id, is_deleted=False))):
        result = runner.invoke(cli, args)

    assert result.exit_code == 0
    mock_backfill.assert_awaited_once()
    call_args = mock_backfill.call_args
    assert call_args.args[1] == vault_id
    assert call_args.kwargs["dry_run"] is not apply
    if apply:
        assert "Applied." in result.output
    else:
        assert "merged=2" in result.output
        assert "Dry run" in result.output


@pytest.mark.parametrize("command", ["merge-rooms", "backfill-vault-layout"])
def test_backfill_rejects_missing_or_deleted_vault(mock_backfill, command):
    vault_id = uuid4()
    mock_backfill.return_value = {"merged": 2}

    with _patched_session(_session(None)):
        result = runner.invoke(cli, ["backfill", command, "--vault", str(vault_id)])

    assert result.exit_code != 0
    assert "not found or deleted" in result.output
    mock_backfill.assert_not_awaited()


def test_merge_rooms_all_active(mock_backfill):
    mock_backfill.return_value = {"merged": 0}

    with _patched_session(_session(active=[_live_vault()])):
        result = runner.invoke(cli, ["backfill", "merge-rooms", "--all-active"])

    assert result.exit_code == 0
    mock_backfill.assert_awaited_once()


def test_merge_rooms_all_active_excludes_deleted_vaults(mock_backfill):
    mock_backfill.return_value = {"merged": 0}
    session = _session(active=[_live_vault()])

    with _patched_session(session):
        result = runner.invoke(cli, ["backfill", "merge-rooms", "--all-active"])

    assert result.exit_code == 0
    assert "is_deleted" in str(session.execute.call_args.args[0])


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
    session = _session(MagicMock(id=vault_id, is_deleted=False))

    with (
        patch(
            "app.services.vault_layout_backfill_service.vault_layout_backfill_service.relayout",
            new_callable=AsyncMock,
            return_value=invalid_summary,
        ),
        _patched_session(session),
    ):
        result = runner.invoke(cli, ["backfill", "backfill-vault-layout", "--vault", str(vault_id), "--apply"])

    assert result.exit_code != 0
    assert "invalid layouts" in result.output
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited()


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


@pytest.mark.parametrize("apply", [False, True])
def test_dweller_name_backfill_dry_run_default_and_apply(apply):
    vault_id = uuid4()
    args = ["backfill", "backfill-dweller-names", "--vault", str(vault_id)] + (["--apply"] if apply else [])

    with (
        _patched_session(_session(MagicMock(id=vault_id, is_deleted=False))),
        patch(NAMES_FOR_VAULT, new_callable=AsyncMock, return_value=_dweller_name_summary()) as mocked,
    ):
        result = runner.invoke(cli, args)

    assert result.exit_code == 0
    assert mocked.call_args.kwargs["dry_run"] is not apply
    if apply:
        assert "Applied." in result.output
    else:
        assert "renamed=1" in result.output
        assert "Michael Smith -> Grog" in result.output
        assert "Dry run" in result.output


@pytest.mark.parametrize(("omitted", "args", "max_vaults"), [(0, [], None), (3, ["--max-vaults", "2"], 2)])
def test_dweller_name_backfill_all_active_reports_vault_cap(omitted, args, max_vaults):
    with patch(
        NAMES_FOR_ACTIVE,
        new_callable=AsyncMock,
        return_value=ActiveVaultBackfillResult(summaries={}, omitted=omitted),
    ) as mocked:
        result = runner.invoke(cli, ["backfill", "backfill-dweller-names", "--all-active", *args])

    assert result.exit_code == 0
    mocked.assert_awaited_once()
    assert mocked.call_args.kwargs["max_vaults"] == max_vaults
    if omitted:
        assert "3 active vault(s) left unprocessed because --max-vaults=2" in result.output


def test_dweller_name_backfill_rejects_zero_vault_cap():
    result = runner.invoke(cli, ["backfill", "backfill-dweller-names", "--all-active", "--max-vaults", "0"])

    assert result.exit_code != 0
    assert "at least 1" in result.output


def test_dweller_name_backfill_requires_scope():
    result = runner.invoke(cli, ["backfill", "backfill-dweller-names"])

    assert result.exit_code != 0
    assert "Either --vault or --all-active" in result.output
