"""Retroactive discovery-unlock backfill service.

Links each DISCOVERY-type wasteland location to the dweller who found it
(exploration.dweller_id) with ``is_unlocked=True``. Discoveries created before
the discovery-unlock fix never created a dweller link, so they stayed locked on
the world map.
"""

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
    from collections.abc import Sequence

    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class DiscoveryBackfillService:
    """Backfill missing discovery-unlock links for existing vaults."""

    async def unlock_discoveries_for_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        *,
        locations: Sequence[WastelandLocation] | None = None,
    ) -> int:
        """Link every locked DISCOVERY location in a vault to its finding dweller.

        Pass *locations* to avoid a second query when the caller already loaded
        the vault's discovery rows (e.g. during an all-vault scan).
        """
        if locations is None:
            result = await db_session.execute(
                select(WastelandLocation).where(
                    WastelandLocation.vault_id == vault_id,
                    WastelandLocation.type == LocationTypeEnum.DISCOVERY,
                    WastelandLocation.exploration_id.is_not(None),
                )
            )
            locations = result.scalars().all()

        fixed = 0
        for location in locations:
            exploration = await db_session.get(Exploration, location.exploration_id)
            if exploration is None:
                logger.warning("No exploration %s for location %s", location.exploration_id, location.name)
                continue

            existing = (
                (
                    await db_session.execute(
                        select(DwellerLocation).where(
                            DwellerLocation.dweller_id == exploration.dweller_id,
                            DwellerLocation.location_id == location.id,
                            DwellerLocation.relation == DwellerLocationRelationEnum.VISITED,
                        )
                    )
                )
                .scalars()
                .first()
            )
            was_locked = existing is None or not existing.is_unlocked
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
        """Unlock discovery locations across all active (non-deleted) vaults.

        Returns a mapping of ``vault_id`` → number of locations unlocked.
        Vaults are ordered by creation date for deterministic runs.
        """
        stmt = select(Vault).where(~Vault.is_deleted).order_by(Vault.created_at)
        if max_vaults is not None:
            stmt = stmt.limit(max_vaults)
        result = await db_session.execute(stmt)
        vaults = result.scalars().all()

        counts: dict[UUID4, int] = {}
        for vault in vaults:
            counts[vault.id] = await self.unlock_discoveries_for_vault(db_session, vault.id)

        return counts


# Module-level singleton — matches the convention used by other services.
discovery_backfill_service = DiscoveryBackfillService()
