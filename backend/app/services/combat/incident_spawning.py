"""Incident creation: spawn gating, room selection, spreading, and spawn locks."""

import logging
import random
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import db_locks
from app.core.enums import IncidentType
from app.core.game_config import game_config
from app.crud import game_state_crud
from app.crud.dweller import dweller as crud_dweller
from app.crud.incident import incident_crud
from app.crud.room import room as room_crud
from app.crud.user_profile import profile_crud
from app.crud.vault import vault as vault_crud
from app.models.game_state import GameState
from app.models.incident import Incident, hazard_team_for
from app.models.incident_event import IncidentEvent
from app.models.room import Room
from app.models.vault import Vault
from app.services.combat import incident_publishing
from app.services.combat.incident_publishing import INCIDENT_NAMES
from app.utils.reward_delivery import persist_reward_change

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

    # Spawns need a watching player: the vault overview must have sent a
    # visibility-gated heartbeat inside the presence window, so background
    # tabs start nothing.
    presence_window = game_config.incident.spawn_presence_seconds
    if (
        game_state is None
        or game_state.last_presence_at is None
        or (datetime.utcnow() - game_state.last_presence_at).total_seconds() > presence_window
    ):
        logger.debug(f"Vault {vault_id} has no fresh presence heartbeat, suppressing incident spawn")
        return False

    vault = await vault_crud.get_or_none(db_session, vault_id, include_deleted=True)
    if is_spawning_disabled(vault):
        logger.debug(f"Incidents are disabled for vault {vault_id}")
        return False

    if await crud_dweller.count_living_in_vault(db_session, vault_id) < game_config.incident.min_vault_population:
        return False

    # Check if max active incidents reached
    active_incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
    if is_at_incident_cap(active_incidents):
        return False

    # Check cooldown period (if there are any incidents, check the most recent one)
    if active_incidents:
        most_recent = max(active_incidents, key=lambda i: i.start_time)
        seconds_since_last = (datetime.utcnow() - most_recent.start_time).total_seconds()
        if seconds_since_last < game_config.incident.spawn_cooldown_seconds:
            return False

    # Time-based cap: limit spawn chance growth to prevent bursts
    # Cap hours_passed to prevent excessive spawn chance after long offline periods
    hours_passed = min(seconds_passed / 3600, 2.0)  # Cap at 2 hours worth of chance
    room_count = await room_crud.count_by_vault(db_session, vault_id)
    spawn_chance = game_config.incident.get_spawn_rate(room_count) * hours_passed

    # Random roll
    return random.random() < spawn_chance


def roll_incident_type(population: int, mode: str) -> IncidentType:
    """Pick a spawn type from the balance weights this population and mode qualify for."""
    weights = game_config.incident.get_spawn_weights(population, mode)
    return random.choices(list(weights), weights=list(weights.values()), k=1)[0]


async def spawn_incident(
    db_session: AsyncSession,
    vault_id: UUID4,
    incident_type: IncidentType | None = None,
    *,
    target_room_id: UUID4 | None = None,
    difficulty_bonus: int = 0,
    start_delay_seconds: float = 0,
) -> Incident | None:
    """Spawn a new incident in a random occupied room, or in the requested target room.
    Raiders and Deathclaws spawn at vault door (0,0) and spread inward.

    Rules enforced:
    - Only one incident type per vault at a time
    - Only one incident per room
    - Never spawn in elevators

    Args:
        db_session: Database session
        vault_id: ID of the vault
        incident_type: Type of incident (rolled from the balance weights if None)
        target_room_id: Spawn in this room instead of a random eligible one
        difficulty_bonus: Extra difficulty added to the rolled value (capped at 10)
        start_delay_seconds: Reserve the incident now and activate it after this grace period

    Returns:
        Incident or None if no suitable room found
    """
    if not await db_locks.try_advisory_xact_lock(db_session, f"incident-spawn:{vault_id}"):
        return None

    vault = await vault_crud.get_or_none(db_session, vault_id, include_deleted=True)
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

    # A vault already fighting a hazard gets more of the same; only a fresh wave
    # rolls from the balance weights. Explicit types stay available to
    # administrative and test callers.
    if incident_type is None:
        if active_types:
            incident_type = next(iter(active_types))
        else:
            population = await crud_dweller.count_living_in_vault(db_session, vault_id)
            incident_type = roll_incident_type(population, vault.vault_mode)

    # If type specified but vault has different type, don't spawn
    if active_types and incident_type not in active_types:
        logger.info(f"Cannot spawn {incident_type} in vault {vault_id} - vault already has {active_types}")
        return None

    # Get rooms that already have active incidents
    rooms_with_incidents = await incident_crud.get_rooms_with_active_incidents(db_session, vault_id)

    if target_room_id is None:
        target_room = await select_spawn_room(db_session, vault_id, incident_type, rooms_with_incidents)
    elif target_room_id in rooms_with_incidents:
        logger.info(f"Cannot spawn {incident_type} in room {target_room_id} - room already has an incident")
        return None
    else:
        target_room = await room_crud.get_or_none(db_session, target_room_id)
        if target_room is None or target_room.vault_id != vault_id or target_room.name.lower() == "elevator":
            logger.info(f"Cannot spawn {incident_type} in room {target_room_id} - room is not eligible")
            return None

    if target_room is None:
        return None

    difficulty = random.randint(*game_config.incident.get_difficulty_range(incident_type))
    difficulty = min(10, difficulty + max(0, difficulty_bonus))

    incident = await incident_crud.create(
        db_session,
        vault_id=vault_id,
        room_id=target_room.id,
        incident_type=incident_type,
        difficulty=difficulty,
        duration=game_config.incident.spread_duration,
        commit=False,
    )
    if start_delay_seconds > 0:
        incident.start_time = datetime.utcnow() + timedelta(seconds=start_delay_seconds)
        incident_publishing.record_event(db_session, incident, "pending", "Rush failure animation in progress.")
        await persist_reward_change(db_session, incident)
    else:
        await activate_incident(db_session, incident, vault, target_room)
    return incident


async def activate_incident(
    db_session: AsyncSession,
    incident: Incident,
    vault: Vault,
    target_room: Room,
    pending_event: IncidentEvent | None = None,
) -> None:
    """Start an ordinary or reserved incident through the same announcement/dispatch path."""
    profile = await profile_crud.get_by_user_id(db_session, vault.user_id)
    auto_paused = bool(profile and (profile.preferences or {}).get("pause_on_incident") is True)
    if auto_paused:
        game_state = await game_state_crud.get_or_create(db_session, vault.id, commit=False)
        game_state.pause()
        db_session.add(game_state)

    incident_name = INCIDENT_NAMES.get(incident.type, str(incident.type))
    message = f"{incident_name} detected in {target_room.name}."
    if pending_event is None:
        incident_publishing.record_event(db_session, incident, "spawned", message)
    else:
        pending_event.kind = "spawned"
        pending_event.message = message
        db_session.add(pending_event)
    await profile_crud.increment_statistic(db_session, vault.user_id, "total_incidents", commit=False)
    # Persist activation and auto-pause together before any combat round can run.
    await db_session.commit()

    logger.info(
        "Spawned %s (difficulty %s) in room %s of vault %s",
        incident.type,
        incident.difficulty,
        target_room.name,
        vault.id,
    )
    if hazard_team_for(incident.type):
        from app.services.hazard_team_service import hazard_team_service

        if await hazard_team_service.dispatch_to_incident(db_session, incident):
            await db_session.commit()

    await incident_publishing.notify_spawn(db_session, incident, target_room.name, incident_name, incident.difficulty)
    await incident_publishing.publish_sse(
        incident, "incident_spawned", room_name=target_room.name, is_paused=auto_paused
    )


async def select_spawn_room(
    db_session: AsyncSession, vault_id: UUID4, incident_type: IncidentType, rooms_with_incidents: set[UUID4]
) -> Room | None:
    """Pick the spawn room for an incident type; None when no suitable room exists."""
    # Determine where to spawn based on incident type
    if incident_type.value in game_config.incident.vault_door_incidents:
        # External attacks spawn at vault door (0,0) and spread inward
        target_room = await room_crud.get_room_by_coordinates(
            db_session=db_session,
            vault_id=vault_id,
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
        spread_vault = await vault_crud.get(db_session, incident.vault_id)
        if spread_vault is not None:
            await profile_crud.increment_statistic(db_session, spread_vault.user_id, "total_incidents", commit=False)

        logger.warning(
            f"Incident {incident.type} spread from {current_room.name} to {new_room.name} "
            f"(difficulty {new_incident.difficulty})"
        )
        return True

    return False
