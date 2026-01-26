"""
Dweller Recycling Service (NOT YET IMPLEMENTED)

TODO: This service will manage the recycling of soft-deleted dwellers, allowing their
AI-generated content (names, bios, visual attributes) to be reused in new vaults.

This is planned for a future update. For now, only soft delete functionality is implemented.
"""

from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.dweller import Dweller
from app.schemas.common import GenderEnum, RarityEnum


class DwellerRecyclingService:
    """Service for recycling soft-deleted dwellers with AI-generated content. (NOT YET IMPLEMENTED)"""

    @staticmethod
    async def get_recyclable_dwellers(
        db_session: AsyncSession,
        gender: GenderEnum | None = None,
        rarity: RarityEnum | None = None,
        min_age_days: int = 7,
        limit: int = 10,
    ) -> list[Dweller]:
        """NOT YET IMPLEMENTED"""
        raise NotImplementedError("Dweller recycling is not yet implemented")

    @staticmethod
    async def recycle_dweller_for_vault(
        db_session: AsyncSession,
        dweller_id: UUID4,
        target_vault_id: UUID4,
        reset_stats: bool = True,
    ) -> Dweller:
        """NOT YET IMPLEMENTED"""
        raise NotImplementedError("Dweller recycling is not yet implemented")

    @staticmethod
    async def bulk_recycle_dwellers(
        db_session: AsyncSession,
        target_vault_id: UUID4,
        count: int = 5,
        gender: GenderEnum | None = None,
        rarity: RarityEnum | None = None,
        reset_stats: bool = True,
    ) -> list[Dweller]:
        """NOT YET IMPLEMENTED"""
        raise NotImplementedError("Dweller recycling is not yet implemented")

    @staticmethod
    async def permanently_delete_old_dwellers(
        db_session: AsyncSession,
        days_threshold: int = 90,
        batch_size: int = 100,
    ) -> int:
        """NOT YET IMPLEMENTED"""
        raise NotImplementedError("Dweller recycling is not yet implemented")

    @staticmethod
    async def get_recycling_stats(db_session: AsyncSession) -> dict[str, Any]:
        """NOT YET IMPLEMENTED"""
        raise NotImplementedError("Dweller recycling is not yet implemented")


# Singleton instance
dweller_recycling_service = DwellerRecyclingService()
