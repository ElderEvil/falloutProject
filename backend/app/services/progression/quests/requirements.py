"""Requirement policy for quests: stateless decision rules over a vault facts snapshot.

A policy, not a service — no orchestration, transactions, events, or state. The vault gate reads a
point-in-time :class:`VaultFacts` snapshot, loaded once per request, so a quest list costs a fixed handful
of aggregate queries instead of one to four per requirement; party entry and validators stay pure.
"""

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import SPECIAL_STATS, RequirementType
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.options.identity_modifiers import effective_stat
from app.utils.objective_constants import normalize_room_type

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VaultFacts:
    """Point-in-time vault snapshot the requirement gates read, so evaluation needs no DB session.

    Loaded by :func:`load_vault_facts`. Counts are precomputed per requirement dimension: dweller levels,
    effective SPECIAL values, equipped weapon damage, owned/equipped item names, room types and completed
    quest ids — each check is then a Python count over the snapshot.
    """

    alive_dweller_count: int
    max_dweller_level: int
    dweller_levels: tuple[int, ...]
    effective_stats: Mapping[str, tuple[int, ...]]
    weapon_damage_sums: tuple[int, ...]
    item_counts: Mapping[str, int]
    room_type_counts: Mapping[str, int]
    completed_quest_ids: frozenset[UUID]

    def count_at_level(self, min_level: int) -> int:
        """Living dwellers at or above ``min_level``."""
        return sum(1 for level in self.dweller_levels if level >= min_level)

    def count_with_stat(self, stat: str, min_value: int) -> int:
        """Living dwellers whose effective ``stat`` is at or above ``min_value``."""
        return sum(1 for value in self.effective_stats.get(stat, ()) if value >= min_value)

    def count_with_attack(self, min_attack: int) -> int:
        """Living dwellers whose equipped weapon's average damage reaches ``min_attack``."""
        return sum(1 for damage_sum in self.weapon_damage_sums if damage_sum >= 2 * min_attack)

    def count_item(self, item_name: str) -> int:
        """Copies of an item owned in storage plus equipped, matched case-insensitively."""
        return self.item_counts.get(item_name.lower(), 0)

    def count_rooms(self, room_type: str) -> int:
        """Rooms of a normalized type."""
        return self.room_type_counts.get(room_type, 0)


async def load_vault_facts(db_session: AsyncSession, vault_id: UUID) -> VaultFacts:
    """Snapshot everything the vault requirement gates need in a fixed, small number of queries.

    One statement for living dwellers (weapon/outfit/pet eagerly loaded), one per item type for storage and
    equipped name counts, one for room names and one for completed quests.
    """
    dwellers = await crud.dweller.get_living_with_equipment(db_session, vault_id)

    item_counts: Counter[str] = Counter()
    storage = await crud.storage.get_storage_by_vault(db_session, vault_id)
    if storage is not None:
        item_counts.update(await crud.weapon.count_by_name_in_storage(db_session, storage.id))
        item_counts.update(await crud.outfit.count_by_name_in_storage(db_session, storage.id))
    item_counts.update(await crud.weapon.count_equipped_by_name(db_session, vault_id))
    item_counts.update(await crud.outfit.count_equipped_by_name(db_session, vault_id))

    room_type_counts: Counter[str] = Counter()
    for name in await crud.dweller.count_room_names_by_type(db_session, vault_id):
        normalized = normalize_room_type(name)
        if normalized is not None:
            room_type_counts[normalized] += 1

    return VaultFacts(
        alive_dweller_count=len(dwellers),
        max_dweller_level=max((dweller.level for dweller in dwellers), default=0),
        dweller_levels=tuple(dweller.level for dweller in dwellers),
        effective_stats={stat: tuple(effective_stat(dweller, stat) for dweller in dwellers) for stat in SPECIAL_STATS},
        weapon_damage_sums=tuple(
            dweller.weapon.damage_min + dweller.weapon.damage_max for dweller in dwellers if dweller.weapon is not None
        ),
        item_counts=dict(item_counts),
        room_type_counts=dict(room_type_counts),
        completed_quest_ids=frozenset(await crud.quest_crud.get_completed_quest_ids(db_session, vault_id)),
    )


async def vault_requirement_states(
    db_session: AsyncSession,
    vault_id: UUID,
    quest: Quest,
    *,
    facts: VaultFacts | None = None,
) -> dict[UUID, bool]:
    """Per-requirement vault-scoped verdicts keyed by requirement id.

    Every requirement (mandatory or optional) goes through the same fail-closed dispatch as the availability
    gate, so the UI shows which requirement blocks a quest. Pass ``facts`` to reuse a snapshot a batch caller
    already loaded; otherwise one is built on demand.
    """
    requirements: list[QuestRequirement] = quest.quest_requirements
    if facts is None and _requires_facts(requirements):
        facts = await load_vault_facts(db_session, vault_id)
    return {req.id: _check_requirement(vault_id, req, facts) for req in requirements}


async def vault_missing_requirements(
    db_session: AsyncSession,
    vault_id: UUID,
    quest: Quest,
    *,
    facts: VaultFacts | None = None,
) -> list[str]:
    """Vault-level requirement gates for a quest, as human-readable reasons.

    Only mandatory requirements gate; unmet optional ones are debug-logged and skipped. Fail-closed: unknown
    types or validator errors are logged and treated as not met. Pass ``facts`` to reuse a snapshot a batch
    caller already loaded; otherwise one is built on demand.
    """
    missing: list[str] = []
    requirements: list[QuestRequirement] = quest.quest_requirements

    if not requirements:
        return missing

    if facts is None and _requires_facts(requirements):
        facts = await load_vault_facts(db_session, vault_id)

    for req in requirements:
        is_met = _check_requirement(vault_id, req, facts)

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
    db_session: AsyncSession, vault_id: UUID, requirement_data: dict[str, Any]
) -> bool:
    """Evaluate a single LEVEL gate; convenience entry point for callers without a snapshot."""
    return _level_met(await load_vault_facts(db_session, vault_id), requirement_data)


async def validate_item_requirement(db_session: AsyncSession, vault_id: UUID, requirement_data: dict[str, Any]) -> bool:
    """Evaluate a single ITEM gate; convenience entry point for callers without a snapshot."""
    return _item_met(await load_vault_facts(db_session, vault_id), requirement_data)


async def validate_attack_requirement(
    db_session: AsyncSession, vault_id: UUID, requirement_data: dict[str, Any]
) -> bool:
    """Evaluate a single ATTACK gate; convenience entry point for callers without a snapshot."""
    return _attack_met(await load_vault_facts(db_session, vault_id), requirement_data)


async def validate_stat_requirement(db_session: AsyncSession, vault_id: UUID, requirement_data: dict[str, Any]) -> bool:
    """Evaluate a single STAT gate; convenience entry point for callers without a snapshot."""
    return _stat_met(await load_vault_facts(db_session, vault_id), requirement_data)


async def validate_room_requirement(db_session: AsyncSession, vault_id: UUID, requirement_data: dict[str, Any]) -> bool:
    """Evaluate a single ROOM gate; convenience entry point for callers without a snapshot."""
    return _room_met(await load_vault_facts(db_session, vault_id), requirement_data)


async def validate_dweller_count_requirement(
    db_session: AsyncSession, vault_id: UUID, requirement_data: dict[str, Any]
) -> bool:
    """Evaluate a single DWELLER_COUNT gate; convenience entry point for callers without a snapshot."""
    return _dweller_count_met(await load_vault_facts(db_session, vault_id), requirement_data)


async def validate_quest_completed_requirement(
    db_session: AsyncSession, vault_id: UUID, requirement_data: dict[str, Any]
) -> bool:
    """Evaluate a single QUEST_COMPLETED gate; convenience entry point for callers without a snapshot."""
    return _quest_completed_met(await load_vault_facts(db_session, vault_id), requirement_data)


def _level_met(facts: VaultFacts, requirement_data: dict[str, Any]) -> bool:
    return facts.count_at_level(requirement_data.get("level", 1)) >= requirement_data.get("count", 1)


def _item_met(facts: VaultFacts, requirement_data: dict[str, Any]) -> bool:
    item_name = requirement_data.get("item_name", "")
    return facts.count_item(item_name) >= requirement_data.get("count", 1)


def _attack_met(facts: VaultFacts, requirement_data: dict[str, Any]) -> bool:
    return facts.count_with_attack(requirement_data.get("attack", 0)) >= requirement_data.get("count", 1)


def _stat_met(facts: VaultFacts, requirement_data: dict[str, Any]) -> bool:
    stat = requirement_data.get("stat")
    if stat not in SPECIAL_STATS:
        return False
    return facts.count_with_stat(stat, requirement_data.get("value", 1)) >= requirement_data.get("count", 1)


def _room_met(facts: VaultFacts, requirement_data: dict[str, Any]) -> bool:
    room_type = normalize_room_type(requirement_data.get("room_type"))
    if room_type is None:
        return False
    return facts.count_rooms(room_type) >= requirement_data.get("count", 1)


def _dweller_count_met(facts: VaultFacts, requirement_data: dict[str, Any]) -> bool:
    return facts.alive_dweller_count >= requirement_data.get("count", 0)


def _quest_completed_met(facts: VaultFacts, requirement_data: dict[str, Any]) -> bool:
    quest_id = requirement_data.get("quest_id")
    if not quest_id:
        logger.warning("quest_completed requirement missing quest_id")
        return False

    try:
        quest_id = UUID(str(quest_id))
    except TypeError, ValueError:
        logger.warning(f"quest_completed requirement has invalid quest_id: {quest_id}")
        return False

    return quest_id in facts.completed_quest_ids


_CHECKERS = {
    RequirementType.LEVEL: _level_met,
    RequirementType.ITEM: _item_met,
    RequirementType.ROOM: _room_met,
    RequirementType.DWELLER_COUNT: _dweller_count_met,
    RequirementType.QUEST_COMPLETED: _quest_completed_met,
    RequirementType.ATTACK: _attack_met,
    RequirementType.STAT: _stat_met,
}


def _requires_facts(requirements: Sequence[QuestRequirement]) -> bool:
    """Whether any requirement type can be evaluated from the snapshot at all."""
    return any(req.requirement_type in _CHECKERS for req in requirements)


def _check_requirement(vault_id: UUID, requirement: QuestRequirement, facts: VaultFacts | None) -> bool:
    """Dispatch on requirement type against the snapshot; unknown types and errors fail closed."""
    checker = _CHECKERS.get(requirement.requirement_type)
    if checker is None:
        logger.warning(f"Unknown requirement type: {requirement.requirement_type}")
        return False
    if facts is None:
        logger.warning(f"No vault facts for {requirement.requirement_type} requirement of vault {vault_id}")
        return False

    try:
        return checker(facts, requirement.requirement_data)
    except Exception:
        logger.exception(f"Error validating {requirement.requirement_type} requirement for vault {vault_id}")
        return False


async def vault_missing_item_requirements(
    db_session: AsyncSession,
    vault_id: UUID,
    quest: Quest,
    *,
    facts: VaultFacts | None = None,
) -> list[str]:
    """Unmet mandatory ITEM gates, as human-readable reasons.

    ITEM is vault-scoped: counts when in storage or equipped by any vault dweller, matching the read path.
    Party-gating it made quests read available then refuse to start when the wearer stayed home.
    """
    item_requirements = [
        req for req in quest.quest_requirements if req.is_mandatory and req.requirement_type == RequirementType.ITEM
    ]
    if not item_requirements:
        return []

    if facts is None:
        facts = await load_vault_facts(db_session, vault_id)

    return [
        _describe_item(req.requirement_data)
        for req in item_requirements
        if not _check_requirement(vault_id, req, facts)
    ]


def party_missing_requirements(party_dwellers: Sequence[Dweller], quest: Quest) -> list[str]:
    """Missing party-level requirements for a quest, given the dwellers being sent.

    LEVEL/ATTACK/STAT check the dispatched party; ITEM/ROOM/DWELLER_COUNT/QUEST_COMPLETED stay vault-level in
    vault_missing_requirements.
    """
    missing: list[str] = []
    for req in quest.quest_requirements:
        if not req.is_mandatory:
            continue
        if req.requirement_type == RequirementType.LEVEL and not _party_meets_level(
            party_dwellers, req.requirement_data
        ):
            missing.append(_describe_level(req.requirement_data))
        elif req.requirement_type == RequirementType.ATTACK and not _party_meets_attack(
            party_dwellers, req.requirement_data
        ):
            missing.append(_describe_party_attack(req.requirement_data))
        elif req.requirement_type == RequirementType.STAT and not _party_meets_stat(
            party_dwellers, req.requirement_data
        ):
            missing.append(_describe_party_stat(req.requirement_data))
    return missing


def individual_meets_requirement(dweller: Dweller, requirement: QuestRequirement) -> bool:
    """Whether a single dweller satisfies a requirement's per-individual threshold.

    Count-independent: aggregate count is enforced on the party at start. Optional and vault-level gates (ROOM,
    DWELLER_COUNT, QUEST_COMPLETED) never disqualify a candidate per-individual.
    """
    if not requirement.is_mandatory:
        return True
    if requirement.requirement_type == RequirementType.LEVEL:
        return _individual_meets_level(dweller, requirement.requirement_data)
    if requirement.requirement_type == RequirementType.ATTACK:
        return _individual_meets_attack(dweller, requirement.requirement_data)
    if requirement.requirement_type == RequirementType.STAT:
        return _individual_meets_stat(dweller, requirement.requirement_data)
    # ITEM / ROOM / DWELLER_COUNT / QUEST_COMPLETED are vault-scoped; not judged here.
    return True


def _individual_meets_level(dweller: Dweller, requirement_data: dict[str, Any]) -> bool:
    return dweller.level >= requirement_data.get("level", 1)


def _individual_meets_attack(dweller: Dweller, requirement_data: dict[str, Any]) -> bool:
    required_attack = requirement_data.get("attack", 0)
    return dweller.weapon is not None and (dweller.weapon.damage_min + dweller.weapon.damage_max) / 2 >= required_attack


def _individual_meets_stat(dweller: Dweller, requirement_data: dict[str, Any]) -> bool:
    stat = requirement_data.get("stat")
    if stat not in SPECIAL_STATS:
        return False
    return effective_stat(dweller, stat) >= requirement_data.get("value", 1)


def _party_meets_level(party_dwellers: Sequence[Dweller], requirement_data: dict[str, Any]) -> bool:
    required_count = requirement_data.get("count", 1)
    return sum(1 for dweller in party_dwellers if _individual_meets_level(dweller, requirement_data)) >= required_count


def _party_meets_attack(party_dwellers: Sequence[Dweller], requirement_data: dict[str, Any]) -> bool:
    required_count = requirement_data.get("count", 1)
    return sum(1 for dweller in party_dwellers if _individual_meets_attack(dweller, requirement_data)) >= required_count


def _party_meets_stat(party_dwellers: Sequence[Dweller], requirement_data: dict[str, Any]) -> bool:
    required_count = requirement_data.get("count", 1)
    return sum(1 for dweller in party_dwellers if _individual_meets_stat(dweller, requirement_data)) >= required_count


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
        return f"Need {count}x {item_name} owned or equipped"
    return f"Need {item_name} owned or equipped"


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
