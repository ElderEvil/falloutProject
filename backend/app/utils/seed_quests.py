"""Quest seeding utility to populate database from JSON files on startup."""

import logging
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement, RequirementType
from app.models.quest_reward import QuestReward, RewardType
from app.schemas.quest import QuestJSON, QuestRewardJSON
from app.utils.load_quests import load_all_quest_chain_files

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

    def format_reward(reward: QuestRewardJSON) -> str:  # noqa: PLR0911
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


async def seed_quests_from_json(  # noqa: C901, PLR0912, PLR0915
    db_session: AsyncSession, quest_dir: Path | None = None
) -> int:
    """Seed quests from JSON files into database if they don't already exist.

    Args:
        db_session: Database session
        quest_dir: Directory containing quest JSON files (defaults to app/data/quests)

    Returns:
        Number of quests seeded
    """
    try:
        # Load quest chains from JSON files
        quest_chains = load_all_quest_chain_files(quest_dir)

        # Flatten all quests from all chains
        all_quest_jsons: list[QuestJSON] = []
        for chain in quest_chains:
            all_quest_jsons.extend(chain.quests)

        logger.info("Loaded %d quests from %d quest chains", len(all_quest_jsons), len(quest_chains))

        # Check which quests already exist in database
        existing_titles_result = await db_session.execute(select(Quest.title))
        existing_titles = set(existing_titles_result.scalars().all())

        # Track seeded quests for requirement resolution
        quest_name_to_id: dict[str, str] = {}
        quests_to_commit: list[tuple[Quest, QuestJSON]] = []

        # Seed quests that don't exist yet
        seeded_count = 0
        for quest_json in all_quest_jsons:
            # Handle requirements - can be string, list of strings, or list of QuestJSON (from chain format)
            reqs = quest_json.requirements
            if reqs is None:
                req_str = ""
            elif isinstance(reqs, str):
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
                        requirement = QuestRequirement(
                            quest_id=quest.id,
                            requirement_type=RequirementType(req_json.requirement_type.lower()),
                            requirement_data=requirement_data,
                            is_mandatory=req_json.is_mandatory,
                        )
                        db_session.add(requirement)
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
                        )
                        db_session.add(reward)
                    except ValueError as e:
                        logger.warning(f"Failed to create reward for quest '{quest.title}': {e}")

            await db_session.commit()
            logger.info("Seeded %d new quests with requirements and rewards", seeded_count)
        else:
            logger.info("No new quests to seed, all quests already exist in database")
        return seeded_count
    except Exception:
        logger.exception("Failed to seed quests from JSON files")
        await db_session.rollback()
        return 0
