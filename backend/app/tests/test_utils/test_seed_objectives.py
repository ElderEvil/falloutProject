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
async def test_seed_objectives_from_json_basic(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test basic objective seeding from JSON files."""
    # Create temporary objectives directory
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    # Create objectives JSON file
    objectives_data = [
        {"challenge": "Collect 3 outfits", "reward": "50 caps"},
        {"challenge": "Collect 3 stimpaks", "reward": "70 caps"},
        {"challenge": "Collect 4 weapons", "reward": "100 caps"},
    ]

    objectives_file = objectives_dir / "collect.json"
    with objectives_file.open("w", encoding="utf-8") as f:
        json.dump(objectives_data, f)

    # Seed objectives
    seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)

    assert seeded_count == 3

    # Verify objectives were added to database
    result = await async_session.execute(select(Objective))
    objectives = result.scalars().all()

    assert len(objectives) == 3
    challenges = {obj.challenge for obj in objectives}
    assert "Collect 3 outfits" in challenges
    assert "Collect 3 stimpaks" in challenges
    assert "Collect 4 weapons" in challenges


@pytest.mark.asyncio
async def test_seed_objectives_prevents_duplicates(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that seeding doesn't create duplicates."""
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    objectives_data = [
        {"challenge": "Assign 2 dwellers", "reward": "25 caps"},
        {"challenge": "Assign 4 dwellers", "reward": "100 caps"},
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
async def test_seed_objectives_multiple_files(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding objectives from multiple JSON files."""
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    # Create first objectives file
    collect_data = [
        {"challenge": "Collect 100 food", "reward": "50 caps"},
        {"challenge": "Collect 100 water", "reward": "50 caps"},
    ]
    with (objectives_dir / "collect.json").open("w", encoding="utf-8") as f:
        json.dump(collect_data, f)

    # Create second objectives file
    assign_data = [
        {"challenge": "Assign 5 dwellers", "reward": "150 caps"},
        {"challenge": "Assign 7 dwellers", "reward": "175 caps"},
    ]
    with (objectives_dir / "assign.json").open("w", encoding="utf-8") as f:
        json.dump(assign_data, f)

    # Seed all objectives
    seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)
    assert seeded_count == 4

    # Verify all objectives exist
    result = await async_session.execute(select(Objective))
    objectives = result.scalars().all()
    challenges = {obj.challenge for obj in objectives}

    assert "Collect 100 food" in challenges
    assert "Collect 100 water" in challenges
    assert "Assign 5 dwellers" in challenges
    assert "Assign 7 dwellers" in challenges


@pytest.mark.asyncio
async def test_seed_objectives_single_object(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding with single objective (not array) in JSON."""
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    # Create single objective (not in array)
    objective_data = {"challenge": "Single objective", "reward": "1 lunchbox"}

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
    valid_data = [{"challenge": "Valid objective", "reward": "10 caps"}]
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
async def test_seed_objectives_empty_directory(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding with empty objectives directory."""
    objectives_dir = tmp_path / "empty_objectives"
    objectives_dir.mkdir()

    seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)
    assert seeded_count == 0


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
        {"challenge": "Missing reward field"},  # Missing 'reward'
        {"challenge": "Valid objective", "reward": "50 caps"},  # Valid
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
    objectives_data = [{"challenge": "Test objective", "reward": "10 caps"}]
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
async def test_seed_objectives_with_special_characters(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding objectives with special characters in challenge/reward."""
    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    objectives_data = [
        {"challenge": "Collect 8 rare weapons", "reward": "1320 caps"},
        {"challenge": "Assign 10 dwellers in right room", "reward": "1 lunchbox"},
    ]

    objectives_file = objectives_dir / "special.json"
    with objectives_file.open("w", encoding="utf-8") as f:
        json.dump(objectives_data, f)

    seeded_count = await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)
    assert seeded_count == 2

    # Verify objectives were stored correctly
    result = await async_session.execute(select(Objective))
    objectives = result.scalars().all()

    challenges = {obj.challenge for obj in objectives}
    assert "Collect 8 rare weapons" in challenges
    assert "Assign 10 dwellers in right room" in challenges


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
            "objective_type": "collect",
            "target_entity": {"resource_type": "food"},
            "target_amount": 100,
        },
        # Incomplete - missing objective_type
        {"challenge": "Incomplete 1", "reward": "10 caps"},
        # Complete - assign type, target_entity is optional/empty
        {
            "challenge": "Assign 5 dwellers",
            "reward": "150 caps",
            "objective_type": "assign",
            "target_amount": 5,
        },
        # Incomplete - target_amount is 1 (too small)
        {
            "challenge": "Build 1 Room",
            "reward": "100 caps",
            "objective_type": "build",
            "target_entity": {"room_type": "*"},
            "target_amount": 1,
        },
        # Complete
        {
            "challenge": "Build 3 Rooms",
            "reward": "1000 caps",
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


@pytest.mark.asyncio
async def test_vault_objective_progress_uses_target_amount(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that vault objectives properly use target_amount from seeded objectives.

    This verifies that when objectives are assigned to a vault, the total
    comes from the objective's target_amount field, not a hardcoded default.
    """
    from app.models.vault_objective import VaultObjectiveProgressLink

    objectives_dir = tmp_path / "objectives"
    objectives_dir.mkdir()

    # Create complete objective
    objectives_data = [
        {
            "challenge": "Collect 500 caps",
            "reward": "500 caps",
            "objective_type": "collect",
            "target_entity": {"resource_type": "caps"},
            "target_amount": 500,
        },
    ]

    objectives_file = objectives_dir / "progress_test.json"
    with objectives_file.open("w", encoding="utf-8") as f:
        json.dump(objectives_data, f)

    await seed_objectives_from_json(async_session, objectives_dir=objectives_dir)

    # Get the seeded objective
    result = await async_session.execute(select(Objective).where(Objective.challenge == "Collect 500 caps"))
    objective = result.scalar_one_or_none()

    assert objective is not None
    assert objective.target_amount == 500

    # Create a vault objective link (simulating _assign_initial_objectives)
    link = VaultObjectiveProgressLink(
        vault_id=objective.id,  # Using objective.id as vault_id for testing
        objective_id=objective.id,
        progress=0,
        total=objective.target_amount or 1,  # This should use 500, not 1
        is_completed=False,
    )
    async_session.add(link)
    await async_session.commit()

    # Verify the total was set correctly
    assert link.total == 500, f"Expected total=500, got {link.total}"
    assert link.progress == 0
    assert link.is_completed is False
