"""Tests for quest seeding utility."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.quest import Quest
from app.utils.seed_quests import seed_quests_from_json


@pytest.mark.asyncio
async def test_seed_quests_from_json_basic(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test basic quest seeding from JSON files."""
    # Create temporary quest directory
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()

    # Create a simple quest JSON file
    quest_data = [
        {
            "Quest name": "Test Quest 1",
            "Long description": "This is a test quest for seeding",
            "Short description": "Test quest",
            "Requirements": "Level 5 dwellers",
            "Rewards": "100 caps",
            "Quest objective": "Complete the test",
        }
    ]

    quest_file = quest_dir / "test_quests.json"
    with quest_file.open("w", encoding="utf-8") as f:
        json.dump(quest_data, f)

    # Seed quests
    seeded_count = await seed_quests_from_json(async_session, quest_dir=quest_dir)

    assert seeded_count == 1

    # Verify quest was added to database
    result = await async_session.execute(select(Quest).where(Quest.title == "Test Quest 1"))
    quest = result.scalar_one_or_none()

    assert quest is not None
    assert quest.title == "Test Quest 1"
    assert quest.short_description == "Test quest"
    assert quest.long_description == "This is a test quest for seeding"
    assert quest.requirements == "Level 5 dwellers"
    assert quest.rewards == "100 caps"


@pytest.mark.asyncio
async def test_seed_quests_with_list_requirements(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding quests with list-based requirements."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()

    # Create quest with list requirements
    quest_data = [
        {
            "Quest name": "Multi Requirement Quest",
            "Long description": "Quest with multiple requirements",
            "Short description": "Multi req quest",
            "Requirements": ["Level 10 dwellers", "Lucy's vault suit", "The Ghoul's coat"],
            "Rewards": "500 caps",
            "Quest objective": "Complete all requirements",
        }
    ]

    quest_file = quest_dir / "multi_req.json"
    with quest_file.open("w", encoding="utf-8") as f:
        json.dump(quest_data, f)

    seeded_count = await seed_quests_from_json(async_session, quest_dir=quest_dir)
    assert seeded_count == 1

    # Verify requirements were joined properly
    result = await async_session.execute(select(Quest).where(Quest.title == "Multi Requirement Quest"))
    quest = result.scalar_one_or_none()

    assert quest is not None
    assert "Level 10 dwellers" in quest.requirements
    assert "Lucy's vault suit" in quest.requirements
    assert "The Ghoul's coat" in quest.requirements
    assert ", " in quest.requirements  # Should be comma-separated


@pytest.mark.asyncio
async def test_seed_quests_prevents_duplicates(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that seeding doesn't create duplicates."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()

    quest_data = [
        {
            "Quest name": "Unique Quest",
            "Long description": "A unique quest",
            "Short description": "Unique",
            "Requirements": "Level 1",
            "Rewards": "10 caps",
            "Quest objective": "Be unique",
        }
    ]

    quest_file = quest_dir / "unique.json"
    with quest_file.open("w", encoding="utf-8") as f:
        json.dump(quest_data, f)

    # First seeding
    first_count = await seed_quests_from_json(async_session, quest_dir=quest_dir)
    assert first_count == 1

    # Second seeding (should not add duplicate)
    second_count = await seed_quests_from_json(async_session, quest_dir=quest_dir)
    assert second_count == 0

    # Verify only one quest exists
    result = await async_session.execute(select(Quest).where(Quest.title == "Unique Quest"))
    quests = result.scalars().all()
    assert len(quests) == 1


@pytest.mark.asyncio
async def test_seed_quests_multiple_files(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding quests from multiple JSON files."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()

    # Create first quest file
    quest_data1 = [
        {
            "Quest name": "Quest A",
            "Long description": "First quest file",
            "Short description": "Quest A",
            "Requirements": "Level 5",
            "Rewards": "50 caps",
            "Quest objective": "Complete A",
        }
    ]
    with (quest_dir / "quests_a.json").open("w", encoding="utf-8") as f:
        json.dump(quest_data1, f)

    # Create second quest file
    quest_data2 = [
        {
            "Quest name": "Quest B",
            "Long description": "Second quest file",
            "Short description": "Quest B",
            "Requirements": "Level 10",
            "Rewards": "100 caps",
            "Quest objective": "Complete B",
        }
    ]
    with (quest_dir / "quests_b.json").open("w", encoding="utf-8") as f:
        json.dump(quest_data2, f)

    # Seed all quests
    seeded_count = await seed_quests_from_json(async_session, quest_dir=quest_dir)
    assert seeded_count == 2

    # Verify both quests exist
    result = await async_session.execute(select(Quest))
    quests = result.scalars().all()
    quest_titles = {q.title for q in quests}

    assert "Quest A" in quest_titles
    assert "Quest B" in quest_titles


@pytest.mark.asyncio
async def test_seed_quests_handles_errors_gracefully(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that seeding handles errors gracefully."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()

    # Create an invalid JSON file
    invalid_file = quest_dir / "invalid.json"
    with invalid_file.open("w", encoding="utf-8") as f:
        f.write("{ invalid json }")

    # Create a valid JSON file
    valid_data = [
        {
            "Quest name": "Valid Quest",
            "Long description": "This quest is valid",
            "Short description": "Valid",
            "Requirements": "Level 1",
            "Rewards": "5 caps",
            "Quest objective": "Be valid",
        }
    ]
    valid_file = quest_dir / "valid.json"
    with valid_file.open("w", encoding="utf-8") as f:
        json.dump(valid_data, f)

    # Seeding should continue despite invalid file
    seeded_count = await seed_quests_from_json(async_session, quest_dir=quest_dir)

    # At least the valid quest should be seeded
    assert seeded_count >= 1

    # Verify valid quest exists
    result = await async_session.execute(select(Quest).where(Quest.title == "Valid Quest"))
    quest = result.scalar_one_or_none()
    assert quest is not None


@pytest.mark.asyncio
async def test_seed_quests_empty_directory(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding with empty quest directory."""
    quest_dir = tmp_path / "empty_quests"
    quest_dir.mkdir()

    seeded_count = await seed_quests_from_json(async_session, quest_dir=quest_dir)
    assert seeded_count == 0


@pytest.mark.asyncio
async def test_seed_quests_nonexistent_directory(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test seeding with nonexistent quest directory."""
    quest_dir = tmp_path / "nonexistent"

    # Should handle gracefully and return 0
    seeded_count = await seed_quests_from_json(async_session, quest_dir=quest_dir)
    assert seeded_count == 0


@pytest.mark.asyncio
async def test_seed_quests_rollback_on_error(async_session: AsyncSession, tmp_path: Path) -> None:
    """Test that seeding rolls back on critical errors."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()

    # Create quest data
    quest_data = [
        {
            "Quest name": "Test Quest",
            "Long description": "Test",
            "Short description": "Test",
            "Requirements": "Level 1",
            "Rewards": "10 caps",
            "Quest objective": "Test",
        }
    ]
    with (quest_dir / "test.json").open("w", encoding="utf-8") as f:
        json.dump(quest_data, f)

    # Mock commit to raise an exception
    with patch.object(async_session, "commit", side_effect=Exception("Database error")):
        seeded_count = await seed_quests_from_json(async_session, quest_dir=quest_dir)
        assert seeded_count == 0

    # Verify no quests were added
    result = await async_session.execute(select(Quest))
    quests = result.scalars().all()
    assert len(quests) == 0
