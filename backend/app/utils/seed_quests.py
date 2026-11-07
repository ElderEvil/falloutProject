"""Quest seeding utility to populate database from JSON files on startup."""

import json
import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import QuestType, RequirementType, RewardType
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.quest_reward import QuestReward
from app.schemas.quest import QuestChainJSON, QuestJSON, QuestRequirementJSON, QuestRewardJSON
from app.utils.load_quests import load_all_quest_chain_files
from app.utils.static_data import game_data_store

logger = logging.getLogger(__name__)


def generate_rewards_string(quest_json: QuestJSON) -> str:
    """Generate a human-readable rewards string from structured quest_rewards.

    Prefers the text "Rewards" field if available and valid (>= 3 chars),
    otherwise generates from structured quest_rewards.
    """
    # Prefer the text Rewards field if it exists and is valid
    if quest_json.rewards and len(quest_json.rewards) >= 3:
        return quest_json.rewards

    if not quest_json.quest_rewards:
        return quest_json.rewards or ""

    def format_reward(reward: QuestRewardJSON) -> str:
        rtype, data = reward.reward_type.upper(), reward.reward_data
        qty = data.get("quantity", data.get("amount", 1))

        if rtype in ("CAPS", "CAP"):
            return f"{data.get('amount', 0)} caps"
        if rtype == "ITEM":
            item = data.get("item_name", "Unknown")
            return f"{qty}x {item}" if qty > 1 else item
        if rtype in ("STIMPAK", "STIMPACK"):
            return f"{qty} stimpak{'s' if qty > 1 else ''}"
        if rtype == "RADAWAY":
            return f"{qty} radaway{'s' if qty > 1 else ''}"
        if rtype == "LUNCHBOX":
            return f"{qty} lunchbox{'es' if qty > 1 else ''}"
        if rtype == "DWELLER":
            return "New dweller"

        # Generic fallback
        item = data.get("item_name", "")
        return f"{qty}x {item}" if item and qty > 1 else (item or rtype.lower().replace("_", " "))

    return ", ".join(format_reward(r) for r in quest_json.quest_rewards)


def _quest_text_fields(quest_json: QuestJSON) -> dict[str, str]:
    """Resolve the display-text fields shared by the create and sync paths.

    ``rewards`` goes through :func:`generate_rewards_string` rather than the raw
    authored text: most catalog quests leave "Rewards" empty and describe their
    rewards structurally, and the model rejects text shorter than 3 characters.
    Resolving both paths here keeps them from drifting apart - a raw ``rewards``
    here would have blanked 24 of 35 quests on every re-seed.
    """
    reqs = quest_json.requirements
    req_str = ""
    if isinstance(reqs, str):
        req_str = reqs
    elif isinstance(reqs, list):
        req_str = ", ".join(reqs) if all(isinstance(r, str) for r in reqs) else str(reqs[0]) if reqs else ""
    return {
        "short_description": quest_json.short_description,
        "long_description": quest_json.long_description,
        "requirements": req_str,
        "rewards": generate_rewards_string(quest_json),
    }


def _quest_metadata(quest_json: QuestJSON, chain_id: str | None) -> dict[str, Any]:
    return {
        "quest_type": QuestType(quest_json.quest_type or QuestType.SIDE),
        "quest_category": quest_json.quest_category,
        "chain_id": chain_id,
        "chain_order": quest_json.chain_order,
        "duration_minutes": quest_json.duration_minutes,
        **_quest_text_fields(quest_json),
    }


def _matches_reward_json(reward: QuestReward, reward_json: QuestRewardJSON) -> bool:
    if reward.reward_type != RewardType(reward_json.reward_type.lower()):
        return False
    if reward.reward_data == reward_json.reward_data:
        return True

    template_id = reward_json.reward_data.get("template_id")
    template = game_data_store.get_dweller(template_id) if template_id else None
    template_name = f"{template.first_name} {template.last_name or ''}".strip() if template else None
    return bool(template_name and reward.reward_data.get("name", "").casefold() == template_name.casefold())


async def _sync_existing_quest_rewards(
    db_session: AsyncSession, quests_by_title: dict[str, Quest], quest_jsons: list[QuestJSON]
) -> int:
    """Reconcile existing rewards with the typed quest-data source of truth."""
    updated_count = 0
    for quest_json in quest_jsons:
        quest = quests_by_title.get(quest_json.quest_name)
        if quest is None:
            continue
        rewards = list((await db_session.exec(select(QuestReward).where(QuestReward.quest_id == quest.id))).all())
        for reward_json in quest_json.quest_rewards:
            item_data = reward_json.item_data_json
            reward = next((candidate for candidate in rewards if _matches_reward_json(candidate, reward_json)), None)
            if reward is None:
                reward_type = RewardType(reward_json.reward_type.lower())
                reward = next((candidate for candidate in rewards if candidate.reward_type == reward_type), None)
            if reward is None:
                db_session.add(
                    QuestReward(
                        quest_id=quest.id,
                        reward_type=RewardType(reward_json.reward_type.lower()),
                        reward_data=reward_json.reward_data,
                        reward_chance=reward_json.reward_chance,
                        item_data=item_data,
                    )
                )
                updated_count += 1
                continue
            rewards.remove(reward)
            if (
                reward.reward_data != reward_json.reward_data
                or reward.item_data != item_data
                or reward.reward_chance != reward_json.reward_chance
            ):
                reward.reward_data = reward_json.reward_data
                reward.item_data = item_data
                reward.reward_chance = reward_json.reward_chance
                db_session.add(reward)
                updated_count += 1
    return updated_count


def _desired_requirements(
    quest_json: QuestJSON, resolve_map: dict[str, Quest]
) -> list[tuple[RequirementType, dict[str, Any], bool]]:
    """Build the canonical stored representation of a quest's JSON requirements."""
    desired: list[tuple[RequirementType, dict[str, Any], bool]] = []
    for req_json in quest_json.quest_requirements:
        try:
            requirement_type = RequirementType(req_json.requirement_type.lower())
        except ValueError as e:
            logger.warning(f"Failed to parse requirement type for quest '{quest_json.quest_name}': {e}")
            continue
        requirement_data = dict(req_json.requirement_data)
        if requirement_type == RequirementType.QUEST_COMPLETED:
            quest_name = requirement_data.get("quest_name")
            if quest_name:
                predecessor = resolve_map.get(quest_name)
                if predecessor is not None:
                    requirement_data["quest_id"] = str(predecessor.id)
                    del requirement_data["quest_name"]
                else:
                    logger.warning(
                        f"Could not resolve quest_name '{quest_name}' "
                        f"for QUEST_COMPLETED requirement in quest '{quest_json.quest_name}'"
                    )
        desired.append((requirement_type, requirement_data, req_json.is_mandatory))
    return desired


def _predecessor_id(desired: list[tuple[RequirementType, dict[str, Any], bool]]) -> UUID | None:
    """Return the first mandatory QUEST_COMPLETED predecessor id, if any."""
    for requirement_type, requirement_data, is_mandatory in desired:
        if requirement_type == RequirementType.QUEST_COMPLETED and is_mandatory:
            quest_id = requirement_data.get("quest_id")
            if quest_id:
                return UUID(str(quest_id))
    return None


def _requirements_in_sync(
    existing: list[QuestRequirement], desired: list[tuple[RequirementType, dict[str, Any], bool]]
) -> bool:
    if len(existing) != len(desired):
        return False
    existing_sorted = sorted(
        (r.requirement_type.value, json.dumps(r.requirement_data, sort_keys=True, default=str), r.is_mandatory)
        for r in existing
    )
    desired_sorted = sorted(
        (rt.value, json.dumps(rd, sort_keys=True, default=str), mandatory) for rt, rd, mandatory in desired
    )
    return existing_sorted == desired_sorted


async def _sync_existing_quest_requirements(
    db_session: AsyncSession,
    quests_by_title: dict[str, Quest],
    quest_jsons: list[QuestJSON],
    *,
    resolve_map: dict[str, Quest] | None = None,
) -> int:
    """Reconcile existing quest requirements with the typed quest-data source of truth."""
    resolve_map = resolve_map if resolve_map is not None else quests_by_title
    updated_count = 0
    for quest_json in quest_jsons:
        quest = quests_by_title.get(quest_json.quest_name)
        if quest is None:
            continue
        existing = list(
            (await db_session.exec(select(QuestRequirement).where(QuestRequirement.quest_id == quest.id))).all()
        )
        desired = _desired_requirements(quest_json, resolve_map)
        predecessor_id = _predecessor_id(desired)
        if _requirements_in_sync(existing, desired) and quest.previous_quest_id == predecessor_id:
            continue
        for requirement in existing:
            await db_session.delete(requirement)
        for requirement_type, requirement_data, is_mandatory in desired:
            db_session.add(
                QuestRequirement(
                    quest_id=quest.id,
                    requirement_type=requirement_type,
                    requirement_data=requirement_data,
                    is_mandatory=is_mandatory,
                )
            )
        quest.previous_quest_id = predecessor_id
        updated_count += 1
    return updated_count


def _load_quest_jsons(
    quest_chains: list[QuestChainJSON],
) -> tuple[list[QuestJSON], dict[str, str | None]]:
    """Flatten the chain files into one ordered quest list and reject duplicate names."""
    all_quest_jsons: list[QuestJSON] = []
    quest_chain_ids: dict[str, str | None] = {}
    for chain in quest_chains:
        for quest_json in chain.quests:
            if quest_json.quest_name in quest_chain_ids:
                raise ValueError(f"Duplicate quest_name '{quest_json.quest_name}' in quest data")
            all_quest_jsons.append(quest_json)
            quest_chain_ids[quest_json.quest_name] = chain.chain_id
    return all_quest_jsons, quest_chain_ids


def _stage_new_quests(
    db_session: AsyncSession,
    all_quest_jsons: list[QuestJSON],
    quest_chain_ids: dict[str, str | None],
    existing_titles: set[str],
) -> list[tuple[Quest, QuestJSON]]:
    """Add a Quest row for every JSON quest the database does not have yet."""
    staged: list[tuple[Quest, QuestJSON]] = []
    for quest_json in all_quest_jsons:
        if quest_json.quest_name in existing_titles:
            continue
        quest = Quest(
            title=quest_json.quest_name,
            **_quest_metadata(quest_json, quest_chain_ids[quest_json.quest_name]),
        )
        db_session.add(quest)
        staged.append((quest, quest_json))
        logger.debug("Seeding quest: %s", quest_json.quest_name)
    return staged


async def _refresh_new_quest_ids(db_session: AsyncSession, staged: list[tuple[Quest, QuestJSON]]) -> dict[str, str]:
    """Flush-assigned ids into a name->id map used to resolve prerequisites."""
    quest_name_to_id: dict[str, str] = {}
    for quest, quest_json in staged:
        await db_session.refresh(quest)
        quest_name_to_id[quest_json.quest_name] = str(quest.id)
    return quest_name_to_id


async def _resolve_quest_name(
    db_session: AsyncSession, quest_name: str, quest_name_to_id: dict[str, str]
) -> str | None:
    """Resolve a predecessor name against the new batch, then the database."""
    if quest_name in quest_name_to_id:
        return quest_name_to_id[quest_name]
    existing_quest = (await db_session.exec(select(Quest).where(Quest.title == quest_name))).first()
    if existing_quest is None:
        return None
    quest_name_to_id[quest_name] = str(existing_quest.id)
    return quest_name_to_id[quest_name]


async def _stage_requirement(
    db_session: AsyncSession,
    quest: Quest,
    req_json: QuestRequirementJSON,
    quest_name_to_id: dict[str, str],
) -> None:
    """Store one requirement, resolving a QUEST_COMPLETED predecessor name to its id."""
    requirement_data = dict(req_json.requirement_data)

    if req_json.requirement_type.upper() == "QUEST_COMPLETED":
        quest_name = requirement_data.get("quest_name")
        if quest_name:
            resolved_id = await _resolve_quest_name(db_session, quest_name, quest_name_to_id)
            if resolved_id:
                requirement_data["quest_id"] = resolved_id
                del requirement_data["quest_name"]
            else:
                logger.warning(
                    f"Could not resolve quest_name '{quest_name}' "
                    f"for QUEST_COMPLETED requirement in quest '{quest.title}'"
                )

    try:
        predecessor_id = None
        if (
            req_json.requirement_type.upper() == "QUEST_COMPLETED"
            and req_json.is_mandatory
            and quest.previous_quest_id is None
            and (previous_quest_id := requirement_data.get("quest_id"))
        ):
            predecessor_id = UUID(str(previous_quest_id))

        db_session.add(
            QuestRequirement(
                quest_id=quest.id,
                requirement_type=RequirementType(req_json.requirement_type.lower()),
                requirement_data=requirement_data,
                is_mandatory=req_json.is_mandatory,
            )
        )
        if predecessor_id:
            quest.previous_quest_id = predecessor_id
    except ValueError as e:
        logger.warning(f"Failed to create requirement for quest '{quest.title}': {e}")


def _stage_reward(db_session: AsyncSession, quest: Quest, reward_json: QuestRewardJSON) -> None:
    """Store one reward, warning instead of failing on a bad reward payload."""
    try:
        db_session.add(
            QuestReward(
                quest_id=quest.id,
                reward_type=RewardType(reward_json.reward_type.lower()),
                reward_data=reward_json.reward_data,
                reward_chance=reward_json.reward_chance,
                item_data=reward_json.item_data_json,
            )
        )
    except ValueError as e:
        logger.warning(f"Failed to create reward for quest '{quest.title}': {e}")


async def _stage_quest_children(
    db_session: AsyncSession,
    staged: list[tuple[Quest, QuestJSON]],
    quest_name_to_id: dict[str, str],
) -> None:
    """Create requirements and rewards for the quests staged in this run."""
    for quest, quest_json in staged:
        for req_json in quest_json.quest_requirements:
            await _stage_requirement(db_session, quest, req_json, quest_name_to_id)
        for reward_json in quest_json.quest_rewards:
            _stage_reward(db_session, quest, reward_json)


def _update_existing_quest_metadata(
    all_quest_jsons: list[QuestJSON],
    existing_quests_by_title: dict[str, Quest],
    quest_chain_ids: dict[str, str | None],
) -> int:
    """Refresh display/chain metadata for quests that already exist."""
    updated_count = 0
    for quest_json in all_quest_jsons:
        quest = existing_quests_by_title.get(quest_json.quest_name)
        if quest is None:
            continue
        metadata = _quest_metadata(quest_json, quest_chain_ids[quest_json.quest_name])
        if any(getattr(quest, field) != value for field, value in metadata.items()):
            quest.sqlmodel_update(metadata)
            updated_count += 1
    return updated_count


async def seed_quests_from_json(db_session: AsyncSession, quest_dir: Path | None = None) -> int:
    """Seed quests from JSON files into database if they don't already exist.

    Args:
        db_session: Database session
        quest_dir: Directory containing quest JSON files (defaults to app/data/quests)

    Returns:
        Number of quests seeded
    """
    quest_chains = load_all_quest_chain_files(quest_dir)
    all_quest_jsons, quest_chain_ids = _load_quest_jsons(quest_chains)

    try:
        logger.info("Loaded %d quests from %d quest chains", len(all_quest_jsons), len(quest_chains))

        existing_quests = (await db_session.exec(select(Quest))).all()
        existing_quests_by_title = {quest.title: quest for quest in existing_quests}

        staged = _stage_new_quests(db_session, all_quest_jsons, quest_chain_ids, set(existing_quests_by_title))
        seeded_count = len(staged)
        if staged:
            # Flush first so the new rows have ids; prerequisites may reference them.
            await db_session.flush()
            quest_name_to_id = await _refresh_new_quest_ids(db_session, staged)
            await _stage_quest_children(db_session, staged, quest_name_to_id)

        updated_quest_count = _update_existing_quest_metadata(
            all_quest_jsons, existing_quests_by_title, quest_chain_ids
        )
        all_quests_by_title = {
            **existing_quests_by_title,
            **{quest_json.quest_name: quest for quest, quest_json in staged},
        }
        updated_reward_count = await _sync_existing_quest_rewards(db_session, existing_quests_by_title, all_quest_jsons)
        updated_requirement_count = await _sync_existing_quest_requirements(
            db_session, existing_quests_by_title, all_quest_jsons, resolve_map=all_quests_by_title
        )

        if seeded_count or updated_quest_count or updated_reward_count or updated_requirement_count:
            await db_session.commit()
        if seeded_count:
            logger.info(
                "Seeded %d new quests and updated %d existing quest rewards and %d existing quest requirements",
                seeded_count,
                updated_reward_count,
                updated_requirement_count,
            )
        elif updated_quest_count or updated_reward_count or updated_requirement_count:
            logger.info(
                "Updated %d quest definitions, %d existing quest rewards, and %d existing quest requirements "
                "from static data",
                updated_quest_count,
                updated_reward_count,
                updated_requirement_count,
            )
        else:
            logger.info("No new quests to seed, all quests already exist in database")
    except Exception:
        logger.exception("Failed to seed quests from JSON files")
        await db_session.rollback()
        return 0
    return seeded_count
