"""
Data migration script for v2.10.0 - Convert existing objectives to structured format.

This script parses existing objective challenge strings and sets objective_type,
target_entity, and target_amount fields.

Usage:
    cd backend
    uv run python -m app.scripts.migrate_objective_data
"""

import asyncio
import logging
import re

from app.core.db import async_session_maker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import objective as objective_crud

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _determine_objective_type(challenge_lower: str) -> str:
    """Determine objective type from challenge text."""
    type_keywords = [
        ("collect", ["collect", "gather"]),
        ("build", ["build", "construct"]),
        ("train", ["train"]),
        ("assign", ["assign"]),
        ("kill", ["kill", "defeat"]),
        ("reach", ["reach", "have"]),
        ("explore", ["explore"]),
        ("rush", ["rush"]),
        ("equip", ["equip"]),
    ]

    for obj_type, keywords in type_keywords:
        if any(keyword in challenge_lower for keyword in keywords):
            return obj_type

    return "reach"


def _determine_dweller_target(challenge_lower: str, amount: int, obj_type: str) -> dict:
    """Determine dweller-specific target."""
    if obj_type == "train":
        return {"entity_type": "dweller", "action": "train"}
    if obj_type == "assign":
        return {"entity_type": "dweller", "action": "assign"}
    if "level" in challenge_lower:
        return {"entity_type": "dweller", "action": "level_up"}
    return {"entity_type": "dweller", "count": amount}


def _determine_target_entity(challenge_lower: str, amount: int, obj_type: str) -> dict:
    """Determine target entity from challenge text."""
    resource_types = [
        ("caps", ["cap"]),
        ("power", ["power"]),
        ("food", ["food"]),
        ("water", ["water"]),
    ]

    for resource_type, keywords in resource_types:
        if any(keyword in challenge_lower for keyword in keywords):
            return {"resource_type": resource_type}

    if "room" in challenge_lower:
        return {"entity_type": "room"}

    if "dweller" in challenge_lower:
        return _determine_dweller_target(challenge_lower, amount, obj_type)

    if "living quarter" in challenge_lower:
        return {"room_type": "living_quarters"}

    return {"description": challenge_lower}


def parse_objective_challenge(challenge: str) -> dict:
    """Parse objective challenge string into structured data.

    Examples:
        "Collect 100 Caps" -> {type: "collect", target: "caps", amount: 100}
        "Build 3 Rooms" -> {type: "build", target: "room", amount: 3}
        "Train a Dweller" -> {type: "train", target: "dweller", amount: 1}
    """
    challenge_lower = challenge.lower()
    obj_type = _determine_objective_type(challenge_lower)

    # Extract amount (first number found)
    amount_match = re.search(r"(\d+)", challenge)
    amount = int(amount_match.group(1)) if amount_match else 1

    target = _determine_target_entity(challenge_lower, amount, obj_type)

    return {
        "type": obj_type,
        "target": target,
        "amount": amount,
    }


async def migrate_objective_data(db: AsyncSession) -> dict:
    """Migrate existing objective data to structured format.

    Returns:
        dict with count of objectives updated
    """
    logger.info("Starting objective data migration...")

    # Get all objectives
    objectives = await objective_crud.get_all(db)
    logger.info(f"Found {len(objectives)} objectives to process")

    stats = {"objectives_updated": 0}

    for objective in objectives:
        logger.info(f"Processing objective: {objective.challenge}")

        parsed = parse_objective_challenge(objective.challenge)

        objective.objective_type = parsed["type"]
        objective.target_entity = parsed["target"]
        objective.target_amount = parsed["amount"]

        # Ensure total matches target_amount if not already set
        objective.total = max(objective.total, parsed["amount"])

        stats["objectives_updated"] += 1
        logger.debug(
            f"  Set type={parsed['type']}, amount={parsed['amount']}, target={parsed['target']}"
        )

    await db.commit()
    logger.info(f"Migration complete: {stats}")
    return stats


async def main():
    """Main entry point."""
    async with async_session_maker() as db:
        stats = await migrate_objective_data(db)
        print("\nMigration Summary:")
        print(f"  Objectives updated: {stats['objectives_updated']}")


if __name__ == "__main__":
    asyncio.run(main())
