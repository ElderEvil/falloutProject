"""CRUD operations for training."""

from pydantic import UUID4
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.dweller import Dweller
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

    async def get_dwellers_for_trainings(
        self,
        db_session: AsyncSession,
        training_sessions: list[Training],
    ) -> dict[UUID4, Dweller]:
        """
        Batch-fetch dwellers for multiple training sessions.

        Args:
            db_session: Database session
            training_sessions: List of training sessions

        Returns:
            Dictionary mapping dweller_id to Dweller object
        """
        if not training_sessions:
            return {}

        dweller_ids = {training.dweller_id for training in training_sessions}

        result = await db_session.execute(select(Dweller).where(Dweller.id.in_(dweller_ids)))
        dwellers = result.scalars().all()

        return {dweller.id: dweller for dweller in dwellers}


training = CRUDTraining(Training)
