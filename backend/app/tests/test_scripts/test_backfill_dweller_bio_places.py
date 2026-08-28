"""Tests for the retro-active bio place backfill CLI command."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from app.cli.app.backfills import app as backfills_app
from app.cli.main import cli
from app.models.vault import Vault
from app.utils.exceptions import ResourceNotFoundException

runner = CliRunner()

# ---------------------------------------------------------------------------
# backfill-bio-places command tests (with mocks)
# ---------------------------------------------------------------------------


def test_command_requires_vault_or_all_active() -> None:
    """When no vault is supplied and --all-active is not set, the command exits non-zero."""
    result = runner.invoke(cli, ["backfill", "backfill-bio-places"])
    assert result.exit_code != 0
    assert "Either --vault or --all-active" in result.output


def test_command_single_vault_delegates_to_service() -> None:
    """Single-vault mode delegates to BioPlaceBackfillService."""
    vault_id = uuid4()

    with (
        patch("app.cli.app.backfills.async_session_maker", return_value=AsyncMock()),
        patch("app.cli.app.backfills.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "app.cli.app.backfills.bio_place_backfill_service.backfill_bio_places_for_vault",
            new_callable=AsyncMock,
        ) as mock_backfill_vault,
    ):
        mock_vault_get.return_value = type("Vault", (), {"id": vault_id})()
        mock_backfill_vault.return_value = 5

        result = runner.invoke(
            cli,
            ["backfill", "backfill-bio-places", "--vault", str(vault_id), "--max-dwellers", "10"],
        )

        assert result.exit_code == 0
        mock_vault_get.assert_awaited_once()
        mock_backfill_vault.assert_awaited_once()
        assert "Backfill complete: 5 dweller bio places registered" in result.output


def test_command_all_active_delegates_to_service() -> None:
    """--all-active mode delegates to BioPlaceBackfillService."""
    with (
        patch("app.cli.app.backfills.async_session_maker", return_value=AsyncMock()),
        patch(
            "app.cli.app.backfills.crud.vault.get",
            new_callable=AsyncMock,
        ) as mock_vault_get,
        patch(
            "app.cli.app.backfills.bio_place_backfill_service.backfill_bio_places_for_active_vaults",
            new_callable=AsyncMock,
        ) as mock_backfill_all,
    ):
        expected = {uuid4(): 2, uuid4(): 0}
        mock_backfill_all.return_value = expected

        result = runner.invoke(
            cli,
            ["backfill", "backfill-bio-places", "--all-active", "--max-dwellers", "50", "--max-vaults", "10"],
        )

        assert result.exit_code == 0
        mock_vault_get.assert_not_awaited()
        mock_backfill_all.assert_awaited_once()
        assert "Backfill complete: 2 dweller bio places registered across 2 vaults" in result.output


def test_command_vault_not_found_raises() -> None:
    """Non-existent vault UUID -> the command exits non-zero."""
    with (
        patch("app.cli.app.backfills.async_session_maker", return_value=AsyncMock()),
        patch("app.cli.app.backfills.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "app.cli.app.backfills.bio_place_backfill_service.backfill_bio_places_for_vault",
            new_callable=AsyncMock,
        ) as mock_backfill_vault,
    ):
        vault_uuid = uuid4()
        mock_vault_get.side_effect = ResourceNotFoundException(Vault, vault_uuid)

        result = runner.invoke(cli, ["backfill", "backfill-bio-places", "--vault", str(vault_uuid)])

        assert result.exit_code == 1
        assert "Vault" in result.output
        assert "not found" in result.output
        mock_backfill_vault.assert_not_awaited()


def test_backfills_app_has_command() -> None:
    """The backfill Typer app exposes the renamed command."""
    result = runner.invoke(backfills_app, ["--help"])
    assert result.exit_code == 0
    assert "backfill-bio-places" in result.output
