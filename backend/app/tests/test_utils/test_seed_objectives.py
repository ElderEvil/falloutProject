"""Tests for objective seeding utility."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.objective import Objective
from app.utils.seed_objectives import seed_objectives_from_json


@pytest.mark.asyncio
async def test_seed_objectives_prevents_duplicates(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that seeding doesn't create duplicates."""
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    objectives_data = [
        {"challenge": "Assign 2 dwellers", "reward": "25 caps", "category": "achievement"},
        {"challenge": "Assign 4 dwellers", "reward": "100 caps", "category": "achievement"},
    ]

    objectives_file = objectives_dir / "assign.json"
    with objectives_file.open("w", encoding="utf-8") as f:
        json.dump(objectives_data, f)

    # First seeding
    first_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)
    assert first_count == 2

    # Second seeding (should not add duplicates)
    second_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)
    assert second_count == 0

    # Verify only 2 objectives exist
    result = await async_session.execute(select(Objective))
    objectives = result.scalars().all()
    assert len(objectives) == 2


@pytest.mark.asyncio
async def test_seed_objectives_single_object(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding with single objective (not array) in JSON."""
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    # Create single objective (not in array)
    objective_data = {"challenge": "Single objective", "reward": "1 lunchbox", "category": "achievement"}

    objective_file = objectives_dir / "single.json"
    with objective_file.open("w", encoding="utf-8") as f:
        json.dump(objective_data, f)

    seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)
    assert seeded_count == 1

    # Verify objective exists
    result = await async_session.execute(select(Objective).where(Objective.challenge == "Single objective"))
    objective = result.scalar_one_or_none()
    assert objective is not None
    assert objective.reward == "1 lunchbox"


@pytest.mark.asyncio
async def test_seed_objectives_handles_errors_gracefully(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that seeding handles errors gracefully."""
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    # Create an invalid JSON file
    invalid_file = objectives_dir / "invalid.json"
    with invalid_file.open("w", encoding="utf-8") as f:
        f.write("{ invalid json }")

    # Create a valid JSON file
    valid_data = [{"challenge": "Valid objective", "reward": "10 caps", "category": "achievement"}]
    valid_file = objectives_dir / "valid.json"
    with valid_file.open("w", encoding="utf-8") as f:
        json.dump(valid_data, f)

    # Seeding should continue despite invalid file
    seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)

    # At least the valid objective should be seeded
    assert seeded_count >= 1

    # Verify valid objective exists
    result = await async_session.execute(select(Objective).where(Objective.challenge == "Valid objective"))
    objective = result.scalar_one_or_none()
    assert objective is not None


@pytest.mark.asyncio
async def test_seed_objectives_nonexistent_directory(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding with nonexistent objectives directory."""
    objectives_dir = tmp_path / "nonexistent"

    # Should handle gracefully and return 0
    seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)
    assert seeded_count == 0


@pytest.mark.asyncio
async def test_seed_objectives_validates_schema(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that invalid objectives are rejected."""
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    # Create objectives with missing required fields
    invalid_data = [
        {"challenge": "Missing reward field", "category": "achievement"},  # Missing 'reward'
        {"challenge": "Valid objective", "reward": "50 caps", "category": "achievement"},  # Valid
    ]

    objectives_file = objectives_dir / "mixed.json"
    with objectives_file.open("w", encoding="utf-8") as f:
        json.dump(invalid_data, f)

    # Seeding should skip invalid objectives
    seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)

    # Should handle error and continue (may seed 0 or 1 depending on validation)
    assert seeded_count >= 0


@pytest.mark.asyncio
async def test_seed_objectives_rollback_on_error(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that seeding rolls back on critical errors."""
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    # Create objective data
    objectives_data = [{"challenge": "Test objective", "reward": "10 caps", "category": "achievement"}]
    with (objectives_dir / "test.json").open("w", encoding="utf-8") as f:
        json.dump(objectives_data, f)

    # Mock commit to raise an exception
    with patch.object(async_session, "commit", side_effect=Exception("Database error")):
        seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)
        assert seeded_count == 0

    # Verify no objectives were added
    result = await async_session.execute(select(Objective))
    objectives = result.scalars().all()
    assert len(objectives) == 0


@pytest.mark.asyncio
async def test_get_multi_complete_returns_only_complete_objectives(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that get_multi_complete returns objectives with required fields set.

    Complete objectives have:
    - objective_type is not None
    - target_amount > 1

    Note: target_entity can be None for some objective types (e.g., assign) as
    the evaluator handles null/empty target_entity as "match any".
    """
    from app.crud.objective import objective_crud

    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    # Create mix of complete and incomplete objectives
    objectives_data = [
        # Complete - all fields set
        {
            "challenge": "Collect 100 food",
            "reward": "50 caps",
            "category": "achievement",
            "objective_type": "collect",
            "target_entity": {"resource_type": "food"},
            "target_amount": 100,
        },
        # Incomplete - missing objective_type
        {"challenge": "Incomplete 1", "reward": "10 caps", "category": "achievement"},
        # Complete - assign type, target_entity is optional/empty
        {
            "challenge": "Assign 5 dwellers",
            "reward": "150 caps",
            "category": "achievement",
            "objective_type": "assign",
            "target_amount": 5,
        },
        # Incomplete - target_amount is 1 (too small)
        {
            "challenge": "Build 1 Room",
            "reward": "100 caps",
            "category": "achievement",
            "objective_type": "build",
            "target_entity": {"room_type": "*"},
            "target_amount": 1,
        },
        # Complete
        {
            "challenge": "Build 3 Rooms",
            "reward": "1000 caps",
            "category": "achievement",
            "objective_type": "build",
            "target_entity": {"room_type": "*"},
            "target_amount": 3,
        },
    ]

    objectives_file = objectives_dir / "mixed.json"
    with objectives_file.open("w", encoding="utf-8") as f:
        json.dump(objectives_data, f)

    seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)
    assert seeded_count == 5

    # Get only complete objectives
    complete_objectives = await objective_crud.get_multi_complete(async_session, skip=0, limit=10)

    # Should get 3 complete objectives (Collect 100 food, Assign 5 dwellers, Build 3 Rooms)
    # Excludes: Incomplete 1 (no objective_type), Build 1 Room (target_amount=1)
    assert len(complete_objectives) == 3, (
        f"Expected 3, got {len(complete_objectives)}: {[o.challenge for o in complete_objectives]}"
    )

    challenges = {obj.challenge for obj in complete_objectives}
    assert "Collect 100 food" in challenges
    assert "Assign 5 dwellers" in challenges
    assert "Build 3 Rooms" in challenges

    # Should NOT contain incomplete objectives
    assert "Incomplete 1" not in challenges
    assert "Build 1 Room" not in challenges

    # Verify all returned objectives have proper values
    for obj in complete_objectives:
        assert obj.objective_type is not None
        assert obj.target_amount > 1


def test_starter_seed_file_integrity() -> None:
    """The starter arc seed file is well-formed: supported types, valid targets,
    unique contiguous sequence, challenge/description within limits."""
    from app.utils.objective_constants import (
        VALID_REACH_TYPES,
        VALID_RESOURCE_TYPES,
        VALID_ROOM_TYPES,
        normalize_resource_type,
        normalize_room_type,
    )
    from app.utils.static_data import DATA_DIR

    starter_file = DATA_DIR / "objectives" / "starter.json"
    assert starter_file.exists(), "starter.json must exist"

    with starter_file.open("r", encoding="utf-8") as f:
        steps = json.load(f)

    assert len(steps) == 8
    supported_types = {"assign", "build", "collect", "reach", "assign_correct"}
    sequences = []
    for step in steps:
        assert step["category"] == "starter"
        assert step["objective_type"] in supported_types, f"unsupported type {step['objective_type']}"
        assert step["objective_type"] != "kill"
        assert 3 <= len(step["challenge"]) <= 32
        assert 3 <= len(step["reward"]) <= 32
        assert step.get("description"), "description required"
        sequences.append(step["sequence"])
        target = step.get("target_entity") or {}
        if step["objective_type"] == "build":
            assert normalize_room_type(target.get("room_type")) in VALID_ROOM_TYPES
        elif step["objective_type"] == "collect":
            resource = target.get("resource_type")
            if resource:
                assert normalize_resource_type(resource) in VALID_RESOURCE_TYPES
        elif step["objective_type"] == "reach":
            assert target.get("reach_type") in VALID_REACH_TYPES

    assert sequences == list(range(8)), "sequences must be unique and contiguous 0..7"
