"""Tests for the retro-active bio place backfill script CLI."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from scripts.backfill_dweller_bio_places import MAX_DWELLERS, MAX_VAULTS, VAULT_ID
from scripts.backfill_dweller_bio_places import main as backfill_main

# ---------------------------------------------------------------------------
# main() integration tests (with mocks)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_main_defaults_to_project_vault() -> None:
    """When no vault is supplied, the script looks up the default project vault."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch("scripts.backfill_dweller_bio_places.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.bio_place_backfill_service.backfill_bio_places_for_vault",
            new_callable=AsyncMock,
        ) as mock_backfill_vault,
    ):
        vault_id = uuid4()
        mock_vault_get.return_value = type("Vault", (), {"id": vault_id})()
        mock_backfill_vault.return_value = 3

        result = await backfill_main()

        mock_vault_get.assert_awaited_once()
        call_args = mock_vault_get.call_args
        assert str(call_args[0][1]) == VAULT_ID
        mock_backfill_vault.assert_awaited_once_with(mock_session, vault_id, max_dwellers=MAX_DWELLERS)
        assert result == 3


@pytest.mark.asyncio
async def test_main_single_vault_delegates_to_service() -> None:
    """Single-vault mode delegates to BioPlaceBackfillService."""
    vault_id = uuid4()
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch("scripts.backfill_dweller_bio_places.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.bio_place_backfill_service.backfill_bio_places_for_vault",
            new_callable=AsyncMock,
        ) as mock_backfill_vault,
    ):
        mock_vault_get.return_value = type("Vault", (), {"id": vault_id})()
        mock_backfill_vault.return_value = 5

        result = await backfill_main(vault_uuid=str(vault_id), max_dwellers=10)

        mock_vault_get.assert_awaited_once_with(mock_session, vault_id)
        mock_backfill_vault.assert_awaited_once_with(mock_session, vault_id, max_dwellers=10)
        assert result == 5


@pytest.mark.asyncio
async def test_main_all_active_delegates_to_service() -> None:
    """--all-active mode delegates to BioPlaceBackfillService."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch(
            "scripts.backfill_dweller_bio_places.crud.vault.get",
            new_callable=AsyncMock,
        ) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.bio_place_backfill_service.backfill_bio_places_for_active_vaults",
            new_callable=AsyncMock,
        ) as mock_backfill_all,
    ):
        expected = {uuid4(): 2, uuid4(): 0}
        mock_backfill_all.return_value = expected

        result = await backfill_main(all_active=True, max_dwellers=50, max_vaults=10)

        mock_vault_get.assert_not_awaited()
        mock_backfill_all.assert_awaited_once_with(
            mock_session,
            max_dwellers_per_vault=50,
            max_vaults=10,
        )
        assert result == expected


@pytest.mark.asyncio
async def test_main_vault_not_found_graceful() -> None:
    """Non-existent vault UUID -> exits gracefully, no crash."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    with (
        patch("scripts.backfill_dweller_bio_places.async_session_maker", return_value=mock_session),
        patch("scripts.backfill_dweller_bio_places.crud.vault.get", new_callable=AsyncMock) as mock_vault_get,
        patch(
            "scripts.backfill_dweller_bio_places.bio_place_backfill_service.backfill_bio_places_for_vault",
            new_callable=AsyncMock,
        ) as mock_backfill_vault,
    ):
        mock_vault_get.return_value = None

        result = await backfill_main(vault_uuid=str(uuid4()), max_dwellers=MAX_DWELLERS)

        mock_backfill_vault.assert_not_awaited()
        assert result == 0
