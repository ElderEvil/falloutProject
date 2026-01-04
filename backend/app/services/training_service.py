"""Training service for managing dweller SPECIAL stat training."""

import logging
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config.game_balance import (
    SPECIAL_STAT_MAX,
    TRAINING_BASE_DURATION_SECONDS,
    TRAINING_PER_LEVEL_INCREASE_SECONDS,
    TRAINING_TIER_MULTIPLIER,
)
from app.crud import training as training_crud
from app.crud.dweller import dweller as dweller_crud
from app.crud.room import room as room_crud
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.training import Training, TrainingStatus
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, VaultOperationException


class TrainingService:
    """Service for managing dweller training in training rooms."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def calculate_training_duration(current_stat: int, room_tier: int = 1) -> int:
        """
        Calculate training duration in seconds.

        Base: 2 hours (7200 seconds)
        Scaling: +30 minutes per current stat level
        Room tier reduces time: T2 = 75%, T3 = 60%

        Examples:
        - Stat 1→2: 2h (base)
        - Stat 5→6: 4.5h
        - Stat 9→10: 6.5h
        - Stat 9→10 (T3): 3.9h (6.5h * 0.6)

        Args:
            current_stat: Current SPECIAL stat value (1-10)
            room_tier: Training room tier (1-3)

        Returns:
            Duration in seconds
        """
        base_duration = TRAINING_BASE_DURATION_SECONDS
        per_level_increase = TRAINING_PER_LEVEL_INCREASE_SECONDS

        duration = base_duration + (current_stat * per_level_increase)

        # Apply tier multiplier
        tier_multiplier = TRAINING_TIER_MULTIPLIER.get(room_tier, 1.0)
        duration *= tier_multiplier

        return int(duration)

    async def can_start_training(  # noqa: PLR0911
        self,
        db_session: AsyncSession,
        dweller: Dweller,
        room: Room,
    ) -> tuple[bool, str]:
        """
        Check if dweller can start training in the given room.

        Args:
            db_session: Database session
            dweller: Dweller to train
            room: Training room

        Returns:
            (can_train: bool, reason: str)
        """
        # Check if room is a training room
        if room.category != RoomTypeEnum.TRAINING:
            return False, "Room is not a training room"

        # Check dweller availability
        if dweller.status != DwellerStatusEnum.IDLE:
            return False, f"Dweller is {dweller.status} and cannot train"

        existing_training = await training_crud.training.get_active_by_dweller(db_session, dweller.id)
        if existing_training:
            return False, f"Dweller is already training {existing_training.stat_being_trained}"

        # Determine which stat this room trains and check if maxed
        if not room.ability:
            return False, "Training room has no assigned SPECIAL stat"

        stat_to_train = room.ability
        current_stat_value = getattr(dweller, stat_to_train.value.lower())
        # Defensive: if stat is None (shouldn't happen), treat as 1 (minimum)
        current_stat_value = 1 if current_stat_value is None else current_stat_value

        if current_stat_value >= SPECIAL_STAT_MAX:
            return False, f"{stat_to_train.value} is already at maximum ({SPECIAL_STAT_MAX})"

        # Check room capacity
        # TODO: Capacity should be calculated based on room size: size/3*2 or similar formula
        active_trainees = await training_crud.training.get_active_by_room(db_session, room.id)
        if room.capacity is not None and len(active_trainees) >= room.capacity:
            return False, "Training room is at full capacity"

        return True, "Can start training"

    async def start_training(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        room_id: UUID4,
    ) -> Training:
        """
        Start training a dweller in a training room.

        Args:
            db_session: Database session
            dweller_id: Dweller to train
            room_id: Training room ID

        Returns:
            Created training session

        Raises:
            ResourceNotFoundException: If dweller or room not found
            VaultOperationException: If training cannot be started
            ResourceConflictException: If dweller already training
        """
        # Fetch dweller and room
        dweller = await dweller_crud.get(db_session, dweller_id)
        if not dweller:
            raise ResourceNotFoundException(model=Dweller, identifier=dweller_id)

        # Refresh to ensure all SPECIAL stats are loaded
        await db_session.refresh(dweller)

        room = await room_crud.get(db_session, room_id)
        if not room:
            raise ResourceNotFoundException(model=Room, identifier=room_id)

        # Validate can start training
        can_train, reason = await self.can_start_training(db_session, dweller, room)
        if not can_train:
            if "already training" in reason.lower():
                raise ResourceConflictException(detail=reason)
            raise VaultOperationException(detail=reason)

        # Get current stat value
        stat_to_train = room.ability
        current_stat_value = getattr(dweller, stat_to_train.value.lower())
        # Defensive: if stat is None (shouldn't happen), treat as 1 (minimum)
        if current_stat_value is None:
            self.logger.warning(f"Dweller {dweller.id} has None value for {stat_to_train.value}, using 1")
            current_stat_value = 1

        # Calculate duration
        duration_seconds = self.calculate_training_duration(current_stat_value, room.tier)

        # Create training session
        now = datetime.utcnow()
        training = Training(
            dweller_id=dweller.id,
            room_id=room.id,
            vault_id=dweller.vault_id,
            stat_being_trained=stat_to_train,
            current_stat_value=current_stat_value,
            target_stat_value=current_stat_value + 1,
            progress=0.0,
            started_at=now,
            estimated_completion_at=now + timedelta(seconds=duration_seconds),
            status=TrainingStatus.ACTIVE,
        )

        db_session.add(training)
        await db_session.commit()
        await db_session.refresh(training)

        # Update dweller status to TRAINING
        from app.schemas.dweller import DwellerUpdate

        await dweller_crud.update(
            db_session, dweller.id, DwellerUpdate(status=DwellerStatusEnum.TRAINING, room_id=room.id)
        )

        self.logger.info(
            f"Started training: Dweller {dweller.first_name} training {stat_to_train.value} "
            f"from {current_stat_value} to {current_stat_value + 1} ({duration_seconds}s)"
        )

        return training

    async def update_training_progress(
        self,
        db_session: AsyncSession,
        training: Training,
    ) -> Training:
        """
        Update training progress based on elapsed time.
        Auto-completes training if duration has elapsed.

        Args:
            db_session: Database session
            training: Training session to update

        Returns:
            Updated training session
        """
        if not training.is_active():
            return training

        now = datetime.utcnow()

        # Check if training is complete
        if now >= training.estimated_completion_at:
            return await self.complete_training(db_session, training.id)

        # Calculate progress
        total_duration = (training.estimated_completion_at - training.started_at).total_seconds()
        elapsed = (now - training.started_at).total_seconds()
        progress = min(1.0, elapsed / total_duration)

        # Update progress
        training.progress = progress
        db_session.add(training)
        await db_session.commit()
        await db_session.refresh(training)

        return training

    async def complete_training(
        self,
        db_session: AsyncSession,
        training_id: UUID4,
    ) -> Training:
        """
        Complete a training session and increase the dweller's SPECIAL stat.

        Args:
            db_session: Database session
            training_id: Training session ID

        Returns:
            Completed training session

        Raises:
            ResourceNotFoundException: If training not found
            VaultOperationException: If training not active
        """
        training = await training_crud.training.get(db_session, training_id)
        if not training:
            raise ResourceNotFoundException(model=Training, identifier=training_id)

        if not training.is_active():
            raise VaultOperationException(detail=f"Training is {training.status}, cannot complete")

        # Get dweller
        dweller = await dweller_crud.get(db_session, training.dweller_id)
        if not dweller:
            raise ResourceNotFoundException(model=Dweller, identifier=training.dweller_id)

        # Increase SPECIAL stat
        stat_name = training.stat_being_trained.value.lower()
        current_value = getattr(dweller, stat_name)
        new_value = min(current_value + 1, SPECIAL_STAT_MAX)

        setattr(dweller, stat_name, new_value)
        db_session.add(dweller)

        # Update training status
        training.status = TrainingStatus.COMPLETED
        training.completed_at = datetime.utcnow()
        training.progress = 1.0
        db_session.add(training)

        # Update dweller status back to IDLE and remove from room
        from app.schemas.dweller import DwellerUpdate

        await dweller_crud.update(db_session, dweller.id, DwellerUpdate(status=DwellerStatusEnum.IDLE, room_id=None))

        await db_session.commit()
        await db_session.refresh(training)

        self.logger.info(
            f"Completed training: Dweller {dweller.first_name} increased "
            f"{training.stat_being_trained.value} from {current_value} to {new_value}"
        )

        return training

    async def cancel_training(
        self,
        db_session: AsyncSession,
        training_id: UUID4,
    ) -> Training:
        """
        Cancel an active training session.
        Dweller does not gain the stat increase.

        Args:
            db_session: Database session
            training_id: Training session ID

        Returns:
            Cancelled training session

        Raises:
            ResourceNotFoundException: If training not found
            VaultOperationException: If training not active
        """
        training = await training_crud.training.get(db_session, training_id)
        if not training:
            raise ResourceNotFoundException(model=Training, identifier=training_id)

        if not training.is_active():
            raise VaultOperationException(detail=f"Training is {training.status}, cannot cancel")

        # Get dweller
        dweller = await dweller_crud.get(db_session, training.dweller_id)
        if not dweller:
            raise ResourceNotFoundException(model=Dweller, identifier=training.dweller_id)

        # Update training status
        training.status = TrainingStatus.CANCELLED
        training.completed_at = datetime.utcnow()
        db_session.add(training)

        # Update dweller status back to IDLE and remove from room
        from app.schemas.dweller import DwellerUpdate

        await dweller_crud.update(db_session, dweller.id, DwellerUpdate(status=DwellerStatusEnum.IDLE, room_id=None))

        await db_session.commit()
        await db_session.refresh(training)

        self.logger.info(
            f"Cancelled training: Dweller {dweller.first_name} stopped training {training.stat_being_trained.value}"
        )

        return training


# Singleton instance
training_service = TrainingService()
