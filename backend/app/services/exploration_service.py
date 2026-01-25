"""Exploration service for managing wasteland explorations.

This service provides a clean API for exploration operations and delegates to
the modular exploration system in services/exploration/ modules.
"""

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import exploration as crud_exploration
from app.crud.dweller import dweller as dweller_crud
from app.models.exploration import Exploration
from app.schemas.exploration import ExplorationProgress
from app.schemas.exploration_event import RewardsSchema
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.event_generator import event_generator


class ExplorationService:
    """Exploration service for managing wasteland explorations.

    This class provides a unified API for exploration operations and delegates
    to the modular exploration system in services/exploration/.
    """

    def generate_event(self, exploration: Exploration) -> dict | None:
        """Generate a random wasteland event.

        :param exploration: Active exploration
        :type exploration: Exploration
        :return: Event dict or None if no event should be generated
        :rtype: dict | None
        """
        return event_generator.generate_event(exploration)

    async def process_event(self, db_session: AsyncSession, exploration: Exploration) -> Exploration:
        """Process and add a generated event to an exploration.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration: Active exploration
        :type exploration: Exploration
        :return: Updated exploration
        :rtype: Exploration
        """
        return await exploration_coordinator.process_event(db_session, exploration)

    async def complete_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> dict:
        """Complete an exploration and return rewards summary.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :return: Rewards summary dict
        :rtype: dict
        """
        return await exploration_coordinator.complete_exploration(db_session, exploration_id)

    async def recall_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> dict:
        """Recall a dweller early from exploration.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :return: Rewards summary dict with reduced rewards
        :rtype: dict
        """
        return await exploration_coordinator.recall_exploration(db_session, exploration_id)

    async def send_dweller(  # noqa: PLR0913
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        dweller_id: UUID4,
        duration: int,
        stimpaks: int = 0,
        radaways: int = 0,
    ) -> Exploration:
        """Send a dweller to wasteland exploration.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param vault_id: Vault ID
        :type vault_id: UUID4
        :param dweller_id: Dweller ID
        :type dweller_id: UUID4
        :param duration: Exploration duration in hours
        :type duration: int
        :param stimpaks: Number of Stimpaks to bring, defaults to 0
        :type stimpaks: int
        :param radaways: Number of Radaways to bring, defaults to 0
        :type radaways: int
        :return: Created exploration
        :rtype: Exploration
        :raises ValueError: If dweller is already exploring or lacks supplies
        """
        existing = await crud_exploration.get_by_dweller(db_session, dweller_id=dweller_id)
        if existing:
            msg = "Dweller is already on an exploration"
            raise ValueError(msg)

        # Validate that stimpaks and radaways are non-negative
        if stimpaks < 0:
            msg = f"Stimpaks cannot be negative. Provided: {stimpaks}"
            raise ValueError(msg)
        if radaways < 0:
            msg = f"Radaways cannot be negative. Provided: {radaways}"
            raise ValueError(msg)

        dweller = await dweller_crud.get(db_session, dweller_id)
        if dweller.stimpack < stimpaks:
            msg = f"Dweller only has {dweller.stimpack} Stimpaks"
            raise ValueError(msg)
        if dweller.radaway < radaways:
            msg = f"Dweller only has {dweller.radaway} Radaways"
            raise ValueError(msg)

        return await crud_exploration.create_with_dweller_stats(
            db_session,
            vault_id=vault_id,
            dweller_id=dweller_id,
            duration=duration,
            stimpaks=stimpaks,
            radaways=radaways,
        )

    async def get_exploration_progress(self, db_session: AsyncSession, exploration_id: UUID4) -> ExplorationProgress:
        """Get current progress of an exploration.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :return: Exploration progress data
        :rtype: ExplorationProgress
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
            stimpaks=exploration.stimpaks,
            radaways=exploration.radaways,
        )

    async def complete_exploration_with_data(
        self, db_session: AsyncSession, exploration_id: UUID4
    ) -> tuple[Exploration, RewardsSchema]:
        """Complete exploration and return both exploration and rewards.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :return: Tuple of (exploration, rewards)
        :rtype: tuple[Exploration, RewardsSchema]
        :raises ValueError: If exploration cannot be completed
        """
        rewards = await exploration_coordinator.complete_exploration(db_session, exploration_id)
        exploration = await crud_exploration.get(db_session, exploration_id)
        return exploration, rewards

    async def recall_exploration_with_data(
        self, db_session: AsyncSession, exploration_id: UUID4
    ) -> tuple[Exploration, RewardsSchema]:
        """Recall dweller early and return both exploration and rewards.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :return: Tuple of (exploration, rewards)
        :rtype: tuple[Exploration, RewardsSchema]
        :raises ValueError: If exploration cannot be recalled
        """
        rewards = await exploration_coordinator.recall_exploration(db_session, exploration_id)
        exploration = await crud_exploration.get(db_session, exploration_id)
        return exploration, rewards

    async def process_event_for_exploration(self, db_session: AsyncSession, exploration_id: UUID4) -> Exploration:
        """Generate and process an event for an exploration.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :return: Updated exploration
        :rtype: Exploration
        :raises ValueError: If exploration is not active
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        if not exploration.is_active():
            msg = "Exploration is not active"
            raise ValueError(msg)

        return await exploration_coordinator.process_event(db_session, exploration)


exploration_service = ExplorationService()
