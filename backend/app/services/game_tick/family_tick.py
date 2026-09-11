"""Family and vault-event tick logic for the game loop.

Extracted verbatim from ``GameLoopService``: weighted random vault events,
room-shared relationship affinity updates, conception/pregnancy/birth
processing, and child aging. ``GameLoopService`` keeps same-named thin
delegates. Orchestration helpers dispatch through the service instance so
existing ``GameLoopService`` test patches keep intercepting.
"""

import logging
from types import ModuleType
from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RelationshipTypeEnum
from app.core.game_config import game_config
from app.crud import dweller as crud_dweller
from app.crud.relationship import relationship_crud as crud_relationship
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.pregnancy import Pregnancy
from app.models.relationship import Relationship
from app.services.vault_service import vault_service
from app.utils.dwellers import group_dwellers_by_room

if TYPE_CHECKING:
    from app.services.game_loop import GameLoopService

logger = logging.getLogger(__name__)


async def process_events(
    db_session: AsyncSession,
    vault_id: UUID4,
    seconds_passed: int,
    game_state: GameState | None = None,
    *,
    rng: ModuleType,
) -> dict:
    """Fire weighted random vault events (raider scout, resource cache, wanderer).

    ``rng`` is the ``random`` module passed in by the facade so tests can keep
    patching ``app.services.game_loop.random``.
    """
    # Import here to avoid circular import
    from app.models.incident import IncidentType
    from app.models.notification import NotificationPriority, NotificationType
    from app.services.combat.incident_service import incident_service
    from app.services.notification_service import notification_service

    stats = {"triggered": 0, "events": []}

    # Events do not punish players for time away from the vault
    if game_state and not game_state.is_user_online():
        return stats

    # Minimum population gate
    population = await crud_dweller.count_in_vault(db_session, vault_id)
    if population < game_config.vault_event.min_vault_population:
        return stats

    # Time-based spawn chance (capped like incidents)
    hours_passed = min(seconds_passed / 3600, 2.0)
    if rng.random() >= game_config.vault_event.spawn_chance_per_hour * hours_passed:
        return stats

    # Pick weighted event type
    weights = {
        "resource_cache": game_config.vault_event.weight_resource_cache,
        "wanderer": game_config.vault_event.weight_wanderer,
        "raider_scout": game_config.vault_event.weight_raider_scout,
    }
    event_type = rng.choices(list(weights), weights=list(weights.values()), k=1)[0]

    vault = await vault_crud.get(db_session, vault_id)
    if not vault or not vault.user_id:
        return stats

    if event_type == "raider_scout":
        # Fail fast: the raider event can only fire when an incident can
        # actually spawn. Check the blocking states before calling the
        # service, which raises on them (the game-tick boundary handler
        # would otherwise log a disabled vault as an error every tick).
        if not vault.incidents_disabled:
            from app.crud.incident import incident_crud

            active_incidents = await incident_crud.get_active_by_vault(db_session, vault_id)
            if len(active_incidents) < game_config.incident.max_active_incidents:
                incident = await incident_service.spawn_incident(db_session, vault_id, IncidentType.RADSCORPION_ATTACK)
                if incident:
                    stats["triggered"] = 1
                    stats["events"].append({"type": "raider_scout", "incident_id": str(incident.id)})
        return stats

    # Positive events award caps
    if event_type == "resource_cache":
        caps = rng.randint(
            game_config.vault_event.resource_cache_caps_min, game_config.vault_event.resource_cache_caps_max
        )
        title, message = "Resource Cache Found!", f"Dwellers found a hidden cache worth {caps} caps!"
    else:  # wanderer
        caps = rng.randint(game_config.vault_event.wanderer_caps_min, game_config.vault_event.wanderer_caps_max)
        title, message = "Wanderer at the Door", f"A wanderer gifted the vault {caps} caps before moving on!"

    await vault_service.deposit_caps(db_session=db_session, vault_obj=vault, amount=caps)
    await notification_service.create_and_send(
        db_session,
        user_id=vault.user_id,
        vault_id=vault_id,
        notification_type=NotificationType.ACHIEVEMENT_UNLOCKED,
        priority=NotificationPriority.NORMAL,
        title=title,
        message=message,
        meta_data={"event_type": event_type, "caps": caps},
    )
    stats["triggered"] = 1
    stats["events"].append({"type": event_type, "caps": caps})
    logger.info(f"Vault event {event_type} triggered in vault {vault_id}")
    return stats


async def fetch_existing_relationships(db_session: AsyncSession, dweller_ids: set[UUID4]) -> list[Relationship]:
    """Batch fetch all relationships for a set of dweller IDs."""
    return await crud_relationship.get_involving_any(db_session, dweller_ids)


def build_relationships_map(relationships: list[Relationship]) -> dict[tuple[UUID4, UUID4], Relationship]:
    """Build a bidirectional lookup map for relationships."""
    relationships_map = {}
    for rel in relationships:
        key1 = (rel.dweller_1_id, rel.dweller_2_id)
        key2 = (rel.dweller_2_id, rel.dweller_1_id)
        relationships_map[key1] = rel
        relationships_map[key2] = rel
    return relationships_map


def affinity_gain(dweller1: Dweller, dweller2: Dweller) -> int:
    """Give a small bonus when both dwellers are highly charismatic."""
    return game_config.relationship.affinity_increase_per_tick + min(dweller1.charisma, dweller2.charisma) // 10


async def update_pair_affinity(
    db_session: AsyncSession,
    dweller1: Dweller,
    dweller2: Dweller,
    relationships_map: dict[tuple[UUID4, UUID4], Relationship],
    new_relationships: list[tuple[Relationship, int]],
) -> int:
    """Update affinity for a pair of dwellers, creating relationship if needed."""
    from app.services.relationship_service import relationship_service

    key = (dweller1.id, dweller2.id)
    relationship = relationships_map.get(key)

    if not relationship:
        # Create new relationship
        relationship = Relationship(
            dweller_1_id=dweller1.id,
            dweller_2_id=dweller2.id,
            relationship_type=RelationshipTypeEnum.ACQUAINTANCE,
            affinity=0,
        )
        new_relationships.append((relationship, affinity_gain(dweller1, dweller2)))
        relationships_map[key] = relationship
        relationships_map[(dweller2.id, dweller1.id)] = relationship
        return 0  # New relationships updated later after commit

    # Only update affinity for existing (persistent) relationships
    if not any(new_relationship is relationship for new_relationship, _ in new_relationships):
        await relationship_service.increase_affinity(
            db_session,
            relationship.dweller_1_id,
            relationship.dweller_2_id,
            affinity_gain(dweller1, dweller2),
        )
        return 1
    return 0


async def create_new_relationships(db_session: AsyncSession, new_relationships: list[tuple[Relationship, int]]) -> int:
    """Bulk create new relationships and update their affinity."""
    from app.services.relationship_service import relationship_service

    if not new_relationships:
        return 0

    db_session.add_all([relationship for relationship, _ in new_relationships])
    await db_session.commit()

    # Update affinity for newly created relationships
    count = 0
    for relationship, gain in new_relationships:
        await relationship_service.increase_affinity(
            db_session,
            relationship.dweller_1_id,
            relationship.dweller_2_id,
            gain,
        )
        count += 1
    return count


async def update_room_relationships(service: "GameLoopService", db_session: AsyncSession, vault_id: UUID4) -> dict:
    """Update relationship affinity for dwellers sharing living quarters.

    Relationship helpers are reached through ``service`` so patches on the
    ``GameLoopService`` instance keep intercepting (existing test contract).
    """
    stats = {"relationships_updated": 0}

    try:
        dwellers = await crud_dweller.get_living_quarters_dwellers(db_session, vault_id)
        if not dwellers:
            return stats

        # Group dwellers by room
        room_dwellers = group_dwellers_by_room(list(dwellers))

        # Batch fetch all existing relationships for these dwellers
        all_dweller_ids = {d.id for d in dwellers}
        existing_relationships = await service._fetch_existing_relationships(db_session, all_dweller_ids)

        relationships_map = service._build_relationships_map(existing_relationships)

        new_relationships: list[tuple[Relationship, int]] = []
        for room_dweller_list in room_dwellers.values():
            if len(room_dweller_list) < 2:
                continue

            for i, dweller1 in enumerate(room_dweller_list):
                for dweller2 in room_dweller_list[i + 1 :]:
                    updated = await service._update_pair_affinity(
                        db_session, dweller1, dweller2, relationships_map, new_relationships
                    )
                    stats["relationships_updated"] += updated

        # Bulk add new relationships and commit
        stats["relationships_updated"] += await service._create_new_relationships(db_session, new_relationships)

    except SQLAlchemyError as e:
        logger.error(f"Database error updating relationships for vault {vault_id}: {e}", exc_info=True)
    except ValueError as e:
        logger.error(f"Validation error updating relationships for vault {vault_id}: {e}", exc_info=True)

    return stats


async def _deliver_due_baby(db_session: AsyncSession, vault_id: UUID4, pregnancy: Pregnancy) -> bool:
    """Deliver one due pregnancy; per-delivery errors are logged, not raised."""
    from app.services.family.breeding_service import breeding_service

    try:
        baby = await breeding_service.deliver_baby(db_session, pregnancy.id)
    except (SQLAlchemyError, ValueError) as e:
        logger.error(f"Error delivering baby for pregnancy {pregnancy.id}: {e}", exc_info=True)
        return False
    if baby:
        logger.info(f"Baby born in vault {vault_id}: {baby.first_name} {baby.last_name}")
    return bool(baby)


async def process_pregnancies_and_births(db_session: AsyncSession, vault_id: UUID4) -> dict:
    """Check for conception and process due pregnancies."""
    from app.services.family.breeding_service import breeding_service

    stats = {"conceptions": 0, "births": 0}

    # Check for conception
    try:
        new_pregnancies = await breeding_service.check_for_conception(db_session, vault_id)
        stats["conceptions"] = len(new_pregnancies)
        if new_pregnancies:
            logger.info(f"New pregnancies in vault {vault_id}: {len(new_pregnancies)}")
    except SQLAlchemyError as e:
        logger.error(f"Database error checking for conception in vault {vault_id}: {e}", exc_info=True)
    except ValueError as e:
        logger.error(f"Validation error checking for conception in vault {vault_id}: {e}", exc_info=True)

    # Check for due pregnancies and deliver babies
    try:
        due_pregnancies = await breeding_service.check_due_pregnancies(db_session, vault_id)
        for pregnancy in due_pregnancies:
            if await _deliver_due_baby(db_session, vault_id, pregnancy):
                stats["births"] += 1
    except SQLAlchemyError as e:
        logger.error(f"Database error checking due pregnancies in vault {vault_id}: {e}", exc_info=True)

    return stats


async def age_children(db_session: AsyncSession, vault_id: UUID4) -> dict:
    """Age children to adults if they're ready."""
    from app.services.family.breeding_service import breeding_service

    stats = {"children_aged": 0}

    try:
        aged_children = await breeding_service.age_children(db_session, vault_id)
        stats["children_aged"] = len(aged_children)
        if aged_children:
            logger.info(f"Children aged to adults in vault {vault_id}: {len(aged_children)}")
    except SQLAlchemyError as e:
        logger.error(f"Database error aging children in vault {vault_id}: {e}", exc_info=True)
    except ValueError as e:
        logger.error(f"Validation error aging children in vault {vault_id}: {e}", exc_info=True)

    return stats


async def process_breeding(service: "GameLoopService", db_session: AsyncSession, vault_id: UUID4) -> dict:
    """Process relationships and breeding for a vault.

    - Update relationship affinity for dwellers in the same room
    - Check for conception in living quarters
    - Process due pregnancies and deliver babies
    - Age children to adults
    """
    # Update relationship affinity
    relationship_stats = await service._update_room_relationships(db_session, vault_id)

    # Process pregnancies and births
    pregnancy_stats = await service._process_pregnancies_and_births(db_session, vault_id)

    # Age children
    aging_stats = await service._age_children(db_session, vault_id)

    # Combine stats
    return {
        "relationships_updated": relationship_stats["relationships_updated"],
        "conceptions": pregnancy_stats["conceptions"],
        "births": pregnancy_stats["births"],
        "children_aged": aging_stats["children_aged"],
    }
