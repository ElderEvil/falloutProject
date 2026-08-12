"""Tests for the retro-active bio place backfill script CLI."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models.vault import Vault
from app.utils.exceptions import ResourceNotFoundException
from scripts.backfill_dweller_bio_places import MAX_DWELLERS, MAX_VAULTS
from scripts.backfill_dweller_bio_places import main as backfill_main

# ---------------------------------------------------------------------------
# main() integration tests (with mocks)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_main_requires_vault_or_all_active() -> None:
    """When no vault is supplied and --all-active is not set, the script raises an error."""
    with pytest.raises(ValueError, match="Either --vault or --all-active"):
        await backfill_main()


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
async def test_main_vault_not_found_raises() -> None:
    """Non-existent vault UUID -> raises a ValueError so the CLI exits non-zero."""
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
        vault_uuid = uuid4()
        mock_vault_get.side_effect = ResourceNotFoundException(Vault, vault_uuid)

        with pytest.raises(ValueError, match=r"Vault .* not found"):
            await backfill_main(vault_uuid=str(vault_uuid), max_dwellers=MAX_DWELLERS)

        mock_backfill_vault.assert_not_awaited()
