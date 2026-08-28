"""Backfill missing discovery-unlock links."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlmodel import select

from app.crud.wasteland_location import wasteland_location as wl_crud
from app.models.exploration import Exploration
from app.models.vault import Vault
from app.models.wasteland_location import (
    DwellerLocation,
    DwellerLocationRelationEnum,
    LocationTypeEnum,
    WastelandLocation,
)

if TYPE_CHECKING:
    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class DiscoveryBackfillService:
    """Backfill missing discovery-unlock links for existing vaults."""

    async def unlock_discoveries_for_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> int:
        """Link every discovery location to the dweller who found it."""
        result = await db_session.execute(
            select(WastelandLocation).where(
                WastelandLocation.vault_id == vault_id,
                WastelandLocation.type == LocationTypeEnum.DISCOVERY,
                WastelandLocation.exploration_id.is_not(None),
            )
        )
        fixed = 0
        for location in result.scalars():
            exploration = await db_session.get(Exploration, location.exploration_id)
            if exploration is None:
                logger.warning("No exploration %s for location %s", location.exploration_id, location.name)
                continue

            existing = await db_session.execute(
                select(DwellerLocation).where(
                    DwellerLocation.dweller_id == exploration.dweller_id,
                    DwellerLocation.location_id == location.id,
                    DwellerLocation.relation == DwellerLocationRelationEnum.VISITED,
                )
            )
            was_locked = (link := existing.scalar_one_or_none()) is None or not link.is_unlocked
            await wl_crud.link_dweller(
                db_session,
                exploration.dweller_id,
                location.id,
                DwellerLocationRelationEnum.VISITED,
                is_unlocked=True,
            )
            if was_locked:
                fixed += 1

        return fixed

    async def unlock_discoveries_for_active_vaults(
        self,
        db_session: AsyncSession,
        *,
        max_vaults: int | None = None,
    ) -> dict[UUID4, int]:
        """Unlock discoveries in active vaults, ordered by creation date."""
        stmt = select(Vault).where(~Vault.is_deleted).order_by(Vault.created_at)
        if max_vaults is not None:
            stmt = stmt.limit(max_vaults)
        result = await db_session.execute(stmt)
        vaults = result.scalars().all()

        return {vault.id: await self.unlock_discoveries_for_vault(db_session, vault.id) for vault in vaults}


discovery_backfill_service = DiscoveryBackfillService()
