from __future__ import annotations

from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from typer.testing import CliRunner

from app.cli.backfills import app as backfills_app
from app.cli.main import cli

runner = CliRunner()


@contextmanager
def _cli(service_method: str):
    with ExitStack() as stack:
        stack.enter_context(patch("app.cli.backfills.async_session_maker", return_value=AsyncMock()))
        vault_get = stack.enter_context(patch("app.cli.backfills.crud.vault.get", new_callable=AsyncMock))
        backfill = stack.enter_context(
            patch(f"app.cli.backfills.bio_place_backfill_service.{service_method}", new_callable=AsyncMock)
        )
        yield vault_get, backfill


def test_command_requires_vault_or_all_active() -> None:
    result = runner.invoke(cli, ["backfill", "backfill-bio-places"])
    assert result.exit_code != 0
    assert "Either --vault or --all-active" in result.output


def test_command_single_vault_delegates_to_service() -> None:
    vault_id = uuid4()
    with _cli("backfill_bio_places_for_vault") as (mock_vault_get, mock_backfill):
        mock_vault_get.return_value = type("Vault", (), {"id": vault_id})()
        mock_backfill.return_value = 5
        result = runner.invoke(
            cli, ["backfill", "backfill-bio-places", "--vault", str(vault_id), "--max-dwellers", "10"]
        )
        assert result.exit_code == 0
        mock_vault_get.assert_awaited_once()
        mock_backfill.assert_awaited_once()
        assert "Backfill complete: 5 dweller bio places registered" in result.output


def test_command_all_active_delegates_to_service() -> None:
    with _cli("backfill_bio_places_for_active_vaults") as (mock_vault_get, mock_backfill_all):
        mock_backfill_all.return_value = {uuid4(): 2, uuid4(): 0}
        result = runner.invoke(
            cli,
            ["backfill", "backfill-bio-places", "--all-active", "--max-dwellers", "50", "--max-vaults", "10"],
        )
        assert result.exit_code == 0
        mock_vault_get.assert_not_awaited()
        mock_backfill_all.assert_awaited_once()
        assert "Backfill complete: 2 dweller bio places registered across 2 vaults" in result.output


def test_backfills_app_has_command() -> None:
    result = runner.invoke(backfills_app, ["--help"])
    assert result.exit_code == 0
    assert "backfill-bio-places" in result.output
