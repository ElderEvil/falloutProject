from __future__ import annotations

import pytest
from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.world_location import DwellerLocation
from app.services.discovery_backfill_service import discovery_backfill_service
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service


async def test_backfill_unlocks_discoveries_and_is_idempotent(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await async_session.refresh(exploration)
    location = await map_service.register_discovery(
        async_session, vault.id, exploration.id, dweller.id, "Abandoned Bunker"
    )
    assert location is not None
    # Simulate the pre-fix state: no dweller link on the DISCOVERY row.
    await async_session.execute(delete(DwellerLocation).where(DwellerLocation.location_id == location.id))
    await async_session.commit()
    assert await discovery_backfill_service.unlock_discoveries_for_vault(async_session, vault.id) >= 1
    assert await discovery_backfill_service.unlock_discoveries_for_vault(async_session, vault.id) == 0
    links = (
        (
            await async_session.execute(
                select(DwellerLocation).where(
                    DwellerLocation.location_id == location.id, DwellerLocation.is_unlocked.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(links) == 1
