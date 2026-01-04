"""Quest seeding utility to populate database from JSON files on startup."""

import logging
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.quest import Quest
from app.schemas.quest import QuestJSON
from app.utils.load_quests import load_all_quest_chain_files

logger = logging.getLogger(__name__)


async def seed_quests_from_json(db_session: AsyncSession, quest_dir: Path | None = None) -> int:
    """
    Seed quests from JSON files into database if they don't already exist.

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

        # Seed quests that don't exist yet
        seeded_count = 0
        for quest_json in all_quest_jsons:
            # Use quest_name from JSON as the title
            if quest_json.quest_name not in existing_titles:
                quest = Quest(
                    title=quest_json.quest_name,
                    short_description=quest_json.short_description,
                    long_description=quest_json.long_description,
                    requirements=quest_json.requirements
                    if isinstance(quest_json.requirements, str)
                    else ", ".join(quest_json.requirements),
                    rewards=quest_json.rewards,
                )
                db_session.add(quest)
                seeded_count += 1
                logger.debug("Seeding quest: %s", quest_json.quest_name)

        if seeded_count > 0:
            await db_session.commit()
            logger.info("Seeded %d new quests into database", seeded_count)
        else:
            logger.info("No new quests to seed, all quests already exist in database")
        return seeded_count  # noqa: TRY300
    except Exception:
        logger.exception("Failed to seed quests from JSON files")
        await db_session.rollback()
        return 0
