"""Exploration service for managing wasteland explorations.

This service provides a clean API for exploration operations and delegates to
the modular exploration system in services/exploration/ modules.
"""

from datetime import datetime

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import exploration as crud_exploration
from app.crud.dweller import dweller as dweller_crud
from app.crud.storage import storage as crud_storage
from app.models.exploration import Exploration, ExplorationStatus
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum
from app.schemas.dweller import DwellerUpdate
from app.schemas.exploration import ExplorationProgress
from app.schemas.exploration_event import RewardsSchema
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.event_generator import event_generator
from app.services.exploration.event_service import event_service


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
        return await event_service.process_event(db_session, exploration)

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

    async def send_dweller(
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

        # Check vault storage first, then fall back to dweller inventory
        storage = await crud_storage.get_by_vault(db_session, vault_id)
        vault_stimpaks = storage.stimpack if storage else 0
        vault_radaways = storage.radaway if storage else 0

        # Get total available (vault + dweller)
        dweller = await dweller_crud.get(db_session, dweller_id)
        if dweller.vault_id != vault_id:
            raise ValueError("Dweller does not belong to this vault")
        if not dweller.is_adult or dweller.age_group != AgeGroupEnum.ADULT:
            raise ValueError("Children cannot be sent on exploration")
        dweller_stimpaks = dweller.stimpack or 0
        dweller_radaways = dweller.radaway or 0
        total_stimpaks = vault_stimpaks + dweller_stimpaks
        total_radaways = vault_radaways + dweller_radaways

        if stimpaks > total_stimpaks:
            msg = f"Total available stimpaks: {total_stimpaks}"
            raise ValueError(msg)
        if radaways > total_radaways:
            msg = f"Total available radaways: {total_radaways}"
            raise ValueError(msg)

        # Departure and room removal must be committed together so a failed
        # dispatch never leaves the dweller unexpectedly unassigned.
        dweller.room_id = None
        db_session.add(dweller)

        # Calculate how much to take from vault vs dweller
        stimpaks_from_vault = min(stimpaks, vault_stimpaks)
        stimpaks_from_dweller = stimpaks - stimpaks_from_vault

        radaways_from_vault = min(radaways, vault_radaways)
        radaways_from_dweller = radaways - radaways_from_vault

        # Deduct from vault storage
        if (stimpaks_from_vault > 0 or radaways_from_vault > 0) and storage:
            storage.stimpack = (storage.stimpack or 0) - stimpaks_from_vault
            storage.radaway = (storage.radaway or 0) - radaways_from_vault
            db_session.add(storage)

        # Deduct from dweller inventory
        if stimpaks_from_dweller > 0 or radaways_from_dweller > 0:
            new_dweller_stimpaks = (dweller.stimpack or 0) - stimpaks_from_dweller
            new_dweller_radaways = (dweller.radaway or 0) - radaways_from_dweller
            await dweller_crud.update(
                db_session,
                dweller_id,
                obj_in={"stimpack": new_dweller_stimpaks, "radaway": new_dweller_radaways},
                commit=False,
            )

        # Total supplies for exploration
        total_stimpaks = stimpaks_from_vault + stimpaks_from_dweller
        total_radaways = radaways_from_vault + radaways_from_dweller

        exploration = Exploration(
            vault_id=vault_id,
            dweller_id=dweller_id,
            duration=duration,
            stimpaks=total_stimpaks,
            radaways=total_radaways,
            dweller_strength=dweller.strength,
            dweller_perception=dweller.perception,
            dweller_endurance=dweller.endurance,
            dweller_charisma=dweller.charisma,
            dweller_intelligence=dweller.intelligence,
            dweller_agility=dweller.agility,
            dweller_luck=dweller.luck,
            start_time=datetime.utcnow(),
            status=ExplorationStatus.ACTIVE,
        )
        db_session.add(exploration)

        await dweller_crud.update(
            db_session,
            dweller_id,
            DwellerUpdate(status=DwellerStatusEnum.EXPLORING),
            commit=False,
        )

        await db_session.commit()
        await db_session.refresh(exploration)
        return exploration

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

        return await event_service.process_event(db_session, exploration)


exploration_service = ExplorationService()
