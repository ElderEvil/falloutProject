"""
Dweller Recycling Service

Manages the recycling of soft-deleted dwellers, allowing their
AI-generated content (names, bios, visual attributes) to be reused in new vaults.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import DwellerStatusEnum, GenderEnum, RarityEnum
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
        cutoff_date = datetime.now(UTC) - timedelta(days=min_age_days)

        query = (
            select(Dweller)
            .where(col(Dweller.is_deleted).is_(True))
            .where(col(Dweller.deleted_at) <= cutoff_date)
            .order_by(col(Dweller.deleted_at).desc())
            .limit(limit)
        )

        if gender:
            query = query.where(Dweller.gender == gender)

        if rarity:
            query = query.where(Dweller.rarity == rarity)

        response = await db_session.exec(query)
        return list(response.all())

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
        query = select(Dweller).where(Dweller.id == dweller_id).with_for_update()
        response = await db_session.exec(query)
        dweller = response.one_or_none()

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

    @staticmethod
    async def bulk_recycle_dwellers(
        db_session: AsyncSession,
        target_vault_id: UUID4,
        count: int = 5,
        gender: GenderEnum | None = None,
        rarity: RarityEnum | None = None,
        reset_stats: bool = True,
    ) -> list[Dweller]:
        """Recycle multiple dwellers for a vault.

        Args:
            db_session: Database session
            target_vault_id: ID of the vault to restore dwellers to
            count: Number of dwellers to recycle
            gender: Optional gender filter
            rarity: Optional rarity filter
            reset_stats: If True, reset dweller stats to defaults

        Returns:
            List of recycled dwellers

        Raises:
            ResourceNotFoundException: If vault not found
        """
        # Verify target vault exists
        vault = await vault_crud.get(db_session, target_vault_id)
        if not vault:
            raise ResourceNotFoundException(Vault, identifier=target_vault_id)

        # Get recyclable dwellers
        recyclable = await DwellerRecyclingService.get_recyclable_dwellers(
            db_session=db_session,
            gender=gender,
            rarity=rarity,
            limit=count,
        )

        recycled_dwellers: list[Dweller] = []

        for dweller in recyclable:
            try:
                recycled = await DwellerRecyclingService.recycle_dweller_for_vault(
                    db_session=db_session,
                    dweller_id=dweller.id,
                    target_vault_id=target_vault_id,
                    reset_stats=reset_stats,
                )
                recycled_dwellers.append(recycled)
            except ResourceConflictException:
                # Skip if dweller is no longer deleted (race condition)
                logger.warning("Dweller %s is no longer soft-deleted, skipping", dweller.id)
                continue

        logger.info(
            "Bulk recycled %d dwellers to vault %s (requested %d)",
            len(recycled_dwellers),
            target_vault_id,
            count,
        )

        return recycled_dwellers

    @staticmethod
    async def permanently_delete_old_dwellers(
        db_session: AsyncSession,
        days_threshold: int = 90,
        batch_size: int = 100,
    ) -> int:
        """Hard delete dwellers older than threshold.

        Args:
            db_session: Database session
            days_threshold: Delete dwellers deleted more than this many days ago
            batch_size: Maximum number of dwellers to delete in one operation

        Returns:
            Number of dwellers permanently deleted
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days_threshold)

        deleted_count = 0

        while True:
            query = (
                select(Dweller)
                .where(col(Dweller.is_deleted).is_(True))
                .where(col(Dweller.deleted_at) <= cutoff_date)
                .limit(batch_size)
            )

            response = await db_session.exec(query)
            dwellers_to_delete = response.all()

            if not dwellers_to_delete:
                break

            for dweller in dwellers_to_delete:
                await db_session.delete(dweller)
                deleted_count += 1

            await db_session.commit()

        if deleted_count > 0:
            logger.info(
                "Permanently deleted %d dwellers total (older than %d days)",
                deleted_count,
                days_threshold,
            )

        return deleted_count

    @staticmethod
    async def get_recycling_stats(db_session: AsyncSession) -> dict[str, Any]:
        """Return stats about recyclable dwellers.

        Args:
            db_session: Database session

        Returns:
            Dictionary with recycling statistics
        """
        now = datetime.now(UTC)

        total_deleted_query = select(func.count()).where(col(Dweller.is_deleted).is_(True))
        total_deleted_result = await db_session.exec(total_deleted_query)
        total_deleted = total_deleted_result.one()

        week_ago = now - timedelta(days=7)
        eligible_query = (
            select(func.count()).where(col(Dweller.is_deleted).is_(True)).where(col(Dweller.deleted_at) <= week_ago)
        )
        eligible_result = await db_session.exec(eligible_query)
        eligible_count = eligible_result.one()

        ninety_days_ago = now - timedelta(days=90)
        permanent_eligible_query = (
            select(func.count())
            .where(col(Dweller.is_deleted).is_(True))
            .where(col(Dweller.deleted_at) <= ninety_days_ago)
        )
        permanent_eligible_result = await db_session.exec(permanent_eligible_query)
        permanent_eligible_count = permanent_eligible_result.one()

        gender_query = (
            select(Dweller.gender, func.count()).where(col(Dweller.is_deleted).is_(True)).group_by(Dweller.gender)
        )
        gender_result = await db_session.exec(gender_query)
        gender_counts = {str(g): c for g, c in gender_result.all()}

        rarity_query = (
            select(Dweller.rarity, func.count()).where(col(Dweller.is_deleted).is_(True)).group_by(Dweller.rarity)
        )
        rarity_result = await db_session.exec(rarity_query)
        rarity_counts = {str(r): c for r, c in rarity_result.all()}

        oldest_query = select(func.min(Dweller.deleted_at)).where(col(Dweller.is_deleted).is_(True))
        oldest_result = await db_session.exec(oldest_query)
        oldest_deleted_at = oldest_result.one_or_none()

        return {
            "total_soft_deleted": total_deleted,
            "eligible_for_recycling": eligible_count,
            "eligible_for_permanent_deletion": permanent_eligible_count,
            "by_gender": gender_counts,
            "by_rarity": rarity_counts,
            "oldest_deleted_at": oldest_deleted_at.isoformat() if oldest_deleted_at else None,
        }


# Singleton instance
dweller_recycling_service = DwellerRecyclingService()
