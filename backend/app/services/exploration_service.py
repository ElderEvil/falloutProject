"""Exploration service for managing wasteland explorations.

This service provides a clean API for exploration operations and delegates to
the modular exploration system in services/exploration/ modules.
"""

import logging
import math
import random
from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import uuid4

from pydantic import UUID4
from sqlalchemy import orm
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerStatusEnum
from app.core.game_config import game_config
from app.crud import exploration as crud_exploration
from app.crud import team_crud
from app.crud import training as training_crud
from app.crud import world_location as crud_world_location
from app.crud.dweller import dweller as dweller_crud
from app.crud.storage import storage as crud_storage
from app.crud.vault_slot import vault_slot as vault_slot_crud
from app.crud.world_snapshot import world_snapshot as world_snapshot_crud
from app.models.dweller import Dweller
from app.models.exploration import Exploration, ExplorationStatus
from app.models.storage import Storage
from app.models.team import Team, TeamMember
from app.models.training import TrainingStatus
from app.models.world_location import WorldLocation
from app.options.races import can_use_radaway
from app.schemas.dweller import DwellerUpdate
from app.schemas.exploration import ExplorationPartyMemberRead, ExplorationProgress
from app.schemas.exploration_event import ExplorationEvent, RewardsSchema
from app.services.exploration.coordinator import ERROR_NOT_ACTIVE, exploration_coordinator
from app.services.exploration.event_generator import event_generator
from app.services.exploration.event_service import event_service
from app.services.user_service import user_service
from app.services.world_generation_service import WORLD_ID
from app.services.world_snapshot_service import world_snapshot_service
from app.utils import world_terrain
from app.utils.dweller_availability import availability_error
from app.utils.exceptions import ResourceNotFoundException, ValidationException
from app.utils.place_groups import effective_place_group
from app.utils.vault_slots import slot_coords

logger = logging.getLogger(__name__)


def dispatch_travel_hours(distance: float) -> int:
    """Whole-hour travel time for a dispatch to a map point (issue 772).

    Travel is quantized to whole hours: the base travel time plus a per-unit
    distance cost, rounded up, and clamped to the exploration duration bounds.
    """
    cfg = game_config.exploration.dispatch
    total_hours = cfg.base_travel_hours + cfg.travel_hours_per_unit * distance
    return max(1, min(24, math.ceil(total_hours)))


def _to_exploration_party_member_read(
    member: TeamMember, exploration_id: UUID4, vault_id: UUID4
) -> ExplorationPartyMemberRead:
    """Map a dispatch team member into the exploration wire contract (exploration/vault come from the run)."""
    slot_number = member.slot_number
    if slot_number is None:
        raise ValidationException("Exploration team member is missing a slot number")
    return ExplorationPartyMemberRead(
        id=member.id,
        exploration_id=exploration_id,
        vault_id=vault_id,
        dweller_id=member.dweller_id,
        slot_number=slot_number,
        status=member.status,
        created_at=member.created_at.isoformat() if member.created_at else None,
        updated_at=member.updated_at.isoformat() if member.updated_at else None,
    )


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

    async def get_party(
        self, db_session: AsyncSession, vault_id: UUID4, exploration_id: UUID4
    ) -> list[ExplorationPartyMemberRead]:
        """Read the slot-ordered party for a run belonging to the requested vault."""
        exploration = await crud_exploration.get(db_session, exploration_id)
        if exploration.vault_id != vault_id:
            raise ResourceNotFoundException(Exploration, identifier=exploration_id)
        members = await team_crud.get_exploration_team_members(db_session, exploration_id)
        return [_to_exploration_party_member_read(member, exploration_id, vault_id) for member in members]

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
        heading_degrees: float | None = None,
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
        :param heading_degrees: Compass heading (0=N, 90=E) for a spatial roam;
            None keeps today's legacy free-roam behavior
        :type heading_degrees: float | None
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

        # Resolve origin/world before staging: snapshot generation commits, so
        # resolving later would split the departure transaction.
        exploration_id = uuid4()
        origin: tuple[float, float] | None = await self._vault_origin(db_session, vault_id)
        world_version: int | None = None
        if heading_degrees is not None and not 0 <= heading_degrees < 360:
            raise ValueError("heading_degrees must be in [0, 360)")
        if origin is not None:
            snapshot = await world_snapshot_service.get_or_generate(db_session)
            world_version = snapshot.generator_version
            if heading_degrees is None:
                heading_degrees = self.choose_heading(snapshot, origin, duration, seed=exploration_id)
        elif heading_degrees is not None:
            raise ValueError("Vault has no map placement; cannot depart spatially")

        # Check vault storage first, then fall back to dweller inventory
        storage = await crud_storage.get_by_vault(db_session, vault_id)
        vault_stimpaks = storage.stimpack if storage else 0
        vault_radaways = storage.radaway if storage else 0

        # Get total available (vault + dweller)
        dweller = await dweller_crud.get(db_session, dweller_id)
        if dweller.vault_id != vault_id:
            raise ValueError("Dweller does not belong to this vault")
        if radaways > 0 and not can_use_radaway(dweller):
            raise ValueError("This dweller cannot carry RadAway")
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

        start_time = datetime.utcnow()
        exploration = Exploration(
            id=exploration_id,
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
            start_time=start_time,
            status=ExplorationStatus.ACTIVE,
        )
        self._init_spatial_movement(exploration, origin, heading_degrees, world_version, start_time)
        return await self._persist_departure(db_session, vault_id=vault_id, dwellers=[dweller], exploration=exploration)

    @staticmethod
    def _init_spatial_movement(
        exploration: Exploration,
        origin: tuple[float, float] | None,
        heading_degrees: float | None,
        world_version: int | None,
        start_time: datetime,
    ) -> None:
        """Stage movement fields on a departure; legacy runs keep every column NULL."""
        exploration.world_version = world_version
        exploration.origin_x = origin[0] if origin else None
        exploration.origin_y = origin[1] if origin else None
        exploration.heading_degrees = heading_degrees
        exploration.pos_x = origin[0] if origin else None
        exploration.pos_y = origin[1] if origin else None
        exploration.trail = [{"x": origin[0], "y": origin[1], "t": start_time.isoformat()}] if origin else []
        exploration.position_as_of = start_time if origin else None

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

    async def _vault_origin(self, db_session: AsyncSession, vault_id: UUID4) -> tuple[float, float] | None:
        """Travel origin: the vault's slot placement, or None when the vault has no slot.

        No production fallback to the map centre: vaults without a slot are
        grandfathered (their existing placements keep working) but cannot start a
        new spatial run or dispatch.
        """
        slot = await vault_slot_crud.get_by_vault(db_session, vault_id)
        return slot_coords(slot.slot_index) if slot is not None else None

    async def depart(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        dweller_ids: list[UUID4],
        target_location_id: UUID4 | None = None,
        duration: int = 4,
        stimpaks: int = 0,
        radaways: int = 0,
        heading_degrees: float | None = None,
    ) -> Exploration:
        """The single departure entry point: roam (no target) or clear (target).

        Roster and target validation live here so every caller shares one rule set;
        the roam and clear resolution engines stay separate.
        """
        if not dweller_ids:
            raise ValidationException("Provide at least one dweller")
        if target_location_id is None:
            if len(dweller_ids) != 1:
                raise ValidationException("Roaming runs send exactly one dweller")
            try:
                return await self.send_dweller(
                    db_session,
                    vault_id=vault_id,
                    dweller_id=dweller_ids[0],
                    duration=duration,
                    stimpaks=stimpaks,
                    radaways=radaways,
                    heading_degrees=heading_degrees,
                )
            except ValueError as e:
                raise ValidationException(str(e)) from e
        return await self.dispatch(
            db_session,
            vault_id=vault_id,
            dweller_ids=dweller_ids,
            location_id=target_location_id,
            stimpaks=stimpaks,
            radaways=radaways,
        )

    async def dispatch(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        dweller_ids: list[UUID4],
        location_id: UUID4,
        stimpaks: int = 0,
        radaways: int = 0,
    ) -> Exploration:
        """Send a party to clear a specific map point (issue 772).

        A targeted run travels for a whole number of hours based on the distance
        from the vault's slot placement, suppresses random events, and resolves exactly
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

        group = effective_place_group(location.group_key, location.kind)
        if group is None or not group.get("clearable"):
            raise ValidationException("This location cannot be cleared")

        if not await crud_world_location.is_location_unlocked(db_session, vault_id, location_id):
            raise ValidationException("This location is not known to the vault")

        if not state.is_dispatchable(datetime.utcnow()):
            raise ValidationException("This location is currently cleared")

        origin = await self._vault_origin(db_session, vault_id)
        if origin is None:
            raise ValidationException("Vault has no map placement; cannot dispatch")
        distance = math.dist(origin, (location.coord_x, location.coord_y))
        duration = dispatch_travel_hours(distance)
        tier = min(state.clear_count, game_config.exploration.dispatch.escalation_cap)
        if stimpaks < 0 or radaways < 0:
            raise ValidationException("Supplies cannot be negative")
        storage = await crud_storage.get_by_vault(db_session, vault_id)
        self._require_supplies(storage, stimpaks, radaways)
        # Snapshot generation commits when it creates a row; resolve it before
        # staging the storage deduction so supplies, team, and exploration all
        # persist in the single departure commit. Staging first would let the
        # snapshot commit strand the deduction if the run never gets created.
        snapshot = await world_snapshot_service.get_or_generate(db_session)
        # That commit can leave the pre-snapshot read stale, so re-read the row
        # under FOR UPDATE and refresh it: a supply spend committed in the window
        # must not be overwritten by the earlier validation. The row lock holds
        # until the departure commit, making the re-check and deduction atomic.
        storage = await crud_storage.get_by_vault_for_update(db_session, vault_id)
        if storage is not None:
            await db_session.refresh(storage)
        self._require_supplies(storage, stimpaks, radaways)
        if (stimpaks or radaways) and storage is not None:
            storage.stimpack = (storage.stimpack or 0) - stimpaks
            storage.radaway = (storage.radaway or 0) - radaways
            db_session.add(storage)
        anchor = dwellers[0]

        exploration = Exploration(
            vault_id=vault_id,
            dweller_id=anchor.id,
            duration=duration,
            stimpaks=stimpaks,
            radaways=radaways,
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
        self._init_spatial_movement(
            exploration,
            origin,
            world_terrain.heading_to(origin, (location.coord_x, location.coord_y)),
            snapshot.generator_version,
            exploration.start_time,
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

    @staticmethod
    def _require_supplies(storage: Storage | None, stimpaks: int, radaways: int) -> None:
        """Reject a dispatch whose requested supplies exceed the storage row."""
        available_stimpaks = storage.stimpack if storage else 0
        available_radaways = storage.radaway if storage else 0
        if stimpaks > available_stimpaks:
            raise ValidationException(f"Total available stimpaks: {available_stimpaks}")
        if radaways > available_radaways:
            raise ValidationException(f"Total available radaways: {available_radaways}")

    @staticmethod
    def _speed() -> float:
        """Registry-space units per hour (10 at current config)."""
        return 1 / game_config.exploration.dispatch.travel_hours_per_unit

    def choose_heading(self, snapshot, origin: tuple[float, float], duration: int, seed) -> float:
        """Deterministic, terrain-aware heading: the candidate with the most clear ground."""
        outbound = self._speed() * duration / 2
        winners: list[float] = []
        best = -1.0
        for heading in range(0, 360, 15):
            score = min(self._clear_distance(snapshot, origin, heading, outbound), outbound)
            if score > best:
                best = score
                winners = [float(heading)]
            elif score == best:
                winners.append(float(heading))
        return random.Random(str(seed)).choice(winners)

    def _clear_distance(self, snapshot, origin: tuple[float, float], heading: float, max_distance: float) -> float:
        """Distance travelable along *heading* before water or a map bound blocks it."""
        if snapshot is None:
            return max_distance
        radians = math.radians(heading)
        end = (origin[0] + math.sin(radians) * max_distance, origin[1] - math.cos(radians) * max_distance)
        last = self._last_valid_point(snapshot, origin[0], origin[1], end[0], end[1])
        return math.dist(origin, last)

    async def suggest_heading(
        self, db_session: AsyncSession, vault_id: UUID4, duration: int, seed: str
    ) -> float | None:
        """Suggest a deterministic, terrain-aware heading; null when the vault has no placement."""
        origin = await self._vault_origin(db_session, vault_id)
        if origin is None:
            return None
        snapshot = await world_snapshot_service.get_or_generate(db_session)
        return self.choose_heading(snapshot, origin, duration, seed=seed)

    async def _load_snapshot(self, db_session: AsyncSession, exploration: Exploration):
        """The world snapshot the run moves through, or None when unavailable."""
        if exploration.world_version is None:
            return None
        snapshot = await world_snapshot_crud.get_version(
            db_session, world_id=WORLD_ID, generator_version=exploration.world_version
        )
        if snapshot is None:
            logger.warning(
                "No world snapshot for version %s; terrain checks disabled for exploration %s",
                exploration.world_version,
                exploration.id,
            )
        return snapshot

    @staticmethod
    def _is_blocked(snapshot, x: float, y: float) -> bool:
        """True when the registry-space position is out of bounds or on water."""
        return snapshot is not None and world_terrain.is_blocked(snapshot, x, y)

    @classmethod
    def _last_valid_point(cls, snapshot, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float]:
        """The last point along the segment that is not blocked (water/bounds).

        Marches the whole newly traveled segment so offline catch-up cannot jump
        over a water tile between ticks.
        """
        distance = math.dist((x0, y0), (x1, y1))
        steps = max(1, int(distance / 0.5))
        last_valid = (x0, y0)
        for i in range(1, steps + 1):
            t = i / steps
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            if cls._is_blocked(snapshot, x, y):
                break
            last_valid = (x, y)
        return last_valid

    @classmethod
    def _path_clear(cls, snapshot, a: tuple[float, float], b: tuple[float, float]) -> bool:
        """True when the straight segment between two points is fully traversable.

        Uses the same segment march as movement, so a target across water is never
        treated as reached merely because it sits within the arrival radius.
        """
        last = cls._last_valid_point(snapshot, a[0], a[1], b[0], b[1])
        return math.dist(last, b) < 0.01

    def _obstruction_time(
        self, position_as_of: datetime, start: tuple[float, float], blocked_at: tuple[float, float]
    ) -> datetime:
        """When, within the processed interval, the party actually reached the obstruction.

        Dating a blocked return at the interval start would let it expire before the
        party could have traveled to the obstruction; derive it from the distance moved.
        """
        return position_as_of + timedelta(hours=math.dist(start, blocked_at) / self._speed())

    @staticmethod
    def _origin(exploration: Exploration) -> tuple[float, float]:
        """The departure origin; spatial runs always carry one."""
        origin_x = exploration.origin_x
        origin_y = exploration.origin_y
        if origin_x is None or origin_y is None:
            raise ValidationException("Spatial run is missing an origin")
        return (origin_x, origin_y)

    @staticmethod
    def _position(exploration: Exploration) -> tuple[float, float]:
        """The dweller's current position; spatial runs always carry one."""
        pos_x = exploration.pos_x
        pos_y = exploration.pos_y
        if pos_x is None or pos_y is None:
            raise ValidationException("Spatial run is missing a position")
        return (pos_x, pos_y)

    @staticmethod
    def _heading(exploration: Exploration) -> float:
        """The run's compass heading; spatial runs always carry one."""
        heading = exploration.heading_degrees
        if heading is None:
            raise ValidationException("Spatial run is missing a heading")
        return heading

    @staticmethod
    def _return_started_at(exploration: Exploration) -> datetime:
        """When the return leg started; returning spatial runs always carry one."""
        return_started_at = exploration.return_started_at
        if return_started_at is None:
            raise ValidationException("Spatial run is missing a return start")
        return return_started_at

    def _forward_position(self, exploration: Exploration, now: datetime) -> tuple[float, float]:
        """Analytic position along the heading at time *now* (registry space)."""
        origin = self._origin(exploration)
        heading = math.radians(self._heading(exploration))
        dx, dy = math.sin(heading), -math.cos(heading)
        t_hours = (now - exploration.start_time).total_seconds() / 3600
        return (origin[0] + dx * self._speed() * t_hours, origin[1] + dy * self._speed() * t_hours)

    @staticmethod
    def _append_trail(exploration: Exploration, x: float, y: float, t: datetime) -> None:
        exploration.trail.append({"x": round(x, 4), "y": round(y, 4), "t": t.isoformat()})
        orm.attributes.flag_modified(exploration, "trail")

    @staticmethod
    def _begin_spatial_return(exploration: Exploration, return_started_at: datetime) -> None:
        """Start the physical return leg: retrace the traveled path at the same speed."""
        traveled = math.dist(ExplorationService._origin(exploration), ExplorationService._position(exploration))
        return_hours = traveled * game_config.exploration.dispatch.travel_hours_per_unit
        exploration.return_started_at = return_started_at
        exploration.return_completes_at = return_started_at + timedelta(hours=return_hours)
        exploration.status = ExplorationStatus.RETURNING

    async def _advance_forward_to(
        self, exploration: Exploration, at_time: datetime, snapshot, position_as_of: datetime
    ) -> None:
        """Move the dweller forward along the heading; block on water and map bounds."""
        new_x, new_y = self._forward_position(exploration, at_time)
        pos_x, pos_y = self._position(exploration)
        valid_x, valid_y = self._last_valid_point(snapshot, pos_x, pos_y, new_x, new_y)
        if (valid_x, valid_y) != (new_x, new_y):
            exploration.pos_x, exploration.pos_y = valid_x, valid_y
            self._append_trail(exploration, valid_x, valid_y, at_time)
            self._begin_spatial_return(
                exploration, self._obstruction_time(position_as_of, (pos_x, pos_y), (valid_x, valid_y))
            )
            return
        exploration.pos_x, exploration.pos_y = new_x, new_y
        self._append_trail(exploration, new_x, new_y, at_time)

    async def _advance_forward(
        self, db_session: AsyncSession, exploration: Exploration, now: datetime, snapshot, position_as_of: datetime
    ) -> None:
        """Move the dweller forward along the heading; block on water and map bounds."""
        await self._advance_forward_to(exploration, now, snapshot, position_as_of)

    async def _snap_to_forward_end(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        forward_end: datetime,
        snapshot,
        position_as_of: datetime,
    ) -> None:
        """Set the position to the outbound budget point, unless blocked earlier."""
        await self._advance_forward_to(exploration, forward_end, snapshot, position_as_of)

    async def _advance_dispatch(
        self,
        db_session: AsyncSession,
        exploration: Exploration,
        now: datetime,
        snapshot,
        position_as_of: datetime,
    ) -> None:
        """Move a targeted run toward its location; hold on arrival, return when blocked.

        Unlike roams, dispatches have no outbound budget: the forward phase lasts
        until the dweller reaches the target, detected on the traveled segment so
        long offline catch-ups cannot leapfrog it. The tick resolves arrival
        combat; an unreached run falls back to the legacy timer expiry. Blocked
        paths return early instead of stranding the party.
        """
        target_location_id = exploration.target_location_id
        if target_location_id is None:
            self._begin_spatial_return(exploration, now)
            return
        location = await crud_world_location.get_registry(db_session, target_location_id)
        if location is None:
            self._begin_spatial_return(exploration, now)
            return
        target = (location.coord_x, location.coord_y)
        pos = self._position(exploration)
        if math.dist(pos, target) <= world_terrain.ARRIVAL_RADIUS and self._path_clear(snapshot, pos, target):
            self._append_trail(exploration, pos[0], pos[1], now)
            return
        new_x, new_y = self._forward_position(exploration, now)
        valid_x, valid_y = self._last_valid_point(snapshot, pos[0], pos[1], new_x, new_y)
        if world_terrain.segment_passes_near(
            pos, (valid_x, valid_y), target, world_terrain.ARRIVAL_RADIUS
        ) and self._path_clear(snapshot, (valid_x, valid_y), target):
            exploration.pos_x, exploration.pos_y = target
            self._append_trail(exploration, target[0], target[1], now)
            return
        if (valid_x, valid_y) != (new_x, new_y):
            exploration.pos_x, exploration.pos_y = valid_x, valid_y
            self._append_trail(exploration, valid_x, valid_y, now)
            self._begin_spatial_return(exploration, self._obstruction_time(position_as_of, pos, (valid_x, valid_y)))
            return
        exploration.pos_x, exploration.pos_y = new_x, new_y
        self._append_trail(exploration, new_x, new_y, now)

    def _advance_return(self, exploration: Exploration, now: datetime) -> None:
        """Move the dweller back along the traveled path at the same speed."""
        origin = self._origin(exploration)
        heading = math.radians(self._heading(exploration))
        dx, dy = math.sin(heading), -math.cos(heading)
        if exploration.trail:
            last = exploration.trail[-1]
            max_x, max_y = float(last["x"]), float(last["y"])
        else:
            max_x, max_y = origin
        forward_distance = math.dist(origin, (max_x, max_y))
        return_elapsed_hours = (now - self._return_started_at(exploration)).total_seconds() / 3600
        retraced = self._speed() * return_elapsed_hours
        if retraced >= forward_distance:
            exploration.pos_x, exploration.pos_y = origin
        else:
            exploration.pos_x = max_x - dx * retraced
            exploration.pos_y = max_y - dy * retraced

    async def has_arrived(self, db_session: AsyncSession, exploration: Exploration) -> bool:
        """True when a spatial dispatch run reaches its target over traversable terrain."""
        if exploration.target_location_id is None or exploration.pos_x is None or exploration.pos_y is None:
            return False
        location = await crud_world_location.get_registry(db_session, exploration.target_location_id)
        if location is None:
            return False
        target = (location.coord_x, location.coord_y)
        pos = (exploration.pos_x, exploration.pos_y)
        if math.dist(pos, target) > world_terrain.ARRIVAL_RADIUS:
            return False
        snapshot = await self._load_snapshot(db_session, exploration)
        return self._path_clear(snapshot, pos, target)

    async def _settle_movement(self, db_session: AsyncSession, exploration: Exploration, now: datetime) -> None:
        """Apply movement up to *now* on the in-memory exploration (no commit).

        Shared by the tick-owned ``advance`` and the boundary settles so the clock
        arithmetic has one implementation while each caller owns its transaction.
        """
        position_as_of = exploration.position_as_of
        if position_as_of is None or exploration.heading_degrees is None:
            return
        if not exploration.is_in_progress():
            return
        if (now - position_as_of).total_seconds() <= 0:
            return

        # An encounter in progress freezes the journey: burn the interval without
        # moving. The clock shift is applied once at the exit boundary
        # (resume_from_encounter), so a pause with no inside tick is still counted.
        if exploration.paused_at is not None:
            exploration.position_as_of = max(position_as_of, now)
            return

        snapshot = await self._load_snapshot(db_session, exploration)
        forward_budget = timedelta(hours=exploration.duration / 2)
        forward_end = exploration.start_time + forward_budget

        if exploration.is_active():
            if exploration.target_location_id is not None:
                await self._advance_dispatch(db_session, exploration, now, snapshot, position_as_of)
            elif now <= forward_end:
                await self._advance_forward(db_session, exploration, now, snapshot, position_as_of)
            else:
                await self._snap_to_forward_end(db_session, exploration, forward_end, snapshot, position_as_of)
                if exploration.is_active():
                    self._begin_spatial_return(exploration, forward_end)
        elif exploration.is_returning():
            self._advance_return(exploration, now)

        exploration.position_as_of = now

    async def advance(
        self, db_session: AsyncSession, exploration_id: UUID4, *, now: datetime | None = None
    ) -> Exploration:
        """Advance a spatial exploration's position by elapsed time (slice 1 movement).

        Legacy runs (``heading_degrees`` NULL) are untouched. Spatial runs move along
        their heading at ``1 / travel_hours_per_unit`` units per hour; the forward
        phase lasts half the chosen duration, then the dweller retraces the traveled
        path home at the same speed. Water and map bounds block forward movement and
        trigger an early return. Reprocessing an already-processed interval is a no-op
        via ``position_as_of``. The tick owns this transaction, so it commits.
        """
        exploration = await crud_exploration.get(db_session, exploration_id)
        now = now or datetime.utcnow()
        await self._settle_movement(db_session, exploration, now)
        db_session.add(exploration)
        await db_session.commit()
        await db_session.refresh(exploration)
        return exploration

    async def pause_for_encounter(
        self, db_session: AsyncSession, exploration: Exploration, *, now: datetime | None = None
    ) -> Exploration:
        """Stage the journey freeze while a site encounter is open (caller commits).

        The pre-entry segment is settled to the boundary first, then the pause is
        marked. ``advance`` burns intervals while paused and the clock shift happens
        in ``resume_from_encounter``, so entry/exit need no ticks in between.
        """
        now = now or datetime.utcnow()
        await self._settle_movement(db_session, exploration, now)
        if exploration.heading_degrees is not None and exploration.paused_at is None:
            exploration.paused_at = now
        if exploration.position_as_of is not None:
            exploration.position_as_of = max(exploration.position_as_of, now)
        db_session.add(exploration)
        return exploration

    def resume_from_encounter(self, exploration: Exploration, *, now: datetime | None = None) -> Exploration:
        """Stage the clock shift past a pause (caller commits)."""
        now = now or datetime.utcnow()
        paused_at = exploration.paused_at
        if paused_at is None:
            return exploration
        paused = now - paused_at
        if exploration.heading_degrees is not None and paused > timedelta(0):
            if exploration.is_active():
                exploration.start_time += paused
            elif exploration.is_returning():
                if exploration.return_started_at is not None:
                    exploration.return_started_at += paused
                if exploration.return_completes_at is not None:
                    exploration.return_completes_at += paused
        exploration.paused_at = None
        if exploration.position_as_of is not None:
            exploration.position_as_of = max(exploration.position_as_of, now)
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
