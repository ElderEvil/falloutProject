"""Exploration service for managing wasteland explorations.

This service provides a clean API for exploration operations and delegates to
the modular exploration system in services/exploration/ modules.
"""

import math
from collections.abc import Sequence
from datetime import datetime

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerStatusEnum
from app.core.game_config import game_config
from app.crud import exploration as crud_exploration
from app.crud import training as training_crud
from app.crud import world_location as crud_world_location
from app.crud.dweller import dweller as dweller_crud
from app.crud.storage import storage as crud_storage
from app.models.dweller import Dweller
from app.models.exploration import Exploration, ExplorationStatus
from app.models.team import Team, TeamMember
from app.models.training import TrainingStatus
from app.models.world_location import WorldLocation
from app.schemas.dweller import DwellerUpdate
from app.schemas.exploration import ExplorationProgress
from app.schemas.exploration_event import ExplorationEvent, RewardsSchema
from app.services.exploration.coordinator import ERROR_NOT_ACTIVE, exploration_coordinator
from app.services.exploration.event_generator import event_generator
from app.services.exploration.event_service import event_service
from app.services.user_service import user_service
from app.utils.dweller_availability import availability_error
from app.utils.exceptions import ResourceNotFoundException, ValidationException
from app.utils.place_groups import get_place_group

#: The vault home point in the registry's 0..100 coordinate space.
VAULT_HOME_POINT = (50.0, 50.0)


def dispatch_travel_hours(distance: float) -> int:
    """Whole-hour travel time for a dispatch to a map point (issue 772).

    Travel is quantized to whole hours: the base travel time plus a per-unit
    distance cost, rounded up, and clamped to the exploration duration bounds.
    """
    cfg = game_config.exploration.dispatch
    total_hours = cfg.base_travel_hours + cfg.travel_hours_per_unit * distance
    return max(1, min(24, math.ceil(total_hours)))


class ExplorationService:
    """Exploration service for managing wasteland explorations.

    This class provides a unified API for exploration operations and delegates
    to the modular exploration system in services/exploration/.
    """

    def generate_event(self, exploration: Exploration) -> ExplorationEvent | None:
        """Generate a random wasteland event.

        :param exploration: Active exploration
        :type exploration: Exploration
        :return: Generated event schema, or None when no event fires
        :rtype: ExplorationEvent | None
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

    async def start_return(
        self, db_session: AsyncSession, exploration_id: UUID4, *, recalled: bool = False
    ) -> Exploration:
        """Send a dweller home; rewards and loot wait until the return leg finishes.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :param recalled: True for a player-initiated early recall, defaults to False
        :type recalled: bool
        :return: The exploration now in RETURNING state
        :rtype: Exploration
        """
        return await exploration_coordinator.start_return(db_session, exploration_id, recalled=recalled)

    async def finalize_return(self, db_session: AsyncSession, exploration_id: UUID4) -> RewardsSchema:
        """Finalize an exploration whose dweller has arrived home.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :return: Rewards summary
        :rtype: RewardsSchema
        """
        return await exploration_coordinator.finalize_return(db_session, exploration_id)

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
        reason = availability_error(dweller, require_healthy=True)
        if reason is not None:
            raise ValueError(reason)
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
        # Leaving the vault also ends any active training session (mirrors the
        # room-change cancellation in DwellerService.update_dweller, but staged
        # here without committing so dispatch stays atomic).
        active_training = await training_crud.training.get_active_by_dweller(db_session, dweller_id)
        if active_training is not None:
            active_training.status = TrainingStatus.CANCELLED
            active_training.completed_at = datetime.utcnow()
            db_session.add(active_training)

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
        return await self._persist_departure(db_session, vault_id=vault_id, dwellers=[dweller], exploration=exploration)

    async def _persist_departure(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID4,
        dwellers: Sequence[Dweller],
        exploration: Exploration,
    ) -> Exploration:
        """Shared departure tail: clear rooms, mark EXPLORING, commit, record statistic.

        Used by both free-roam sends (one dweller) and targeted dispatches (a party)
        so departure bookkeeping stays in one place. The caller stages the
        exploration (and any team roster) first; this commits everything once.
        """
        # Room clearing goes through CRUD: direct assignment trips the ORM type contract.
        for dweller in dwellers:
            await dweller_crud.update(db_session, dweller.id, {"room_id": None}, commit=False)
        db_session.add(exploration)

        for dweller in dwellers:
            await dweller_crud.update(
                db_session,
                dweller.id,
                DwellerUpdate(status=DwellerStatusEnum.EXPLORING),
                commit=False,
            )

        await db_session.commit()
        await db_session.refresh(exploration)
        await user_service.record_vault_statistic(db_session, vault_id, "total_explorations")
        return exploration

    async def dispatch(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        dweller_ids: list[UUID4],
        location_id: UUID4,
    ) -> Exploration:
        """Send a party to clear a specific map point (issue 772).

        A targeted run travels for a whole number of hours based on the distance
        from the vault home point, suppresses random events, and resolves exactly
        once on arrival (see ``dispatch_resolution.resolve_dispatch_arrival``).
        The party has no leader: ``dweller_ids[0]`` is only the anchor that keeps
        the non-nullable ``Exploration.dweller_id`` FK working.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param vault_id: Vault ID
        :type vault_id: UUID4
        :param dweller_ids: Party of 1 to ``max_party_size`` dweller IDs
        :type dweller_ids: list[UUID4]
        :param location_id: Target world-location ID
        :type location_id: UUID4
        :return: Created exploration
        :rtype: Exploration
        :raises ResourceNotFoundException: If a dweller or the location is unknown
        :raises ValidationException: If a dweller cannot go or the point cannot be cleared
        """
        max_party_size = game_config.exploration.dispatch.max_party_size
        if not dweller_ids:
            raise ValidationException("Party must include at least one dweller")
        if len(set(dweller_ids)) != len(dweller_ids):
            raise ValidationException("Choose each dweller only once")
        if len(dweller_ids) > max_party_size:
            raise ValidationException(f"Party size must be 1-{max_party_size}")

        in_progress = await crud_exploration.get_in_progress_for_dwellers(db_session, dweller_ids)
        if in_progress:
            raise ValidationException("Dweller is already on an exploration")

        dwellers: list[Dweller] = []
        for dweller_id in dweller_ids:
            dweller = await dweller_crud.get(db_session, dweller_id)
            if dweller.vault_id != vault_id:
                raise ValidationException("Dweller does not belong to this vault")
            reason = availability_error(dweller, require_healthy=True)
            if reason is not None:
                raise ValidationException(reason)
            dwellers.append(dweller)

        pair = await crud_world_location.get_state_with_location(db_session, vault_id, location_id)
        if pair is None:
            raise ResourceNotFoundException(WorldLocation, identifier=location_id)
        location, state = pair

        group = get_place_group(location.group_key)
        if group is None or not group.get("clearable"):
            raise ValidationException("This location cannot be cleared")

        if not state.is_dispatchable(datetime.utcnow()):
            raise ValidationException("This location is currently cleared")

        distance = math.dist(VAULT_HOME_POINT, (location.coord_x, location.coord_y))
        duration = dispatch_travel_hours(distance)
        tier = min(state.clear_count, game_config.exploration.dispatch.escalation_cap)
        anchor = dwellers[0]

        exploration = Exploration(
            vault_id=vault_id,
            dweller_id=anchor.id,
            duration=duration,
            stimpaks=0,
            radaways=0,
            dweller_strength=anchor.strength,
            dweller_perception=anchor.perception,
            dweller_endurance=anchor.endurance,
            dweller_charisma=anchor.charisma,
            dweller_intelligence=anchor.intelligence,
            dweller_agility=anchor.agility,
            dweller_luck=anchor.luck,
            target_location_id=location_id,
            clear_tier=tier,
            start_time=datetime.utcnow(),
            status=ExplorationStatus.ACTIVE,
        )
        db_session.add(exploration)
        await db_session.flush()

        team = Team(vault_id=vault_id, exploration_id=exploration.id)
        team.members = []
        db_session.add(team)
        await db_session.flush()
        for slot, dweller in enumerate(dwellers, start=1):
            db_session.add(TeamMember(team_id=team.id, dweller_id=dweller.id, slot_number=slot, status="assigned"))
        exploration.team_id = team.id
        return await self._persist_departure(db_session, vault_id=vault_id, dwellers=dwellers, exploration=exploration)

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
            return_completes_at=exploration.return_completes_at,
            return_time_remaining_seconds=exploration.return_time_remaining_seconds(),
            events=exploration.events,
            loot_collected=exploration.loot_collected,
            stimpaks=exploration.stimpaks,
            radaways=exploration.radaways,
        )

    async def complete_exploration_with_data(
        self, db_session: AsyncSession, exploration_id: UUID4
    ) -> tuple[Exploration, RewardsSchema | None]:
        """Advance a finished exploration: start the return leg, or finalize once home.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :return: Tuple of (exploration, rewards); rewards are None while the dweller is still returning
        :rtype: tuple[Exploration, RewardsSchema | None]
        :raises ValueError: If exploration cannot be advanced
        """
        exploration = await crud_exploration.get(db_session, exploration_id)

        if exploration.is_active():
            return await exploration_coordinator.start_return(db_session, exploration_id), None

        if exploration.is_returning():
            if exploration.return_time_remaining_seconds() > 0:
                return exploration, None
            rewards = await exploration_coordinator.finalize_return(db_session, exploration_id)
            return await crud_exploration.get(db_session, exploration_id), rewards

        raise ValueError(ERROR_NOT_ACTIVE)

    async def recall_exploration_with_data(
        self, db_session: AsyncSession, exploration_id: UUID4
    ) -> tuple[Exploration, RewardsSchema | None]:
        """Recall dweller early: the run enters its return leg, rewards wait for arrival.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param exploration_id: Exploration ID
        :type exploration_id: UUID4
        :return: Tuple of (exploration, None); rewards arrive when the dweller gets home
        :rtype: tuple[Exploration, RewardsSchema | None]
        :raises ValueError: If exploration cannot be recalled
        """
        exploration = await exploration_coordinator.start_return(db_session, exploration_id, recalled=True)
        return exploration, None

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
