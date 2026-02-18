"""Objective seeding utility to populate database from JSON files on startup."""

import logging
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.objective import Objective
from app.schemas.objective import ObjectiveCreate
from app.utils.objective_constants import validate_target_entity
from app.utils.seeding import seed_from_json
from app.utils.static_data import DATA_DIR

logger = logging.getLogger(__name__)


def _transform_objective_create_to_model(objective_data: ObjectiveCreate) -> Objective:
    """Transform ObjectiveCreate schema to Objective model."""
    return Objective(
        challenge=objective_data.challenge,
        reward=objective_data.reward,
        category=objective_data.category,
        objective_type=objective_data.objective_type,
        target_entity=objective_data.target_entity,
        target_amount=objective_data.target_amount,
    )


def _validate_objective(objective_data: ObjectiveCreate) -> list[str]:
    """Validate an objective's target_entity.

    Args:
        objective_data: The objective data to validate

    Returns:
        List of validation errors (empty if valid)
    """
    return validate_target_entity(
        objective_type=objective_data.objective_type or "",
        target_entity=objective_data.target_entity,
    )


async def seed_objectives_from_json(db_session: AsyncSession, objectives_dir: Path | None = None) -> int:
    """
    Seed objectives from JSON files into database if they don't already exist.

    Args:
        db_session: Database session
        objectives_dir: Directory containing objective JSON files (defaults to app/data/objectives)

    Returns:
        Number of objectives seeded
    """
    if objectives_dir is None:
        objectives_dir = DATA_DIR / "objectives"

    return await seed_from_json(
        db_session=db_session,
        model_class=Objective,
        schema_class=ObjectiveCreate,
        directory=objectives_dir,
        unique_field="challenge",
        transform_fn=_transform_objective_create_to_model,
        validate_fn=_validate_objective,
    )
