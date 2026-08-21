"""Tests for the discovery-unlock backfill script."""

from __future__ import annotations

import pytest
from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.wasteland_location import DwellerLocation
from app.services.map_service import map_service
from scripts.backfill_unlock_discoveries import _unlock_discoveries_for_vault


@pytest.mark.asyncio
async def test_backfill_unlocks_discoveries_and_is_idempotent(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """First run unlocks every discovery; a second run changes nothing."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await async_session.refresh(exploration)

    location = await map_service.register_discovery(
        async_session, vault.id, exploration.id, dweller.id, "Abandoned Bunker"
    )
    assert location is not None

    # Simulate the pre-fix state: no dweller link on the DISCOVERY row.
    await async_session.execute(delete(DwellerLocation).where(DwellerLocation.location_id == location.id))
    await async_session.commit()

    first = await _unlock_discoveries_for_vault(async_session, vault.id)
    assert first >= 1

    second = await _unlock_discoveries_for_vault(async_session, vault.id)
    assert second == 0

    # The link is now unlocked.
    links = (
        (
            await async_session.execute(
                select(DwellerLocation).where(
                    DwellerLocation.location_id == location.id,
                    DwellerLocation.is_unlocked.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(links) == 1
