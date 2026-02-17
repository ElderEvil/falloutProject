"""Generic seeding helper for populating database from JSON files."""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import anyio
from pydantic import BaseModel, ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
M = TypeVar("M")


async def _load_json_files(  # noqa: UP047
    directory: Path, file_pattern: str, schema_class: type[T]
) -> list[T]:
    """Load and validate data from JSON files."""
    all_data: list[T] = []
    anyio_path = anyio.Path(directory)

    if not await anyio_path.exists():
        logger.warning("Directory not found: %s", directory)
        return all_data

    async for json_file in anyio_path.glob(file_pattern):
        try:
            async with await json_file.open("r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)
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
    return all_data


async def _get_existing_values(  # noqa: UP047
    db_session: AsyncSession, model_class: type[M], unique_field: str
) -> set:
    """Get existing unique field values from database."""
    result = await db_session.execute(select(getattr(model_class, unique_field)))
    return set(result.scalars().all())


def _seed_records[T, M](
    db_session: AsyncSession,
    all_data: list[T],
    existing_values: set,
    unique_field: str,
    transform_fn: Callable[[T], M],
    validate_fn: Callable[[T], list[str]] | None,
) -> int:
    """Seed records that don't exist yet."""
    seen_values = set(existing_values)
    seeded_count = 0

    for data_item in all_data:
        unique_value = getattr(data_item, unique_field)

        if unique_value in existing_values:
            logger.debug("Skipping duplicate (exists in DB): %s=%s", unique_field, unique_value)
            continue

        if unique_value in seen_values:
            logger.warning("Skipping duplicate (within batch): %s=%s", unique_field, unique_value)
            continue

        if validate_fn:
            errors = validate_fn(data_item)
            if errors:
                for error in errors:
                    logger.error("Validation error for %s=%s: %s", unique_field, unique_value, error)
                continue

        seen_values.add(unique_value)
        model_instance = transform_fn(data_item)
        db_session.add(model_instance)
        seeded_count += 1
        logger.debug("Seeding record with %s=%s", unique_field, unique_value)

    return seeded_count


async def seed_from_json[T, M](
    db_session: AsyncSession,
    model_class: type[M],
    schema_class: type[T],
    directory: Path,
    unique_field: str,
    transform_fn: Callable[[T], M],
    validate_fn: Callable[[T], list[str]] | None = None,
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
        validate_fn: Optional function to validate data after schema validation
        file_pattern: Glob pattern for JSON files (default: "*.json")

    Returns:
        Number of records seeded
    """
    try:
        all_data = await _load_json_files(directory, file_pattern, schema_class)

        if not all_data:
            return 0

        existing_values = await _get_existing_values(db_session, model_class, unique_field)

        seeded_count = _seed_records(db_session, all_data, existing_values, unique_field, transform_fn, validate_fn)

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
