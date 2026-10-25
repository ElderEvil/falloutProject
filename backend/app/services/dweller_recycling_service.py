"""Dweller Recycling Service.

Manages the recycling of soft-deleted dwellers, allowing their
AI-generated content (names, bios, visual attributes) to be reused in new vaults.
"""

import logging
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, GenderEnum, RarityEnum
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException

logger = logging.getLogger(__name__)


class DwellerRecyclingService:
    """Service for recycling soft-deleted dwellers with AI-generated content."""

    @staticmethod
    async def get_recyclable_dwellers(
        db_session: AsyncSession,
        gender: GenderEnum | None = None,
        rarity: RarityEnum | None = None,
        min_age_days: int = 7,
        limit: int = 10,
    ) -> list[Dweller]:
        """Get soft-deleted dwellers older than min_age_days for recycling.

        Args:
            db_session: Database session
            gender: Optional gender filter
            rarity: Optional rarity filter
            min_age_days: Minimum days since deletion to be eligible for recycling
            limit: Maximum number of dwellers to return

        Returns:
            List of recyclable soft-deleted dwellers
        """
        cutoff_date = datetime.utcnow() - timedelta(days=min_age_days)

        return list(
            await crud.dweller.get_recyclable(
                db_session,
                gender=gender,
                rarity=rarity,
                deleted_before=cutoff_date,
                limit=limit,
            )
        )

    @staticmethod
    async def recycle_dweller_for_vault(
        db_session: AsyncSession,
        dweller_id: UUID4,
        target_vault_id: UUID4,
        reset_stats: bool = True,
    ) -> Dweller:
        """Restore a soft-deleted dweller to a new vault.

        Args:
            db_session: Database session
            dweller_id: ID of the soft-deleted dweller to recycle
            target_vault_id: ID of the vault to restore the dweller to
            reset_stats: If True, reset dweller stats to defaults

        Returns:
            The recycled/restored dweller

        Raises:
            ResourceNotFoundException: If dweller or vault not found
            ResourceConflictException: If dweller is not soft-deleted
        """
        # Verify target vault exists
        vault = await vault_crud.get(db_session, target_vault_id)
        if not vault:
            raise ResourceNotFoundException(Vault, identifier=target_vault_id)

        # Use SELECT ... FOR UPDATE to prevent race conditions
        dweller = await crud.dweller.get_for_update(db_session, dweller_id, include_deleted=True)

        if not dweller:
            raise ResourceNotFoundException(Dweller, identifier=dweller_id)

        if not dweller.is_deleted:
            raise ResourceConflictException(detail=f"Dweller {dweller_id} is not soft-deleted and cannot be recycled")

        # Restore the dweller (now safe due to row lock)
        dweller.restore()

        # Update vault assignment
        dweller.vault_id = target_vault_id
        dweller.room_id = None  # Always clear room_id when vault changes

        # Reset stats if requested
        if reset_stats:
            dweller.level = 1
            dweller.experience = 0
            dweller.health = dweller.max_health
            dweller.radiation = 0
            dweller.happiness = 50
            dweller.status = DwellerStatusEnum.IDLE
            dweller.stimpack = 0
            dweller.radaway = 0
            # Clear relationships
            dweller.partner_id = None
            dweller.parent_1_id = None
            dweller.parent_2_id = None

        db_session.add(dweller)
        await db_session.commit()
        await db_session.refresh(dweller)

        logger.info(
            "Recycled dweller %s to vault %s (reset_stats=%s)",
            dweller_id,
            target_vault_id,
            reset_stats,
        )

        return dweller


# Singleton instance
dweller_recycling_service = DwellerRecyclingService()
