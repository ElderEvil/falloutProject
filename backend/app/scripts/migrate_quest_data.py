"""
Data migration script for v2.10.0 - Convert existing quest strings to structured format.

This script parses existing quest requirements and rewards strings into
structured QuestRequirement and QuestReward records.

Usage:
    cd backend
    uv run python -m app.scripts.migrate_quest_data
"""

import asyncio
import logging
import re

from app.core.db import async_session_maker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import quest as quest_crud
from app.models.quest import QuestType
from app.models.quest_requirement import QuestRequirement
from app.models.quest_reward import QuestReward

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_requirements(requirements_str: str) -> list[dict]:
    """Parse requirements string into structured data.

    Examples:
        "Level 1 dwellers" -> [{type: "level", amount: 1, target: "dwellers"}]
        "Level 20 dwellers, 1000 caps" -> [{type: "level", ...}, {type: "resource", ...}]
    """
    requirements = []
    if not requirements_str:
        return requirements

    # Split by comma or 'and'
    parts = re.split(r",|\\band\\b", requirements_str, flags=re.IGNORECASE)

    for raw_part in parts:
        part = raw_part.strip()
        if not part:
            continue

        # Pattern: "Level X dwellers"
        level_match = re.match(r"level\\s+(\\d+)\\s+(\\w+)", part, re.IGNORECASE)
        if level_match:
            requirements.append(
                {"type": "level", "amount": int(level_match.group(1)), "target": level_match.group(2).lower()}
            )
            continue

        # Pattern: "X caps"
        caps_match = re.match(r"(\\d+)\\s+caps", part, re.IGNORECASE)
        if caps_match:
            requirements.append({"type": "resource", "resource_type": "caps", "amount": int(caps_match.group(1))})
            continue

        # Pattern: "X rooms"
        rooms_match = re.match(r"(\\d+)\\s+rooms?", part, re.IGNORECASE)
        if rooms_match:
            requirements.append({"type": "room", "amount": int(rooms_match.group(1))})
            continue

        # Pattern: "X dwellers"
        dwellers_match = re.match(r"(\\d+)\\s+dwellers?", part, re.IGNORECASE)
        if dwellers_match:
            requirements.append({"type": "dweller_count", "amount": int(dwellers_match.group(1))})
            continue

        # Default: store as generic requirement
        requirements.append({"type": "generic", "description": part})

    return requirements


def parse_rewards(rewards_str: str) -> list[dict]:
    """Parse rewards string into structured data.

    Examples:
        "200 caps" -> [{type: "caps", amount: 200}]
        "Nuka-Cola Quantum x15, Lunchbox" -> [{type: "item", ...}, {type: "item", ...}]
    """
    rewards = []
    if not rewards_str:
        return rewards

    # Split by comma
    parts = [p.strip() for p in rewards_str.split(",")]

    for part in parts:
        if not part:
            continue

        # Pattern: "X caps"
        caps_match = re.match(r"(\\d+)\\s+caps", part, re.IGNORECASE)
        if caps_match:
            rewards.append({"type": "caps", "amount": int(caps_match.group(1))})
            continue

        # Pattern: "Item Name xN" or "N x Item Name"
        quantity_match = re.match(r"(.*?)(?:\s*x\s*(\d+))?$", part, re.IGNORECASE)
        if quantity_match:
            item_name = quantity_match.group(1).strip()
            # Skip rewards with empty item names
            if not item_name:
                continue
            quantity = int(quantity_match.group(2)) if quantity_match.group(2) else 1

            rewards.append({"type": "item", "item_name": item_name, "quantity": quantity})

    return rewards


def determine_quest_type(quest_title: str | None, description: str | None) -> QuestType:
    """Determine quest type based on title and description."""
    # Normalize inputs to empty string to avoid TypeError during concatenation
    quest_title = quest_title or ""
    description = description or ""
    text = (quest_title + " " + description).lower()

    if "daily" in text:
        return QuestType.DAILY
    if "event" in text:
        return QuestType.EVENT
    if "tutorial" in text or "training" in text or "getting started" in text:
        return QuestType.MAIN
    return QuestType.SIDE


def determine_category(quest_title: str | None, description: str | None) -> str:
    """Determine quest category based on content."""
    # Normalize inputs to empty string to avoid TypeError during concatenation
    quest_title = quest_title or ""
    description = description or ""
    text = (quest_title + " " + description).lower()

    if any(word in text for word in ["combat", "kill", "defeat", "enemy"]):
        return "combat"
    if any(word in text for word in ["explore", "wasteland", "scout"]):
        return "exploration"
    if any(word in text for word in ["collect", "gather", "find"]):
        return "collection"
    if any(word in text for word in ["build", "construct", "room"]):
        return "building"
    if any(word in text for word in ["train", "level up", "upgrade"]):
        return "training"
    return "general"


async def migrate_quest_data(db: AsyncSession) -> dict:
    """Migrate existing quest data to structured format.

    Returns:
        dict with counts of created requirements and rewards
    """
    logger.info("Starting quest data migration...")

    # Get all quests
    quests = await quest_crud.get_all(db)
    logger.info(f"Found {len(quests)} quests to process")

    stats = {"quests_updated": 0, "requirements_created": 0, "rewards_created": 0}

    for quest in quests:
        logger.info(f"Processing quest: {quest.title}")

        try:
            # Update quest with type and category
            quest.quest_type = determine_quest_type(quest.title, quest.long_description)
            quest.quest_category = determine_category(quest.title, quest.long_description)

            # Parse and create requirements
            requirements_data = parse_requirements(quest.requirements)
            for req_data in requirements_data:
                try:
                    requirement = QuestRequirement(
                        quest_id=quest.id,
                        requirement_type=req_data.get("type", "generic").lower(),
                        requirement_data=req_data,
                        is_mandatory=True,
                    )
                    db.add(requirement)
                    stats["requirements_created"] += 1
                    logger.debug(f"  Created requirement: {req_data}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"  Failed to create requirement: {e}")

            # Parse and create rewards
            rewards_data = parse_rewards(quest.rewards)
            for reward_data in rewards_data:
                try:
                    reward = QuestReward(
                        quest_id=quest.id,
                        reward_type=reward_data.get("type", "item").lower(),
                        reward_data=reward_data,
                        reward_chance=1.0,
                    )
                    db.add(reward)
                    stats["rewards_created"] += 1
                    logger.debug(f"  Created reward: {reward_data}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"  Failed to create reward: {e}")

            # Flush per quest to persist changes and get IDs
            await db.flush()

            stats["quests_updated"] += 1

        except Exception:
            logger.exception(f"Failed to process quest '{quest.title}':")
            await db.rollback()
            continue

    await db.commit()
    logger.info(f"Migration complete: {stats}")
    return stats


async def main():
    """Main entry point."""
    async with async_session_maker() as db:
        stats = await migrate_quest_data(db)
        print("\\nMigration Summary:")
        print(f"  Quests updated: {stats['quests_updated']}")
        print(f"  Requirements created: {stats['requirements_created']}")
        print(f"  Rewards created: {stats['rewards_created']}")


if __name__ == "__main__":
    asyncio.run(main())
