"""Objective seeding utility to populate database from JSON files on startup."""

import logging
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.objective import Objective
from app.schemas.objective import ObjectiveCreate
from app.utils.static_data import DATA_DIR

logger = logging.getLogger(__name__)


async def seed_objectives_from_json(db_session: AsyncSession, objectives_dir: Path | None = None) -> int:
    """
    Seed objectives from JSON files into database if they don't already exist.

    Args:
        db_session: Database session
        objectives_dir: Directory containing objective JSON files (defaults to app/data/objectives)

    Returns:
        Number of objectives seeded
    """
    try:
        if objectives_dir is None:
            objectives_dir = DATA_DIR / "objectives"

        if not objectives_dir.exists():
            logger.warning("Objectives directory not found: %s", objectives_dir)
            return 0

        # Load objectives from all JSON files
        all_objectives: list[ObjectiveCreate] = []
        for json_file in objectives_dir.glob("*.json"):
            try:
                import json

                with json_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        objectives = [ObjectiveCreate.model_validate(obj) for obj in data]
                        all_objectives.extend(objectives)
                    else:
                        objective = ObjectiveCreate.model_validate(data)
                        all_objectives.append(objective)
            except Exception:
                logger.exception("Failed to load objectives from %s", json_file)
                continue

        logger.info("Loaded %d objectives from JSON files", len(all_objectives))

        # Check which objectives already exist in database
        existing_challenges_result = await db_session.execute(select(Objective.challenge))
        existing_challenges = set(existing_challenges_result.scalars().all())

        # Seed objectives that don't exist yet
        seeded_count = 0
        for objective_data in all_objectives:
            if objective_data.challenge not in existing_challenges:
                objective = Objective(
                    challenge=objective_data.challenge,
                    reward=objective_data.reward,
                )
                db_session.add(objective)
                seeded_count += 1
                logger.debug("Seeding objective: %s", objective_data.challenge)

        if seeded_count > 0:
            await db_session.commit()
            logger.info("Seeded %d new objectives into database", seeded_count)
            return seeded_count

        logger.info("No new objectives to seed, all objectives already exist in database")
        return 0  # noqa: TRY300

    except Exception:
        logger.exception("Failed to seed objectives from JSON files")
        await db_session.rollback()
        return 0
