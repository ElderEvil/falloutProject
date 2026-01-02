"""CRUD operations for training."""

from pydantic import UUID4
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.training import Training, TrainingStatus
from app.schemas.training import TrainingCreate, TrainingUpdate


class CRUDTraining(CRUDBase[Training, TrainingCreate, TrainingUpdate]):
    """CRUD operations for Training model."""

    async def get_active_by_dweller(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
    ) -> Training | None:
        """Get the active training session for a dweller."""
        result = await db_session.execute(
            select(Training).where(Training.dweller_id == dweller_id).where(Training.status == TrainingStatus.ACTIVE)
        )
        return result.scalar_one_or_none()

    async def get_active_by_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list[Training]:
        """Get all active training sessions in a vault."""
        result = await db_session.execute(
            select(Training).where(Training.vault_id == vault_id).where(Training.status == TrainingStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def get_active_by_room(
        self,
        db_session: AsyncSession,
        room_id: UUID4,
    ) -> list[Training]:
        """Get all active training sessions in a room."""
        result = await db_session.execute(
            select(Training).where(Training.room_id == room_id).where(Training.status == TrainingStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def get_by_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        status: TrainingStatus | None = None,
    ) -> list[Training]:
        """
        Get training sessions in a vault, optionally filtered by status.

        Args:
            db_session: Database session
            vault_id: Vault ID
            status: Optional status filter

        Returns:
            List of training sessions
        """
        query = select(Training).where(Training.vault_id == vault_id)

        if status:
            query = query.where(Training.status == status)

        result = await db_session.execute(query)
        return list(result.scalars().all())


training = CRUDTraining(Training)
