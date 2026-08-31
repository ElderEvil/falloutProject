"""Tests for quest seeding utility."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.quest_reward import QuestReward
from app.utils.seed_quests import seed_quests_from_json
from app.utils.static_data import game_data_store


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
async def test_seed_quests_syncs_quest_metadata(async_session: AsyncSession, tmp_path: Path) -> None:
    """Quest JSON metadata keeps state objectives out of the timed quest flow."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()
    quest_file = quest_dir / "onboarding.json"
    quest_data = {
        "chain_id": "onboarding",
        "chain_name": "Onboarding",
        "quests": [
            {
                "quest_name": "Build a Room",
                "short_description": "Build your first room.",
                "long_description": "Build a Living Quarter to house your dwellers.",
                "requirements": "1 Living Quarter",
                "rewards": "100 caps",
                "quest_type": "main",
                "quest_category": "building",
                "chain_order": 2,
            }
        ],
    }
    with quest_file.open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)

    assert await seed_quests_from_json(async_session, quest_dir=quest_dir) == 1
    quest = (await async_session.execute(select(Quest).where(Quest.title == "Build a Room"))).scalar_one()
    assert (quest.quest_type.value, quest.quest_category, quest.chain_id, quest.chain_order) == (
        "main",
        "building",
        "onboarding",
        2,
    )

    quest.quest_category = None
    await async_session.commit()
    assert await seed_quests_from_json(async_session, quest_dir=quest_dir) == 0
    assert quest.quest_category == "building"


@pytest.mark.asyncio
async def test_seed_quests_rejects_duplicate_names(async_session: AsyncSession, tmp_path: Path) -> None:
    """A duplicate title cannot silently acquire another chain's metadata."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()
    for chain_id in ("first", "second"):
        with (quest_dir / f"{chain_id}.json").open("w", encoding="utf-8") as file:
            json.dump(
                {
                    "chain_id": chain_id,
                    "quests": [{"quest_name": "Duplicate Quest", "chain_order": 1}],
                },
                file,
            )

    with pytest.raises(ValueError, match="Duplicate quest_name 'Duplicate Quest'"):
        await seed_quests_from_json(async_session, quest_dir=quest_dir)


@pytest.mark.asyncio
async def test_seed_quests_persists_item_reward_data(async_session: AsyncSession, tmp_path: Path) -> None:
    """Seeded item rewards retain the data needed to grant the listed item."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()
    quest_data = [
        {
            "Quest name": "Rewarded Quest",
            "Long description": "A quest with an outfit reward.",
            "Short description": "Earn an outfit",
            "Requirements": "Level 1",
            "Rewards": "Vault Suit",
            "quest_rewards": [
                {
                    "reward_type": "ITEM",
                    "reward_data": {"item_name": "Vault Suit", "quantity": 1},
                    "item_data": {
                        "item_type": "outfit",
                        "name": "Vault Suit",
                        "rarity": "rare",
                        "outfit_type": "jumpsuit",
                    },
                }
            ],
        }
    ]
    with (quest_dir / "rewards.json").open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)

    assert await seed_quests_from_json(async_session, quest_dir=quest_dir) == 1

    quest = (await async_session.execute(select(Quest).where(Quest.title == "Rewarded Quest"))).scalar_one()
    reward = (await async_session.execute(select(QuestReward).where(QuestReward.quest_id == quest.id))).scalar_one()
    assert reward.item_data == {
        "item_type": "outfit",
        "name": "Vault Suit",
        "rarity": "rare",
        "outfit_type": "jumpsuit",
    }


@pytest.mark.asyncio
async def test_seed_quests_updates_existing_reward_payload(async_session: AsyncSession, tmp_path: Path) -> None:
    """Re-seeding adds typed item data to an existing quest reward."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()
    quest_data = [
        {
            "Quest name": "Existing Reward Quest",
            "Long description": "A quest whose reward data was improved.",
            "Short description": "Upgrade its reward",
            "Requirements": "Level 1",
            "Rewards": "Vault Suit",
            "quest_rewards": [
                {
                    "reward_type": "ITEM",
                    "reward_data": {"item_name": "Vault Suit", "quantity": 1},
                    "item_data": {"item_type": "outfit", "name": "Vault Suit", "rarity": "rare"},
                }
            ],
        }
    ]
    with (quest_dir / "rewards.json").open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)

    existing_quest = Quest(
        title="Existing Reward Quest",
        short_description="Upgrade its reward",
        long_description="A quest whose reward data was improved.",
        requirements="Level 1",
        rewards="Vault Suit",
    )
    async_session.add(existing_quest)
    await async_session.flush()
    async_session.add(
        QuestReward(
            quest_id=existing_quest.id,
            reward_type="item",
            reward_data={"item_name": "Vault Suit", "quantity": 1},
        )
    )
    await async_session.commit()

    assert await seed_quests_from_json(async_session, quest_dir=quest_dir) == 0

    reward = (
        await async_session.execute(select(QuestReward).where(QuestReward.quest_id == existing_quest.id))
    ).scalar_one()
    assert reward.item_data == {"item_type": "outfit", "name": "Vault Suit", "rarity": "rare"}


@pytest.mark.asyncio
async def test_seed_quests_updates_changed_reward_data(async_session: AsyncSession, tmp_path: Path) -> None:
    """Re-seeding matches a changed reward to its existing reward slot."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()
    quest_file = quest_dir / "rewards.json"
    quest_data = [
        {
            "Quest name": "Mutable Reward Quest",
            "Long description": "A quest with a balance adjustment.",
            "Short description": "Update reward",
            "Requirements": "Level 1",
            "Rewards": "100 caps",
            "quest_rewards": [{"reward_type": "CAPS", "reward_data": {"amount": 100}}],
        }
    ]
    with quest_file.open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)
    await seed_quests_from_json(async_session, quest_dir=quest_dir)

    quest_data[0]["quest_rewards"][0]["reward_data"] = {"amount": 250}
    with quest_file.open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)
    assert await seed_quests_from_json(async_session, quest_dir=quest_dir) == 0

    quest = (await async_session.execute(select(Quest).where(Quest.title == "Mutable Reward Quest"))).scalar_one()
    reward = (await async_session.execute(select(QuestReward).where(QuestReward.quest_id == quest.id))).scalar_one()
    assert reward.reward_data == {"amount": 250}


@pytest.mark.asyncio
async def test_seed_quests_adds_new_rewards_to_existing_quest(async_session: AsyncSession, tmp_path: Path) -> None:
    """Re-seeding creates a reward appended to an already-seeded quest."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()
    quest_file = quest_dir / "rewards.json"
    quest_data = [
        {
            "Quest name": "Expanding Reward Quest",
            "Long description": "A quest whose reward list grows.",
            "Short description": "Add a reward",
            "Requirements": "Level 1",
            "Rewards": "100 caps",
            "quest_rewards": [{"reward_type": "CAPS", "reward_data": {"amount": 100}}],
        }
    ]
    with quest_file.open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)
    await seed_quests_from_json(async_session, quest_dir=quest_dir)

    quest_data[0]["quest_rewards"].append({"reward_type": "STIMPAK", "reward_data": {"quantity": 2}})
    with quest_file.open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)
    assert await seed_quests_from_json(async_session, quest_dir=quest_dir) == 0

    quest = (await async_session.execute(select(Quest).where(Quest.title == "Expanding Reward Quest"))).scalar_one()
    rewards = (await async_session.execute(select(QuestReward).where(QuestReward.quest_id == quest.id))).scalars().all()
    assert sorted((reward.reward_type.value, reward.reward_data) for reward in rewards) == [
        ("caps", {"amount": 100}),
        ("stimpak", {"quantity": 2}),
    ]


@pytest.mark.asyncio
async def test_seed_quests_migrates_legacy_dweller_reward_to_template(
    async_session: AsyncSession, tmp_path: Path
) -> None:
    """A former name-based dweller reward becomes a template reference."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()
    quest_data = [
        {
            "Quest name": "Recruit Lucy",
            "Long description": "Recruit a capable vault dweller.",
            "Short description": "Find Lucy",
            "Requirements": "Level 20",
            "Rewards": "Lucy MacLean",
            "quest_rewards": [{"reward_type": "DWELLER", "reward_data": {"template_id": "lucy-maclean"}}],
        }
    ]
    with (quest_dir / "rewards.json").open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)

    quest = Quest(
        title="Recruit Lucy",
        short_description="Find Lucy",
        long_description="Recruit a capable vault dweller.",
        requirements="Level 20",
        rewards="Lucy MacLean",
    )
    async_session.add(quest)
    await async_session.flush()
    async_session.add(QuestReward(quest_id=quest.id, reward_type="dweller", reward_data={"name": "Lucy MacLean"}))
    await async_session.commit()

    assert await seed_quests_from_json(async_session, quest_dir=quest_dir) == 0

    reward = (await async_session.execute(select(QuestReward).where(QuestReward.quest_id == quest.id))).scalar_one()
    assert reward.reward_data == {"template_id": "lucy-maclean"}


def test_dweller_quest_rewards_reference_canonical_templates() -> None:
    """Every static dweller reward must resolve to an owned template."""
    for chain in game_data_store.quests:
        for quest in chain.quests:
            for reward in quest.quest_rewards:
                if reward.reward_type.upper() == "DWELLER":
                    template_id = reward.reward_data.get("template_id")
                    assert template_id, f"{quest.quest_name} is missing a dweller template_id"
                    assert game_data_store.get_dweller(template_id), f"Unknown template {template_id}"


@pytest.mark.asyncio
async def test_seed_quests_records_completed_quest_predecessor(async_session: AsyncSession, tmp_path: Path) -> None:
    """Seeded quest-completion requirements also populate the chain predecessor."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()
    quest_data = {
        "chain_name": "Test chain",
        "quests": [
            {
                "quest_name": "Chain Starter",
                "long_description": "The first quest in a test chain.",
                "short_description": "Start the chain",
                "requirements": "Level 1",
                "rewards": "10 caps",
            },
            {
                "quest_name": "Chain Follow-up",
                "long_description": "The second quest in a test chain.",
                "short_description": "Continue the chain",
                "requirements": "Level 1",
                "rewards": "20 caps",
                "quest_requirements": [
                    {
                        "requirement_type": "QUEST_COMPLETED",
                        "requirement_data": {"quest_name": "Chain Starter"},
                    }
                ],
            },
        ],
    }
    with (quest_dir / "chain.json").open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)

    assert await seed_quests_from_json(async_session, quest_dir=quest_dir) == 2

    quests = (await async_session.execute(select(Quest))).scalars().all()
    quests_by_title = {quest.title: quest for quest in quests}
    assert quests_by_title["Chain Follow-up"].previous_quest_id == quests_by_title["Chain Starter"].id


@pytest.mark.asyncio
async def test_seed_quests_skips_requirement_with_invalid_predecessor_id(
    async_session: AsyncSession, tmp_path: Path
) -> None:
    """Malformed predecessor IDs do not leave pending requirements to commit."""
    quest_dir = tmp_path / "quests"
    quest_dir.mkdir()
    quest_data = {
        "quests": [
            {
                "quest_name": "Malformed Predecessor",
                "long_description": "A quest with a malformed predecessor.",
                "short_description": "Invalid predecessor",
                "requirements": "Level 1",
                "rewards": "10 caps",
                "quest_requirements": [
                    {
                        "requirement_type": "QUEST_COMPLETED",
                        "requirement_data": {"quest_id": "not-a-uuid"},
                    }
                ],
            }
        ]
    }
    with (quest_dir / "malformed.json").open("w", encoding="utf-8") as file:
        json.dump(quest_data, file)

    assert await seed_quests_from_json(async_session, quest_dir=quest_dir) == 1

    quest = (await async_session.execute(select(Quest).where(Quest.title == "Malformed Predecessor"))).scalar_one()
    requirements = (
        (await async_session.execute(select(QuestRequirement).where(QuestRequirement.quest_id == quest.id)))
        .scalars()
        .all()
    )
    assert requirements == []


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
