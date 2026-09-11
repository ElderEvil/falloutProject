"""Incident creation: spawn gating, room selection, spreading, and spawn locks."""

import logging
import random

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import db_locks
from app.core.game_config import game_config
from app.crud.dweller import dweller as crud_dweller
from app.crud.incident import incident_crud
from app.crud.room import room as room_crud
from app.models.game_state import GameState
from app.models.incident import Incident, IncidentType
from app.models.room import Room
from app.models.vault import Vault
from app.services.combat import incident_publishing
from app.services.combat.incident_publishing import INCIDENT_NAMES

logger = logging.getLogger(__name__)


def is_at_incident_cap(active_incidents: list[Incident]) -> bool:
    """Report whether the vault already runs the maximum active incidents."""
    return len(active_incidents) >= game_config.incident.max_active_incidents


def is_spawning_disabled(vault: Vault | None) -> bool:
    """Report whether incident spawning is switched off (an absent vault counts as enabled)."""
    return vault is not None and vault.incidents_disabled


async def should_spawn_incident(
    db_session: AsyncSession, vault_id: UUID4, seconds_passed: int, game_state: GameState | None = None
) -> bool:
    """Determine if an incident should spawn based on vault state and time.

    Args:
        db_session: Database session
        vault_id: The vault ID to check
        seconds_passed: Seconds since last tick
        game_state: Optional game state for online/offline check

    Returns:
        bool: True if incident should spawn
    """
    # Check if user is online (has recent activity) - suppress incidents when offline
    if game_state and not game_state.is_user_online(timeout_seconds=600):
        logger.debug(f"Vault {vault_id} is offline, suppressing incident spawn")
        return False

    vault = await db_session.get(Vault, vault_id)
    if is_spawning_disabled(vault):
        logger.debug(f"Incidents are disabled for vault {vault_id}")
        return False

    # Need minimum population
    if await crud_dweller.count_in_vault(db_session, vault_id) < game_config.incident.min_vault_population:
        return False

    # Check if max active incidents reached
    active_incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
    if is_at_incident_cap(active_incidents):
        return False

    # Check cooldown period (if there are any incidents, check the most recent one)
    if active_incidents:
        from datetime import datetime

        most_recent = max(active_incidents, key=lambda i: i.start_time)
        seconds_since_last = (datetime.utcnow() - most_recent.start_time).total_seconds()
        if seconds_since_last < game_config.incident.spawn_cooldown_seconds:
            return False

    # Time-based cap: limit spawn chance growth to prevent bursts
    # Cap hours_passed to prevent excessive spawn chance after long offline periods
    hours_passed = min(seconds_passed / 3600, 2.0)  # Cap at 2 hours worth of chance
    spawn_chance = game_config.incident.spawn_chance_per_hour * hours_passed

    # Random roll
    return random.random() < spawn_chance


async def spawn_incident(
    db_session: AsyncSession, vault_id: UUID4, incident_type: IncidentType | None = None
) -> Incident | None:
    """Spawn a new incident in a random occupied room.
    Raiders and Deathclaws spawn at vault door (0,0) and spread inward.

    Rules enforced:
    - Only one incident type per vault at a time
    - Only one incident per room
    - Never spawn in elevators

    Args:
        db_session: Database session
        vault_id: ID of the vault
        incident_type: Type of incident (radscorpion if None)

    Returns:
        Incident or None if no suitable room found
    """
    if not await db_locks.try_advisory_xact_lock(db_session, f"incident-spawn:{vault_id}"):
        return None

    vault = await db_session.get(Vault, vault_id)
    if vault is None:
        return None
    if is_spawning_disabled(vault):
        from app.utils.exceptions import IncidentsDisabledException

        raise IncidentsDisabledException

    active_incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
    if is_at_incident_cap(active_incidents):
        from app.utils.exceptions import ResourceConflictException

        raise ResourceConflictException(
            detail=f"Vault is at the active-incident cap ({game_config.incident.max_active_incidents})."
        )

    active_types = {incident.type for incident in active_incidents}

    # Runtime spawns use radscorpions; explicit types remain available to
    # administrative and test callers.
    if incident_type is None:
        incident_type = IncidentType.RADSCORPION_ATTACK

    # If type specified but vault has different type, don't spawn
    if active_types and incident_type not in active_types:
        logger.info(f"Cannot spawn {incident_type} in vault {vault_id} - vault already has {active_types}")
        return None

    # Get rooms that already have active incidents
    rooms_with_incidents = await incident_crud.get_rooms_with_active_incidents(db_session, vault_id)

    target_room = await select_spawn_room(db_session, vault_id, incident_type, rooms_with_incidents)
    if target_room is None:
        return None

    difficulty = random.randint(*game_config.incident.get_difficulty_range(incident_type))

    incident_name = INCIDENT_NAMES.get(incident_type, str(incident_type))

    # Create incident
    incident = await incident_crud.create(
        db_session,
        vault_id=vault_id,
        room_id=target_room.id,
        incident_type=incident_type,
        difficulty=difficulty,
        duration=game_config.incident.spread_duration,
    )
    incident_publishing.record_event(
        db_session, incident, "spawned", f"{incident_name} detected in {target_room.name}."
    )
    await db_session.commit()

    logger.info(f"Spawned {incident_type} (difficulty {difficulty}) in room {target_room.name} of vault {vault_id}")

    # Send notification + SSE (non-critical, don't break incident creation on failure)
    await incident_publishing.notify_spawn(db_session, incident, target_room.name, incident_name, difficulty)
    await incident_publishing.publish_sse(
        incident,
        "incident_spawned",
        room_name=target_room.name if target_room else None,
    )

    return incident


async def select_spawn_room(
    db_session: AsyncSession, vault_id: UUID4, incident_type: IncidentType, rooms_with_incidents: set[UUID4]
) -> Room | None:
    """Pick the spawn room for an incident type; None when no suitable room exists."""
    # Determine where to spawn based on incident type
    if incident_type.value in game_config.incident.vault_door_incidents:
        # External attacks spawn at vault door (0,0) and spread inward
        target_room = await room_crud.get_room_by_coordinates(
            db_session=db_session,
            vault_id=vault_id,  # ty: ignore[invalid-argument-type]
            x_coord=0,
            y_coord=0,
        )

        if not target_room:
            logger.warning(f"No vault door found at (0,0) for {incident_type} in vault {vault_id}")
            return None

        # Check if vault door already has incident
        if target_room.id in rooms_with_incidents:
            logger.info(f"Vault door already has active incident in vault {vault_id}")
            return None
        return target_room

    # Other incidents spawn in random occupied rooms (excluding elevators)
    occupied_rooms = await room_crud.get_occupied_rooms(db_session, vault_id)

    # Filter out rooms that already have incidents
    available_rooms = [room for room in occupied_rooms if room.id not in rooms_with_incidents]

    if not available_rooms:
        logger.warning(
            f"No available rooms for incident spawn in vault {vault_id} "
            f"(all occupied non-elevator rooms already have incidents)"
        )
        return None

    # Pick random room
    return random.choice(available_rooms)


async def spread_incident(db_session: AsyncSession, incident: Incident) -> bool:
    """Spread an incident to an adjacent room and report whether it succeeded."""
    if not await db_locks.try_advisory_xact_lock(db_session, f"incident-spawn:{incident.vault_id}"):
        return False

    active_incidents = await incident_crud.get_active_by_vault(db_session, incident.vault_id)
    if is_at_incident_cap(active_incidents):
        logger.info("Incident cap reached while spreading in vault %s", incident.vault_id)
        return False

    # Get the current room to find its coordinates
    current_room = await room_crud.get_or_none(db_session, id=incident.room_id)

    if not current_room or current_room.coordinate_x is None or current_room.coordinate_y is None:
        return False

    # Get rooms that already have active incidents
    rooms_with_incidents = await incident_crud.get_rooms_with_active_incidents(db_session, incident.vault_id)

    # Find adjacent rooms (within 1-2 coordinate units horizontally or vertically)
    # Exclude elevators and rooms with active incidents
    all_adjacent_rooms = await room_crud.get_adjacent_rooms(
        db_session,
        incident.vault_id,
        exclude_room_id=incident.room_id,
        coord_x=current_room.coordinate_x,
        coord_y=current_room.coordinate_y,
    )

    # Filter out rooms that already have incidents
    adjacent_rooms = [room for room in all_adjacent_rooms if room.id not in rooms_with_incidents]

    if adjacent_rooms:
        # Pick a random adjacent room
        new_room = random.choice(adjacent_rooms)

        # Create a new incident in the adjacent room with the SAME type, capped
        # at the model's max difficulty so it can't snowball on repeat spreads.
        new_incident = await incident_crud.create(
            db_session,
            vault_id=incident.vault_id,
            room_id=new_room.id,
            incident_type=incident.type,  # Same type! (field is called 'type')
            difficulty=min(incident.difficulty + 1, 10),  # Slightly harder
            duration=game_config.incident.spread_duration,
        )

        # Update original incident spread tracking
        incident.spread_to_room(str(new_room.id))
        db_session.add(incident)
        incident_publishing.record_event(db_session, incident, "spread", f"Spread to {new_room.name}.")

        logger.warning(
            f"Incident {incident.type} spread from {current_room.name} to {new_room.name} "
            f"(difficulty {new_incident.difficulty})"
        )
        return True

    return False
