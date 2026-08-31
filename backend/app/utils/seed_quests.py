"""Quest seeding utility to populate database from JSON files on startup."""

import logging
from pathlib import Path
from typing import TypedDict
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Item
from app.models.quest import Quest, QuestType
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.models.quest_reward import QuestReward, RewardType
from app.schemas.quest import QuestJSON, QuestRewardJSON
from app.utils.load_quests import load_all_quest_chain_files
from app.utils.static_data import game_data_store

logger = logging.getLogger(__name__)


class QuestMetadata(TypedDict):
    quest_type: QuestType
    quest_category: str | None
    chain_id: str | None
    chain_order: int


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


def _quest_metadata(quest_json: QuestJSON, chain_id: str | None) -> QuestMetadata:
    return {
        "quest_type": QuestType(quest_json.quest_type or QuestType.SIDE),
        "quest_category": quest_json.quest_category,
        "chain_id": chain_id,
        "chain_order": quest_json.chain_order,
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
        rewards = list(
            (await db_session.execute(select(QuestReward).where(QuestReward.quest_id == quest.id))).scalars().all()
        )
        for reward_json in quest_json.quest_rewards:
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
                        item_data=reward_json.item_data,
                    )
                )
                updated_count += 1
                continue
            rewards.remove(reward)
            if (
                reward.reward_data != reward_json.reward_data
                or reward.item_data != reward_json.item_data
                or reward.reward_chance != reward_json.reward_chance
            ):
                reward.reward_data = reward_json.reward_data
                reward.item_data = reward_json.item_data
                reward.reward_chance = reward_json.reward_chance
                db_session.add(reward)
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
    all_quest_jsons: list[QuestJSON] = []
    quest_chain_ids: dict[str, str | None] = {}
    for chain in quest_chains:
        for quest_json in chain.quests:
            if quest_json.quest_name in quest_chain_ids:
                raise ValueError(f"Duplicate quest_name '{quest_json.quest_name}' in quest data")
            all_quest_jsons.append(quest_json)
            quest_chain_ids[quest_json.quest_name] = chain.chain_id

    try:
        logger.info("Loaded %d quests from %d quest chains", len(all_quest_jsons), len(quest_chains))

        # Check which quests already exist in database
        existing_quests = (await db_session.execute(select(Quest))).scalars().all()
        existing_quests_by_title = {quest.title: quest for quest in existing_quests}
        existing_titles = set(existing_quests_by_title)

        # Track seeded quests for requirement resolution
        quest_name_to_id: dict[str, str] = {}
        quests_to_commit: list[tuple[Quest, QuestJSON]] = []
        # Track items created in this seeding run to avoid duplicate SELECTs and inserts
        created_item_names: set[str] = set()

        # Seed quests that don't exist yet
        seeded_count = 0
        for quest_json in all_quest_jsons:
            # Handle requirements - can be string, list of strings, or list of QuestJSON (from chain format)
            reqs = quest_json.requirements
            req_str = ""
            if isinstance(reqs, str):
                req_str = reqs
            elif isinstance(reqs, list):
                # Check if it's a list of strings or list of QuestJSON
                req_str = ", ".join(reqs) if all(isinstance(r, str) for r in reqs) else str(reqs[0]) if reqs else ""

            # Use quest_name from JSON as the title
            if quest_json.quest_name not in existing_titles:
                # Generate rewards string from structured quest_rewards if available
                rewards_str = generate_rewards_string(quest_json)

                quest = Quest(
                    title=quest_json.quest_name,
                    short_description=quest_json.short_description,
                    long_description=quest_json.long_description,
                    requirements=req_str,
                    rewards=rewards_str,
                    **_quest_metadata(quest_json, quest_chain_ids[quest_json.quest_name]),
                )
                db_session.add(quest)
                quests_to_commit.append((quest, quest_json))
                seeded_count += 1
                logger.debug("Seeding quest: %s", quest_json.quest_name)

        # Flush to get quest IDs within the current transaction
        if seeded_count > 0:
            await db_session.flush()

            # Build name->id map for requirement resolution
            for quest, quest_json in quests_to_commit:
                await db_session.refresh(quest)
                quest_name_to_id[quest_json.quest_name] = str(quest.id)

            # Create requirements and rewards for each quest
            for quest, quest_json in quests_to_commit:
                # Create quest requirements
                for req_json in quest_json.quest_requirements:
                    requirement_data = dict(req_json.requirement_data)

                    # For QUEST_COMPLETED type, resolve quest_name to quest_id
                    if req_json.requirement_type.upper() == "QUEST_COMPLETED":
                        quest_name = requirement_data.get("quest_name")
                        if quest_name:
                            # Check in-memory map first
                            if quest_name in quest_name_to_id:
                                requirement_data["quest_id"] = quest_name_to_id[quest_name]
                                del requirement_data["quest_name"]
                            else:
                                # Query database for existing quests by name
                                result = await db_session.execute(select(Quest).where(Quest.title == quest_name))
                                existing_quest = result.scalars().first()
                                if existing_quest:
                                    requirement_data["quest_id"] = str(existing_quest.id)
                                    quest_name_to_id[quest_name] = str(existing_quest.id)
                                    del requirement_data["quest_name"]
                                else:
                                    # Emit warning if quest_name cannot be resolved
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

                        requirement = QuestRequirement(
                            quest_id=quest.id,
                            requirement_type=RequirementType(req_json.requirement_type.lower()),
                            requirement_data=requirement_data,
                            is_mandatory=req_json.is_mandatory,
                        )
                        db_session.add(requirement)
                        if predecessor_id:
                            quest.previous_quest_id = predecessor_id
                    except ValueError as e:
                        logger.warning(f"Failed to create requirement for quest '{quest.title}': {e}")

                # Create quest rewards
                for reward_json in quest_json.quest_rewards:
                    try:
                        reward = QuestReward(
                            quest_id=quest.id,
                            reward_type=RewardType(reward_json.reward_type.lower()),
                            reward_data=reward_json.reward_data,
                            reward_chance=reward_json.reward_chance,
                            item_data=reward_json.item_data,
                        )
                        db_session.add(reward)

                        # Create item from item_data if reward_type is ITEM and item_data is provided
                        if reward_json.reward_type.upper() == "ITEM" and reward_json.item_data:
                            item_name = reward_json.item_data.get("name")
                            if item_name and item_name not in created_item_names:
                                # Check if item already exists in database
                                existing_item = await db_session.execute(select(Item).where(Item.name == item_name))
                                existing = existing_item.scalars().first()
                                if not existing:
                                    # Create the item
                                    item = Item(
                                        name=item_name,
                                        rarity=reward_json.item_data.get("rarity", "common"),
                                        value=reward_json.item_data.get("value"),
                                        image_url=reward_json.item_data.get("image_url"),
                                    )
                                    db_session.add(item)
                                    created_item_names.add(item_name)
                                    logger.debug(f"Created item '{item_name}' from quest reward")

                    except ValueError as e:
                        logger.warning(f"Failed to create reward for quest '{quest.title}': {e}")

            updated_quest_count = 0
            for quest_json in all_quest_jsons:
                quest = existing_quests_by_title.get(quest_json.quest_name)
                if quest is not None:
                    metadata = _quest_metadata(quest_json, quest_chain_ids[quest_json.quest_name])
                    if any(getattr(quest, field) != value for field, value in metadata.items()):
                        quest.sqlmodel_update(metadata)
                        updated_quest_count += 1

            updated_reward_count = await _sync_existing_quest_rewards(
                db_session, existing_quests_by_title, all_quest_jsons
            )
            await db_session.commit()
            logger.info(
                "Seeded %d new quests and updated %d existing quest rewards",
                seeded_count,
                updated_reward_count,
            )
        else:
            updated_quest_count = 0
            for quest_json in all_quest_jsons:
                quest = existing_quests_by_title.get(quest_json.quest_name)
                if quest is not None:
                    metadata = _quest_metadata(quest_json, quest_chain_ids[quest_json.quest_name])
                    if any(getattr(quest, field) != value for field, value in metadata.items()):
                        quest.sqlmodel_update(metadata)
                        updated_quest_count += 1
            updated_reward_count = await _sync_existing_quest_rewards(
                db_session, existing_quests_by_title, all_quest_jsons
            )
            if updated_quest_count or updated_reward_count:
                await db_session.commit()
                logger.info(
                    "Updated %d quest definitions and %d existing quest rewards from static data",
                    updated_quest_count,
                    updated_reward_count,
                )
            else:
                logger.info("No new quests to seed, all quests already exist in database")
    except Exception:
        logger.exception("Failed to seed quests from JSON files")
        await db_session.rollback()
        return 0
    else:
        return seeded_count
