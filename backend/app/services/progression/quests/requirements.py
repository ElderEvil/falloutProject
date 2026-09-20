"""Requirement policy for quests: stateless decision rules, CRUD-backed vault gate.

Replaces the former ``prerequisite_service`` singleton. This is a policy, not a
service — no orchestration, no transactions, no events, no state. The vault-level
entry point reads through CRUD; the party-level entry point and all party
validators are pure.
"""

import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import SPECIAL_STATS
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.options.identity_modifiers import effective_stat
from app.utils.objective_constants import normalize_room_type

logger = logging.getLogger(__name__)


async def vault_missing_requirements(db_session: AsyncSession, vault_id: UUID4, quest: Quest) -> list[str]:
    """Vault-level requirement gates for a quest, as human-readable reasons.

    Only mandatory requirements gate a quest; an unmet *optional* one is
    debug-logged and skipped. Dispatch is fail-closed: an unknown requirement type
    or a validator error is logged and treated as not met.
    """
    missing: list[str] = []
    requirements: list[QuestRequirement] = quest.quest_requirements

    if not requirements:
        return missing

    for req in requirements:
        is_met = await _check_requirement(db_session, vault_id, req)

        if not is_met:
            if not req.is_mandatory:
                logger.debug(
                    f"Optional requirement not met for quest '{quest.title}': "
                    f"{req.requirement_type} - {req.requirement_data}"
                )
                continue

            description = _describe_requirement(req)
            missing.append(description)

    if missing:
        logger.info(f"Vault {vault_id} missing {len(missing)} requirement(s) for quest '{quest.title}': {missing}")

    return missing


async def validate_level_requirement(
    db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
) -> bool:
    required_level = requirement_data.get("level", 1)
    required_count = requirement_data.get("count", 1)

    matching_count = await crud.dweller.count_alive_in_vault(db_session, vault_id, min_level=required_level)
    return matching_count >= required_count


async def validate_item_requirement(
    db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
) -> bool:
    item_name = requirement_data.get("item_name", "")
    required_count = requirement_data.get("count", 1)

    storage = await crud.storage.get_storage_by_vault(db_session, vault_id)
    storage_count = 0
    if storage:
        storage_count = await crud.weapon.count_in_storage_by_name(db_session, storage.id, item_name)
        storage_count += await crud.outfit.count_in_storage_by_name(db_session, storage.id, item_name)

    equipped_count = await crud.weapon.count_equipped_by_name(db_session, vault_id, item_name)
    equipped_count += await crud.outfit.count_equipped_by_name(db_session, vault_id, item_name)

    return storage_count + equipped_count >= required_count


async def validate_attack_requirement(
    db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
) -> bool:
    required_attack = requirement_data.get("attack", 0)
    required_count = requirement_data.get("count", 1)

    matching_count = await crud.dweller.count_alive_with_weapon_attack(db_session, vault_id, required_attack)
    return matching_count >= required_count


async def validate_stat_requirement(
    db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
) -> bool:
    stat = requirement_data.get("stat")
    if stat not in SPECIAL_STATS:
        return False
    min_value = requirement_data.get("value", 1)
    required_count = requirement_data.get("count", 1)

    matching_count = await crud.dweller.count_living_with_effective_stat(db_session, vault_id, stat, min_value)
    return matching_count >= required_count


async def validate_room_requirement(
    db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
) -> bool:
    room_type = normalize_room_type(requirement_data.get("room_type"))
    required_count = requirement_data.get("count", 1)
    if room_type is None:
        return False

    room_names = await crud.dweller.count_room_names_by_type(db_session, vault_id)
    return sum(normalize_room_type(name) == room_type for name in room_names) >= required_count


async def validate_dweller_count_requirement(
    db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
) -> bool:
    required_count = requirement_data.get("count", 0)

    current_count = await crud.dweller.count_alive_in_vault(db_session, vault_id)
    return current_count >= required_count


async def validate_quest_completed_requirement(
    db_session: AsyncSession, vault_id: UUID4, requirement_data: dict[str, Any]
) -> bool:
    quest_id = requirement_data.get("quest_id")
    if not quest_id:
        logger.warning("quest_completed requirement missing quest_id")
        return False

    try:
        quest_id = UUID(str(quest_id))
    except (TypeError, ValueError):
        logger.warning(f"quest_completed requirement has invalid quest_id: {quest_id}")
        return False

    link = await crud.quest_crud.get_link(db_session, quest_id=quest_id, vault_id=vault_id)
    return link is not None and link.is_completed


async def _check_requirement(db_session: AsyncSession, vault_id: UUID4, requirement: QuestRequirement) -> bool:
    """Dispatch to the correct validation function based on requirement type."""
    validators = {
        RequirementType.LEVEL: validate_level_requirement,
        RequirementType.ITEM: validate_item_requirement,
        RequirementType.ROOM: validate_room_requirement,
        RequirementType.DWELLER_COUNT: validate_dweller_count_requirement,
        RequirementType.QUEST_COMPLETED: validate_quest_completed_requirement,
        RequirementType.ATTACK: validate_attack_requirement,
        RequirementType.STAT: validate_stat_requirement,
    }

    validator = validators.get(requirement.requirement_type)
    if not validator:
        logger.warning(f"Unknown requirement type: {requirement.requirement_type}")
        return False

    try:
        return await validator(db_session, vault_id, requirement.requirement_data)
    except Exception:
        logger.exception(f"Error validating {requirement.requirement_type} requirement for vault {vault_id}")
        return False


def party_missing_requirements(party_dwellers: Sequence[Dweller], quest: Quest) -> list[str]:
    """Missing party-level requirements for a quest, given the dwellers being sent.

    LEVEL, ITEM, ATTACK and STAT gates are checked against the party itself — the
    dwellers actually dispatched — while ROOM, DWELLER_COUNT and QUEST_COMPLETED
    stay vault-level and keep their validation in ``vault_missing_requirements``.
    """
    missing: list[str] = []
    for req in quest.quest_requirements:
        if not req.is_mandatory:
            continue
        if req.requirement_type == RequirementType.LEVEL and not _party_meets_level(
            party_dwellers, req.requirement_data
        ):
            missing.append(_describe_level(req.requirement_data))
        elif req.requirement_type == RequirementType.ITEM and not _party_meets_item(
            party_dwellers, req.requirement_data
        ):
            missing.append(_describe_party_item(req.requirement_data))
        elif req.requirement_type == RequirementType.ATTACK and not _party_meets_attack(
            party_dwellers, req.requirement_data
        ):
            missing.append(_describe_party_attack(req.requirement_data))
        elif req.requirement_type == RequirementType.STAT and not _party_meets_stat(
            party_dwellers, req.requirement_data
        ):
            missing.append(_describe_party_stat(req.requirement_data))
    return missing


def _party_meets_level(party_dwellers: Sequence[Dweller], requirement_data: dict[str, Any]) -> bool:
    required_level = requirement_data.get("level", 1)
    required_count = requirement_data.get("count", 1)
    matching = sum(1 for dweller in party_dwellers if dweller.level >= required_level)
    return matching >= required_count


def _party_meets_item(party_dwellers: Sequence[Dweller], requirement_data: dict[str, Any]) -> bool:
    item_name = requirement_data.get("item_name", "")
    required_count = requirement_data.get("count", 1)
    matching = sum(
        1
        for dweller in party_dwellers
        if (dweller.weapon is not None and dweller.weapon.name == item_name)
        or (dweller.outfit is not None and dweller.outfit.name == item_name)
    )
    return matching >= required_count


def _party_meets_attack(party_dwellers: Sequence[Dweller], requirement_data: dict[str, Any]) -> bool:
    required_attack = requirement_data.get("attack", 0)
    required_count = requirement_data.get("count", 1)
    matching = sum(
        1
        for dweller in party_dwellers
        if dweller.weapon is not None and (dweller.weapon.damage_min + dweller.weapon.damage_max) / 2 >= required_attack
    )
    return matching >= required_count


def _party_meets_stat(party_dwellers: Sequence[Dweller], requirement_data: dict[str, Any]) -> bool:
    stat = requirement_data.get("stat")
    min_value = requirement_data.get("value", 1)
    required_count = requirement_data.get("count", 1)
    matching = 0
    for dweller in party_dwellers:
        if stat in SPECIAL_STATS and effective_stat(dweller, stat) >= min_value:
            matching += 1
    return matching >= required_count


def _describe_level(data: dict[str, Any]) -> str:
    level = data.get("level", "?")
    count = data.get("count", 1)
    if count > 1:
        return f"Need {count} dweller(s) at level {level} or higher"
    return f"Need a dweller at level {level} or higher"


def _describe_item(data: dict[str, Any]) -> str:
    item_name = data.get("item_name", "Unknown item")
    count = data.get("count", 1)
    if count > 1:
        return f"Need {count}x {item_name} in storage"
    return f"Need {item_name} in storage"


def _describe_party_item(data: dict[str, Any]) -> str:
    item_name = data.get("item_name", "Unknown item")
    count = data.get("count", 1)
    if count > 1:
        return f"Need {count} party dweller(s) equipped with {item_name}"
    return f"Need a party dweller equipped with {item_name}"


def _describe_attack(data: dict[str, Any]) -> str:
    attack = data.get("attack", "?")
    count = data.get("count", 1)
    if count > 1:
        return f"Need {count} dweller(s) with {attack}+ attack"
    return f"Need a dweller with {attack}+ attack"


def _describe_party_attack(data: dict[str, Any]) -> str:
    attack = data.get("attack", "?")
    count = data.get("count", 1)
    if count > 1:
        return f"Need {count} party dweller(s) with {attack}+ attack"
    return f"Need a party dweller with {attack}+ attack"


def _describe_stat(data: dict[str, Any]) -> str:
    label = str(data.get("stat", "?")).replace("_", " ").title()
    value = data.get("value", "?")
    count = data.get("count", 1)
    if count > 1:
        return f"Need {count} dweller(s) with {label} {value}+"
    return f"Need a dweller with {label} {value}+"


def _describe_party_stat(data: dict[str, Any]) -> str:
    label = str(data.get("stat", "?")).replace("_", " ").title()
    value = data.get("value", "?")
    count = data.get("count", 1)
    if count > 1:
        return f"Need {count} party dweller(s) with {label} {value}+"
    return f"Need a party dweller with {label} {value}+"


def _describe_room(data: dict[str, Any]) -> str:
    room_type = data.get("room_type", "Unknown room")
    room_display = room_type.replace("_", " ").title()
    count = data.get("count", 1)
    if count > 1:
        return f"Need {count} {room_display} room(s) built"
    return f"Need {room_display} built"


def _describe_dweller_count(data: dict[str, Any]) -> str:
    count = data.get("count", 0)
    return f"Need at least {count} dwellers in vault"


def _describe_quest_completed(data: dict[str, Any]) -> str:
    quest_id = data.get("quest_id", "Unknown")
    return f"Need to complete prerequisite quest (ID: {quest_id})"


def _describe_requirement(requirement: QuestRequirement) -> str:
    describers = {
        RequirementType.LEVEL: _describe_level,
        RequirementType.ITEM: _describe_item,
        RequirementType.ROOM: _describe_room,
        RequirementType.DWELLER_COUNT: _describe_dweller_count,
        RequirementType.QUEST_COMPLETED: _describe_quest_completed,
        RequirementType.ATTACK: _describe_attack,
        RequirementType.STAT: _describe_stat,
    }

    describer = describers.get(requirement.requirement_type)
    if not describer:
        return f"Unknown requirement: {requirement.requirement_type}"
    return describer(requirement.requirement_data)
