"""Generic seeding helper for populating database from JSON files."""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
M = TypeVar("M")


async def seed_from_json(
    db_session: AsyncSession,
    model_class: type[M],
    schema_class: type[T],
    directory: Path,
    unique_field: str,
    transform_fn: Callable[[T], M],
    file_pattern: str = "*.json",
) -> int:
    """
    Generic seeding helper that loads JSON files, validates with Pydantic, and seeds database.

    Args:
        db_session: Database session
        model_class: SQLModel database model class (e.g., Quest, Objective)
        schema_class: Pydantic schema class for validation (e.g., QuestJSON, ObjectiveCreate)
        directory: Directory containing JSON files
        unique_field: Field name to check for duplicates (e.g., "title", "challenge")
        transform_fn: Function to transform schema instance to model instance
        file_pattern: Glob pattern for JSON files (default: "*.json")

    Returns:
        Number of records seeded
    """
    try:
        if not directory.exists():
            logger.warning("Directory not found: %s", directory)
            return 0

        # Load all data from JSON files
        all_data: list[T] = []
        for json_file in directory.glob(file_pattern):
            try:
                with json_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        validated = [schema_class.model_validate(item) for item in data]
                        all_data.extend(validated)
                    else:
                        validated = schema_class.model_validate(data)
                        all_data.append(validated)
            except ValidationError:
                logger.exception("Validation error in %s", json_file)
                continue
            except Exception:
                logger.exception("Failed to load data from %s", json_file)
                continue

        logger.info("Loaded %d records from JSON files", len(all_data))

        # Check which records already exist in database
        existing_values_result = await db_session.execute(select(getattr(model_class, unique_field)))
        existing_values = set(existing_values_result.scalars().all())

        # Track values seen in current batch to prevent in-batch duplicates
        seen_values = set(existing_values)

        # Seed records that don't exist yet
        seeded_count = 0
        for data_item in all_data:
            unique_value = getattr(data_item, unique_field)

            # Skip if already in database
            if unique_value in existing_values:
                logger.debug("Skipping duplicate (exists in DB): %s=%s", unique_field, unique_value)
                continue

            # Skip if already seen in this batch
            if unique_value in seen_values:
                logger.warning("Skipping duplicate (within batch): %s=%s", unique_field, unique_value)
                continue

            # Mark as seen and seed
            seen_values.add(unique_value)
            model_instance = transform_fn(data_item)
            db_session.add(model_instance)
            seeded_count += 1
            logger.debug("Seeding record with %s=%s", unique_field, unique_value)

        if seeded_count > 0:
            await db_session.commit()
            logger.info("Seeded %d new records into database", seeded_count)
        else:
            logger.info("No new records to seed, all records already exist in database")
        return seeded_count
    except Exception:
        logger.exception("Failed to seed records from JSON files")
        await db_session.rollback()
        return 0
