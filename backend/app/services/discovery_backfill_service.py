"""Backfill missing discovery-unlock links."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.enums import DwellerLocationRelationEnum
from app.crud.exploration import exploration as exploration_crud
from app.crud.world_location import world_location as wl_crud

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
        fixed = 0
        for location, state in await wl_crud.get_discovery_states(db_session, vault_id):
            exploration = (
                await exploration_crud.get_or_none(db_session, state.exploration_id)
                if state.exploration_id
                else None
            )
            if exploration is None:
                logger.warning("No exploration %s for location %s", state.exploration_id, location.name)
                continue

            link = await wl_crud.get_dweller_link(
                db_session, exploration.dweller_id, state.location_id, DwellerLocationRelationEnum.VISITED
            )
            was_locked = link is None or not link.is_unlocked
            await wl_crud.link_dweller(
                db_session,
                exploration.dweller_id,
                state.location_id,
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
        from app.crud.vault import vault as vault_crud

        vaults = await vault_crud.get_active_ordered(db_session, max_vaults)

        return {vault.id: await self.unlock_discoveries_for_vault(db_session, vault.id) for vault in vaults}


discovery_backfill_service = DiscoveryBackfillService()
