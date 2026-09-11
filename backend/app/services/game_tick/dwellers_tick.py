"""Dweller-phase tick logic for the game loop.

Extracted verbatim from ``GameLoopService``: wasteland explorations, work XP and
level-ups, deaths and dehydration radiation, youth apprenticeships, training
sessions, and happiness. ``GameLoopService`` keeps same-named thin delegates.
"""

import logging
from datetime import datetime

from pydantic import UUID4
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RoomTypeEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud import dweller as crud_dweller
from app.crud import exploration as crud_exploration
from app.crud import room as crud_room
from app.crud.vault import vault as vault_crud
from app.services.exploration_service import exploration_service
from app.services.happiness_service import happiness_service
from app.services.radiation_service import apply_radiation_gain
from app.utils.exceptions import ResourceNotFoundException, VaultOperationException

logger = logging.getLogger(__name__)


async def process_explorations(db_session: AsyncSession, vault_id: UUID4) -> dict:
    """Process all active explorations for a vault.

    - Generate events for explorations that are due
    - Auto-complete explorations that have reached their duration
    """
    stats = {
        "active_count": 0,
        "events_generated": 0,
        "completed": 0,
    }

    try:
        # Get all active explorations for this vault
        active_explorations = await crud_exploration.get_by_vault(
            db_session,
            vault_id=vault_id,
            active_only=True,
        )

        stats["active_count"] = len(active_explorations)

        for exploration in active_explorations:
            try:
                # Check if exploration should be auto-completed
                if exploration.time_remaining_seconds() <= 0:
                    # Auto-complete the exploration
                    await exploration_service.complete_exploration(db_session, exploration.id)
                    stats["completed"] += 1
                    logger.info(f"Auto-completed exploration {exploration.id} for dweller {exploration.dweller_id}")
                    continue

                # Try to generate an event
                event_generated = exploration_service.generate_event(exploration)
                if event_generated:
                    await exploration_service.process_event(db_session, exploration)
                    stats["events_generated"] += 1

            except (SQLAlchemyError, ValueError, RuntimeError) as e:
                # Keep broad exception for individual exploration processing
                logger.error(f"Error processing exploration {exploration.id}: {e}", exc_info=True)

    except (SQLAlchemyError, ResourceNotFoundException) as e:
        logger.error(f"Error loading explorations for vault {vault_id}: {e}", exc_info=True)
        stats["error"] = str(e)

    return stats


async def award_work_xp(db_session: AsyncSession, dweller, room) -> dict:
    """Award work XP to a dweller and check for level-up.

    Args:
        db_session: Database session
        dweller: Dweller model instance
        room: Room model instance

    Returns:
        dict: Statistics with 'xp_awarded' and 'leveled_up' counts
    """
    from app.services.leveling_service import leveling_service

    stats = {"xp_awarded": 0, "leveled_up": 0}

    if room.category != RoomTypeEnum.PRODUCTION:
        return stats

    # Base XP per tick
    xp_to_award = game_config.leveling.work_xp_per_tick

    # Efficiency bonus: if dweller has high matching SPECIAL
    if room.ability:
        dweller_stat = getattr(dweller, room.ability.value.lower(), 1)
        # If SPECIAL >= 7, give efficiency bonus
        if dweller_stat >= 7:
            xp_to_award = int(xp_to_award * game_config.leveling.work_efficiency_bonus)

    # Award XP (ensure it never goes negative)
    dweller.experience = max(0, dweller.experience + xp_to_award)
    db_session.add(dweller)
    stats["xp_awarded"] = xp_to_award

    # Check for level-up
    leveled_up, levels_gained = await leveling_service.check_level_up(db_session, dweller)
    if leveled_up:
        stats["leveled_up"] = levels_gained
        logger.info(f"Dweller {dweller} gained {levels_gained} level(s)! Now level {dweller.level}")
        # Emit DWELLER_LEVEL_UP event for objective tracking
        if dweller.vault_id:
            await event_bus.emit(
                GameEvent.DWELLER_LEVEL_UP,
                dweller.vault_id,
                {
                    "dweller_id": str(dweller.id),
                    "level": dweller.level,
                    "old_level": dweller.level - levels_gained,
                    "amount": levels_gained,
                },
            )

    return stats


async def process_dwellers(db_session: AsyncSession, vault_id: UUID4, seconds_passed: int | None = None) -> dict:
    """Process dweller updates for a vault.

    - Irradiate in-vault dwellers while the vault has no water
    - Award work XP to dwellers in production rooms
    - Check for level-ups
    - Check for deaths (health <= 0 or radiation threshold)
    """
    from app.core.enums import DeathCauseEnum, DwellerStatusEnum
    from app.services.family.death_service import death_service

    stats = {
        "health_updated": 0,
        "leveled_up": 0,
        "xp_awarded": 0,
        "deaths": 0,
        "irradiated": 0,
    }

    try:
        # Get all dwellers in this vault
        dwellers = await crud_dweller.get_all_in_vault(db_session, vault_id)

        vault = await vault_crud.get(db_session, vault_id)
        if vault is not None and vault.water <= 0 and game_config.health.dehydration_radiation_per_tick > 0:
            ticks = max(1, seconds_passed // game_config.game_loop.tick_interval) if seconds_passed else 1
            rads = game_config.health.dehydration_radiation_per_tick * ticks
            for dweller in dwellers:
                # TODO: unify busy-dweller exclusion with responder eligibility; shared policy outside services.
                if dweller.status in (DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING):
                    continue
                if apply_radiation_gain(dweller, rads):
                    db_session.add(dweller)
                    stats["irradiated"] += 1
            if stats["irradiated"]:
                await db_session.commit()
                logger.warning(
                    f"Vault {vault_id} has no water: applied {rads} radiation to {stats['irradiated']} dwellers"
                )

        # Get all unique room IDs from working dwellers
        working_room_ids = {d.room_id for d in dwellers if d.status == DwellerStatusEnum.WORKING and d.room_id}

        # Batch fetch all rooms in one query
        rooms_map = {}
        if working_room_ids:
            rooms = await crud_room.get_by_ids(list(working_room_ids), db_session)
            rooms_map = {room.id: room for room in rooms}

        # Process each dweller
        for dweller in dwellers:
            if dweller.is_dead:
                continue

            if dweller.health <= 0:
                await death_service.mark_as_dead(db_session, dweller, DeathCauseEnum.HEALTH)
                stats["deaths"] += 1
                logger.info(f"Dweller {dweller.first_name} {dweller.last_name} died from health depletion")
                continue

            if dweller.radiation >= game_config.death.radiation_death_threshold:
                await death_service.mark_as_dead(db_session, dweller, DeathCauseEnum.RADIATION)
                stats["deaths"] += 1
                logger.info(f"Dweller {dweller.first_name} {dweller.last_name} died from radiation")
                continue

            if dweller.status == DwellerStatusEnum.WORKING and dweller.room_id:
                room = rooms_map.get(dweller.room_id)
                if room:
                    dweller_stats = await award_work_xp(db_session, dweller, room)
                    stats["xp_awarded"] += dweller_stats["xp_awarded"]
                    stats["leveled_up"] += dweller_stats["leveled_up"]

    except SQLAlchemyError as e:
        logger.error(f"Database error processing dwellers for vault {vault_id}: {e}", exc_info=True)
        raise

    return stats


async def process_apprenticeships(db_session: AsyncSession, vault_id: UUID4) -> dict:
    """Advance eligible youth apprentices by at most one SPECIAL point per tick."""
    from app.models.base import SPECIALModel
    from app.services.training_service import TrainingService

    stats = {"active_count": 0, "stats_awarded": 0}
    apprentices = list(await crud_dweller.get_active_apprentices(db_session, vault_id))
    stats["active_count"] = len(apprentices)
    if not apprentices:
        return stats

    room_ids = {apprentice.room_id for apprentice in apprentices if apprentice.room_id is not None}
    rooms_by_id = {}
    if room_ids:
        rooms = await crud_room.get_by_ids(list(room_ids), db_session)
        rooms_by_id = {room.id: room for room in rooms}

    now = datetime.utcnow()
    for apprentice in apprentices:
        room = rooms_by_id.get(apprentice.room_id)
        if (
            apprentice.is_mature
            or room is None
            or room.category != RoomTypeEnum.PRODUCTION
            or room.ability != apprentice.apprentice_stat
        ):
            continue

        current_stat = SPECIALModel.get_stat(apprentice, apprentice.apprentice_stat)
        duration = TrainingService.calculate_training_duration(current_stat, room.tier)
        if (now - apprentice.apprentice_started_at).total_seconds() < duration:
            continue

        if current_stat < game_config.training.special_stat_max:
            SPECIALModel.set_stat(apprentice, apprentice.apprentice_stat, current_stat + 1)
            stat_key = apprentice.apprentice_stat.value.lower()
            apprentice.apprentice_stat_gains = {
                **apprentice.apprentice_stat_gains,
                stat_key: apprentice.apprentice_stat_gains.get(stat_key, 0) + 1,
            }
            stats["stats_awarded"] += 1
        apprentice.apprentice_started_at = now
        db_session.add(apprentice)

    await db_session.flush()
    return stats


async def process_training(db_session: AsyncSession, vault_id: UUID4) -> dict:
    """Process all active training sessions for a vault.

    - Update training progress
    - Auto-complete trainings that have finished
    - Track statistics
    """
    from app.crud import training as training_crud
    from app.services.training_service import training_service
    from app.utils.exceptions import ResourceConflictException

    stats = {
        "sessions_updated": 0,
        "completed": 0,
        "active_count": 0,
    }

    try:
        # Get all active training sessions in this vault
        active_trainings = await training_crud.training.get_active_by_vault(db_session, vault_id)
        stats["active_count"] = len(active_trainings)

        # Batch-fetch all dwellers for these training sessions (N+1 optimization)
        dwellers_map = await training_crud.training.get_dwellers_for_trainings(db_session, active_trainings)

        for training in active_trainings:
            try:
                # Get pre-fetched dweller
                dweller = dwellers_map.get(training.dweller_id)

                # Update progress (this will auto-complete if ready)
                updated_training = await training_service.update_training_progress(
                    db_session, training, dweller=dweller
                )

                stats["sessions_updated"] += 1

                # Check if it was completed
                if updated_training.is_completed():
                    stats["completed"] += 1
                    logger.info(
                        f"Training completed: Dweller gained {updated_training.stat_being_trained.value} "
                        f"(now {updated_training.target_stat_value})"
                    )

            except (SQLAlchemyError, ValueError, RuntimeError) as e:
                # Keep broad exception for individual training processing
                logger.error(f"Error processing training {training.id}: {e}", exc_info=True)

    except (SQLAlchemyError, ResourceNotFoundException, ResourceConflictException, VaultOperationException) as e:
        logger.error(f"Error loading training sessions for vault {vault_id}: {e}", exc_info=True)
        stats["error"] = str(e)

    return stats


async def process_happiness(db_session: AsyncSession, vault_id: UUID4, seconds_passed: int) -> dict:
    """Process happiness updates for all dwellers in a vault.

    - Calculate happiness changes based on vault conditions
    - Update individual dweller happiness
    - Update vault-wide average happiness
    """
    # Happiness service handles its own errors internally, no wrapper needed
    return await happiness_service.update_vault_happiness(db_session, vault_id, seconds_passed)
