"""Exploration service for managing wasteland explorations.

This service provides a clean API for exploration operations and delegates to
the modular exploration system in services/exploration/ modules.
"""

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import exploration as crud_exploration
from app.models.exploration import Exploration
from app.schemas.exploration import ExplorationProgress
from app.schemas.exploration_event import RewardsSchema
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.event_generator import event_generator


class ExplorationService:
    """
    Exploration service for managing wasteland explorations.

    This class provides a unified API for exploration operations and delegates to
    the modular exploration system in services/exploration/.
    """

    def generate_event(self, exploration: Exploration) -> dict | None:
        """
        Generate a random wasteland event.

        Args:
            exploration: Active exploration

        Returns:
            Event dict or None if no event should be generated
        """
        return event_generator.generate_event(exploration)

    async def process_event(self, db_session: AsyncSession, exploration: Exploration) -> Exploration:
        """
        Process and add a generated event to an exploration.

        Args:
            db_session: Database session
            exploration: Active exploration

        Returns:
            Updated exploration
        """
        return await exploration_coordinator.process_event(db_session, exploration)

    async def complete_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> dict:
        """
        Complete an exploration and return rewards summary.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            Rewards summary dict
        """
        return await exploration_coordinator.complete_exploration(db_session, exploration_id)

    async def recall_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> dict:
        """
        Recall a dweller early from exploration.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            Rewards summary dict with reduced rewards
        """
        return await exploration_coordinator.recall_exploration(db_session, exploration_id)

    async def send_dweller(
        self, db_session: AsyncSession, vault_id: UUID4, dweller_id: UUID4, duration: int
    ) -> Exploration:
        """
        Send a dweller to wasteland exploration.

        Args:
            db_session: Database session
            vault_id: Vault ID
            dweller_id: Dweller ID
            duration: Exploration duration in hours

        Returns:
            Created exploration

        Raises:
            ValueError: If dweller is already on an active exploration
        """
        # Check if dweller is already on an active exploration
        existing_exploration = await crud_exploration.get_by_dweller(db_session, dweller_id=dweller_id)

        if existing_exploration:
            raise ValueError("Dweller is already on an exploration")  # noqa: EM101, TRY003

        # Create new exploration with dweller's current stats
        return await crud_exploration.create_with_dweller_stats(
            db_session,
            vault_id=vault_id,
            dweller_id=dweller_id,
            duration=duration,
        )

    async def get_exploration_progress(self, db_session: AsyncSession, exploration_id: UUID4) -> ExplorationProgress:
        """
        Get current progress of an exploration.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            Exploration progress data
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        return ExplorationProgress(
            id=exploration.id,
            status=exploration.status,
            progress_percentage=exploration.progress_percentage(),
            time_remaining_seconds=exploration.time_remaining_seconds(),
            elapsed_time_seconds=exploration.elapsed_time_seconds(),
            events=exploration.events,
            loot_collected=exploration.loot_collected,
        )

    async def complete_exploration_with_data(
        self, db_session: AsyncSession, exploration_id: UUID4
    ) -> tuple[Exploration, RewardsSchema]:
        """
        Complete an exploration and return both exploration and rewards.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            Tuple of (exploration, rewards)

        Raises:
            ValueError: If exploration cannot be completed
        """
        rewards = await exploration_coordinator.complete_exploration(db_session, exploration_id)
        exploration = await crud_exploration.get(db_session, exploration_id)
        return exploration, rewards

    async def recall_exploration_with_data(
        self, db_session: AsyncSession, exploration_id: UUID4
    ) -> tuple[Exploration, RewardsSchema]:
        """
        Recall a dweller early and return both exploration and rewards.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            Tuple of (exploration, rewards)

        Raises:
            ValueError: If exploration cannot be recalled
        """
        rewards = await exploration_coordinator.recall_exploration(db_session, exploration_id)
        exploration = await crud_exploration.get(db_session, exploration_id)
        return exploration, rewards

    async def process_event_for_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> Exploration:
        """
        Generate and process an event for an exploration.

        Args:
            db_session: Database session
            exploration_id: Exploration ID

        Returns:
            Updated exploration

        Raises:
            ValueError: If exploration is not active
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        if not exploration.is_active():
            raise ValueError("Exploration is not active")  # noqa: EM101, TRY003

        return await exploration_coordinator.process_event(db_session, exploration)


# Singleton instance
exploration_service = ExplorationService()
