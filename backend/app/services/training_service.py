"""Training service for managing dweller SPECIAL stat training."""

import logging
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AgeGroupEnum, DwellerStatusEnum, RoomTypeEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud import training as training_crud
from app.crud.dweller import dweller as dweller_crud
from app.crud.room import room as room_crud
from app.crud.vault import vault as vault_crud
from app.models.base import SPECIALModel
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.training import Training, TrainingStatus
from app.options.pet_modifiers import MAX_PCT_BONUS, pet_modifiers_for
from app.services.notification_service import notification_service
from app.services.room_assignment_policy import calculate_room_capacity
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, VaultOperationException


class TrainingService:
    """Service for managing dweller training in training rooms."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def calculate_training_duration(current_stat: int, room_tier: int = 1) -> int:
        """Calculate training duration in seconds.

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
        base_duration = game_config.training.base_duration_seconds
        per_level_increase = game_config.training.per_level_increase_seconds

        duration = base_duration + (current_stat * per_level_increase)

        # Apply tier multiplier
        tier_multiplier = game_config.training.get_tier_multiplier(room_tier)
        duration *= tier_multiplier

        return int(duration)

    async def can_start_training(
        self,
        db_session: AsyncSession,
        dweller: Dweller,
        room: Room,
    ) -> tuple[bool, str]:
        """Check if dweller can start training in the given room.

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

        # Youth focus play, not SPECIAL drills (issue #1036 decision: training
        # is maturity-gated like equipment; apprenticeship #889 is the youth
        # learning path and is a separate mechanism). Elders are mature adults.
        if dweller.age_group in (AgeGroupEnum.CHILD, AgeGroupEnum.TEEN):
            return False, f"Only adult dwellers can train; {dweller.first_name} is still a {dweller.age_group.value}."

        # Check if dweller has an active training session
        existing_training = await training_crud.training.get_active_by_dweller(db_session, dweller.id)
        if existing_training:
            return False, f"Dweller is already training {existing_training.stat_being_trained}"

        # Check dweller availability (allow TRAINING status if no active session exists)
        if dweller.status not in (DwellerStatusEnum.IDLE, DwellerStatusEnum.TRAINING):
            return False, f"Dweller is {dweller.status} and cannot train"

        # Determine which stat this room trains and check if maxed
        if not room.ability:
            return False, "Training room has no assigned SPECIAL stat"

        stat_to_train = room.ability
        current_stat_value = SPECIALModel.get_stat(dweller, stat_to_train)

        if current_stat_value >= game_config.training.special_stat_max:
            return False, f"{stat_to_train.value} is already at maximum ({game_config.training.special_stat_max})"

        # Check room capacity
        # Calculate effective capacity: use explicit capacity or calculate from room size
        active_trainees = await training_crud.training.get_active_by_room(db_session, room.id)
        effective_capacity = room.capacity
        if effective_capacity is None and room.size is not None:
            # Calculate capacity based on room size: size/3*2 (minimum 1)
            effective_capacity = max(calculate_room_capacity(room.size), 1)
        if effective_capacity is not None and len(active_trainees) >= effective_capacity:
            return False, "Training room is at full capacity"

        return True, "Can start training"

    async def start_training(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        room_id: UUID4,
    ) -> Training:
        """Start training a dweller in a training room.

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
        await db_session.refresh(dweller, with_for_update=True)
        # refresh() expires relationship attributes, dropping the eager-loaded
        # pet; re-read so the training-speed snapshot below sees it (B7).
        dweller = await dweller_crud.get(db_session, dweller_id)

        room = await room_crud.get(db_session, room_id)
        if not room:
            raise ResourceNotFoundException(model=Room, identifier=room_id)

        # Validate can start training
        can_train, reason = await self.can_start_training(db_session, dweller, room)
        if not can_train:
            if "already training" in reason.lower():
                raise ResourceConflictException(detail=reason)
            raise VaultOperationException(detail=reason)

        training = self._new_training(dweller, room)
        db_session.add(training)

        # One transaction for the whole transition: the training row and the
        # dweller's assignment must land together or not at all.
        from app.schemas.dweller import DwellerUpdate

        await dweller_crud.update(
            db_session,
            dweller.id,
            DwellerUpdate(status=DwellerStatusEnum.TRAINING, room_id=room.id),
            commit=False,
        )
        await db_session.commit()
        await db_session.refresh(training)

        self.logger.info("Started training %s for dweller %s", training.id, dweller.id)

        return training

    def _new_training(self, dweller: Dweller, room: Room, goal_stat_value: int = 10) -> Training:
        """Snapshot the stat, room tier and equipped pet for one round."""
        if room.ability is None or dweller.vault_id is None:
            raise VaultOperationException(detail="Training requires a room stat and a dweller in a vault")
        current_stat = SPECIALModel.get_stat(dweller, room.ability)
        speed_bonus = min(pet_modifiers_for(dweller).training_speed_pct, MAX_PCT_BONUS)
        duration = int(self.calculate_training_duration(current_stat, room.tier) * (1 - speed_bonus))
        now = datetime.utcnow()
        return Training(
            dweller_id=dweller.id,
            room_id=room.id,
            vault_id=dweller.vault_id,
            stat_being_trained=room.ability,
            current_stat_value=current_stat,
            target_stat_value=current_stat + 1,
            goal_stat_value=goal_stat_value,
            started_at=now,
            estimated_completion_at=now + timedelta(seconds=duration),
        )

    async def _lock_active_training(
        self, db_session: AsyncSession, training_id: UUID4, operation: str
    ) -> tuple[Training, Dweller]:
        """Lock the dweller before the session, matching assignment write order."""
        training = await training_crud.training.get(db_session, training_id)
        if not training:
            raise ResourceNotFoundException(model=Training, identifier=training_id)
        dweller = await dweller_crud.get_for_update(db_session, training.dweller_id)
        if not dweller:
            raise ResourceNotFoundException(model=Dweller, identifier=training.dweller_id)
        training = await training_crud.training.get_for_update(db_session, training_id)
        if not training:
            raise ResourceNotFoundException(model=Training, identifier=training_id)
        if not training.is_active():
            raise VaultOperationException(detail=f"Training is {training.status}, cannot {operation}")
        return training, dweller

    async def _repeat_training(self, db_session: AsyncSession, training: Training, dweller: Dweller) -> Training | None:
        vault = await vault_crud.get(db_session, training.vault_id)
        if not vault or not vault.continuous_training or training.room_id is None:
            return None
        if SPECIALModel.get_stat(dweller, training.stat_being_trained) >= training.goal_stat_value:
            return None
        room = await room_crud.get(db_session, training.room_id)
        if not room or room.ability != training.stat_being_trained:
            return None
        can_train, _ = await self.can_start_training(db_session, dweller, room)
        if not can_train:
            return None
        # Refresh the equipped pet after locking; each round uses its current bonus.
        dweller = await dweller_crud.get(db_session, dweller.id)
        return self._new_training(dweller, room, training.goal_stat_value)

    async def set_training_goal(self, db_session: AsyncSession, training_id: UUID4, goal: int) -> Training:
        """Serialize goal edits with completion so a successor inherits the saved goal."""
        training, _ = await self._lock_active_training(db_session, training_id, "change goal")
        if not training.target_stat_value <= goal <= game_config.training.special_stat_max:
            raise VaultOperationException(detail=f"Training goal must be between {training.target_stat_value} and 10")
        training.goal_stat_value = goal
        db_session.add(training)
        await db_session.commit()
        await db_session.refresh(training)
        return training

    async def update_training_progress(
        self,
        db_session: AsyncSession,
        training: Training,
        dweller: Dweller | None = None,
    ) -> Training:
        """Update training progress based on elapsed time.
        Auto-completes training if duration has elapsed.

        Args:
            db_session: Database session
            training: Training session to update
            dweller: Optional pre-fetched dweller to avoid N+1 query

        Returns:
            Updated training session
        """
        if not training.is_active():
            return training

        now = datetime.utcnow()

        # Check if training is complete
        if now >= training.estimated_completion_at:
            return await self.complete_training(db_session, training.id, dweller=dweller)

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
        dweller: Dweller | None = None,
    ) -> Training:
        """Complete a training session and increase the dweller's SPECIAL stat.

        Args:
            db_session: Database session
            training_id: Training session ID
            dweller: Optional pre-fetched dweller to avoid N+1 query

        Returns:
            Completed training session

        Raises:
            ResourceNotFoundException: If training not found
            VaultOperationException: If training not active
        """
        training, dweller = await self._lock_active_training(db_session, training_id, "complete")
        if (
            training.room_id is None
            or dweller.room_id != training.room_id
            or dweller.status != DwellerStatusEnum.TRAINING
            or dweller.health <= 0
        ):
            return await self.cancel_training(db_session, training_id)

        # Increase SPECIAL stat
        stat_name = training.stat_being_trained.value.lower()
        current_value = SPECIALModel.get_stat(dweller, stat_name)
        new_value = min(current_value + 1, game_config.training.special_stat_max)

        SPECIALModel.set_stat(dweller, stat_name, new_value)
        db_session.add(dweller)

        # Update training status
        training.status = TrainingStatus.COMPLETED
        training.completed_at = datetime.utcnow()
        training.progress = 1.0
        db_session.add(training)

        # The completed round, stat gain and optional successor share one commit.
        await db_session.flush()
        next_round = await self._repeat_training(db_session, training, dweller)
        if next_round is not None:
            db_session.add(next_round)

        from app.schemas.dweller import DwellerUpdate

        if next_round is None:
            await dweller_crud.update(
                db_session, dweller.id, DwellerUpdate(status=DwellerStatusEnum.IDLE, room_id=None), commit=False
            )

        # One transaction: the stat, the session status, and the dweller's
        # release must land together or not at all.
        await db_session.commit()
        await db_session.refresh(training)
        await db_session.refresh(dweller)

        # Emit DWELLER_TRAINED event for objective tracking (after commit)
        await event_bus.emit(
            GameEvent.DWELLER_TRAINED,
            training.vault_id,
            {
                "dweller_id": str(dweller.id),
                "stat_trained": training.stat_being_trained.value,
                "new_value": new_value,
            },
        )

        # Send notification (non-critical, don't break completion on failure)
        await notification_service.notify_owner(
            db_session,
            training.vault_id,
            context=f"training_complete vault={training.vault_id} dweller={dweller.id}",
            sender=lambda user_id: notification_service.notify_training_complete(
                db_session,
                user_id=user_id,
                vault_id=training.vault_id,
                dweller_id=dweller.id,
                dweller_name=f"{dweller.first_name} {dweller.last_name or ''}".strip(),
                stat_name=training.stat_being_trained.value,
                meta_data={
                    "dweller_id": str(dweller.id),
                    "stat_name": training.stat_being_trained.value,
                    "old_value": current_value,
                    "new_value": new_value,
                    "training_continues": next_round is not None,
                    "goal_reached": new_value >= training.goal_stat_value,
                },
            ),
        )

        self.logger.info(
            f"Completed training: Dweller {dweller.first_name} increased "
            f"{training.stat_being_trained.value} from {current_value} to {new_value}"
        )

        return training

    async def cancel_training(
        self,
        db_session: AsyncSession,
        training_id: UUID4,
        dweller: Dweller | None = None,
        *,
        commit: bool = True,
    ) -> Training:
        """Cancel an active training session.
        Dweller does not gain the stat increase.

        Args:
            db_session: Database session
            training_id: Training session ID
            dweller: Optional pre-fetched dweller to avoid N+1 query
            commit: False lets room demolition commit cancellation and deletion together.

        Returns:
            Cancelled training session

        Raises:
            ResourceNotFoundException: If training not found
            VaultOperationException: If training not active
        """
        training, dweller = await self._lock_active_training(db_session, training_id, "cancel")

        # Update training status
        training.status = TrainingStatus.CANCELLED
        training.completed_at = datetime.utcnow()
        db_session.add(training)

        # Update dweller status back to IDLE and remove from room
        from app.schemas.dweller import DwellerUpdate

        if dweller.room_id == training.room_id and dweller.status == DwellerStatusEnum.TRAINING:
            await dweller_crud.update(
                db_session, dweller.id, DwellerUpdate(status=DwellerStatusEnum.IDLE, room_id=None), commit=False
            )

        # One transaction: the cancelled session and the dweller's release must
        # land together or not at all.
        if commit:
            await db_session.commit()
        else:
            await db_session.flush()
        await db_session.refresh(training)

        self.logger.info(
            f"Cancelled training: Dweller {dweller.first_name} stopped training {training.stat_being_trained.value}"
        )

        return training


# Singleton instance
training_service = TrainingService()
