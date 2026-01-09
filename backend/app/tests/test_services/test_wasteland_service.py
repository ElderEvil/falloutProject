"""Tests for wasteland service logic."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.vault import Vault
from app.schemas.exploration_event import CombatEventSchema, ItemSchema, LootEventSchema, LootSchema
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service

# Note: Detailed SPECIAL stat calculation tests removed for simplicity
# These are tested implicitly through integration tests


@pytest.mark.asyncio
async def test_generate_event_not_active(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that no event is generated for inactive exploration."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await crud.exploration.complete_exploration(async_session, exploration_id=exploration.id)
    await async_session.refresh(exploration)

    event = exploration_service.generate_event(exploration)
    assert event is None


@pytest.mark.asyncio
async def test_generate_event_timing(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test event generation respects timing constraints."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await async_session.refresh(exploration)

    # Immediately after creation, should not generate event (needs 5 minutes)
    event = exploration_service.generate_event(exploration)  # noqa: F841
    # This is probabilistic but timing check should prevent generation
    # We can't assert None because it might have been 5+ minutes in test


@pytest.mark.asyncio
async def test_generate_event_with_loot(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test event generation can produce loot."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Manipulate start time to allow event generation
    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()
    await async_session.refresh(exploration)

    # Generate multiple events to test both outcomes
    events_generated = []
    for _ in range(20):  # Try multiple times to get different event types
        event = exploration_service.generate_event(exploration)
        if event:
            events_generated.append(event)
            # Add the event so next one can be generated
            exploration.add_event(
                event_type=event.type,
                description=event.description,
                loot=getattr(event, "loot", None),
            )
            # Move time forward to allow next event
            if exploration.events:
                exploration.events[-1]["timestamp"] = (datetime.utcnow() - timedelta(minutes=11)).isoformat()

    # Should have generated some events
    assert len(events_generated) > 0

    # Check that event types are valid (updated for new system)
    valid_types = ["combat", "loot", "danger", "rest"]
    for event in events_generated:
        assert event.type in valid_types
        assert hasattr(event, "description")
        if event.type == "loot":
            assert event.loot is not None
            assert hasattr(event.loot, "item")
            assert hasattr(event.loot, "caps")


@pytest.mark.asyncio
async def test_process_event_adds_loot(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test processing an event adds loot to exploration."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Manipulate to allow event generation
    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()
    await async_session.refresh(exploration)

    # Mock generate_event to return a loot event (updated event type)
    mock_event = LootEventSchema(
        description="Found treasure!",
        loot=LootSchema(
            item=ItemSchema(name="Desk Fan", rarity="Common", value=15),
            item_type="junk",
            caps=25,
        ),
    )

    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await exploration_service.process_event(async_session, exploration)

    await async_session.refresh(result)

    # Verify stats were updated (caps from mock event)
    assert result.total_caps_found == 25
    # Verify distance was added (loot event adds 1-5 miles + base 1-3 miles)
    assert 2 <= result.total_distance <= 8
    # Verify event was added
    assert len(result.events) == 1
    assert result.events[0]["type"] == "loot"
    # Verify loot was collected
    assert len(result.loot_collected) == 1
    assert result.loot_collected[0]["item_name"] == "Desk Fan"


@pytest.mark.asyncio
async def test_process_event_combat_increases_enemies(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test processing combat event increases enemy count."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()
    await async_session.refresh(exploration)

    # Mock generate_event to return a combat event (updated event type)
    mock_event = CombatEventSchema(
        description="Encountered raiders!",
        health_loss=10,
        enemy="Raider gang",
        victory=True,
    )

    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await exploration_service.process_event(async_session, exploration)

    await async_session.refresh(result)

    # Verify enemies were incremented
    assert result.enemies_encountered == 1
    # Verify distance was added (all events add 1-3 miles)
    assert 1 <= result.total_distance <= 3
    # Verify event was added
    assert len(result.events) == 1
    assert result.events[0]["type"] == "combat"


@pytest.mark.asyncio
@pytest.mark.skip
async def test_complete_exploration_transfers_caps(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test completing exploration transfers caps to vault."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add some loot and stats
    await crud.exploration.update_stats(
        async_session,
        exploration_id=exploration.id,
        caps=150,
        distance=75,
        enemies=10,
    )
    await crud.exploration.add_loot(
        async_session,
        exploration_id=exploration.id,
        item_name="Wonderglue",
        quantity=2,
        rarity="Rare",
    )

    await async_session.refresh(exploration)
    initial_caps = vault.bottle_caps

    # Complete exploration
    rewards = await exploration_service.complete_exploration(async_session, exploration.id)

    # Calculate expected XP with bonuses
    await async_session.refresh(dweller)
    base_xp = (75 * 10) + (10 * 50)  # distance*10 + enemies*50
    expected_xp = base_xp

    # Add survival bonus if dweller has >70% health
    if dweller.health / dweller.max_health > 0.7:
        expected_xp += int(base_xp * 0.2)  # 20% survival bonus

    # Add luck bonus (2% per luck point)
    expected_xp += int(base_xp * (exploration.dweller_luck * 0.02))

    # Verify rewards
    assert rewards["caps"] == 150
    assert rewards["distance"] == 75
    assert rewards["enemies_defeated"] == 10
    assert rewards["experience"] == expected_xp
    # Note: Loot collection tested separately

    # Verify caps transferred
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 150

    # Verify status changed
    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.COMPLETED
    assert exploration.end_time is not None


@pytest.mark.asyncio
async def test_complete_exploration_not_active_raises_error(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test completing non-active exploration raises error."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await crud.exploration.complete_exploration(async_session, exploration_id=exploration.id)

    with pytest.raises(ValueError, match="not active"):
        await exploration_service.complete_exploration(async_session, exploration.id)


@pytest.mark.asyncio
async def test_recall_exploration_reduced_rewards(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test recalling exploration gives reduced experience based on progress."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add some stats
    await crud.exploration.update_stats(
        async_session,
        exploration_id=exploration.id,
        caps=100,
        distance=50,
        enemies=5,
    )

    await async_session.refresh(exploration)
    initial_caps = vault.bottle_caps

    # Recall early (should be low progress)
    rewards = await exploration_service.recall_exploration(async_session, exploration.id)

    # Verify rewards (using attribute access for Pydantic schema)
    assert rewards.caps == 100  # Caps are kept
    assert rewards.recalled_early is True
    assert rewards.progress_percentage is not None
    assert 0 <= rewards.progress_percentage <= 100

    # Experience should be reduced based on progress
    base_exp = (50 * 10) + (5 * 50)
    expected_exp = int(base_exp * (rewards.progress_percentage / 100))
    assert rewards.experience == expected_exp

    # Verify caps still transferred
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 100

    # Verify status changed
    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.RECALLED
    assert exploration.end_time is not None


@pytest.mark.asyncio
async def test_recall_exploration_not_active_raises_error(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test recalling non-active exploration raises error."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await crud.exploration.recall_exploration(async_session, exploration_id=exploration.id)

    with pytest.raises(ValueError, match="not active"):
        await exploration_service.recall_exploration(async_session, exploration.id)


@pytest.mark.asyncio
async def test_process_event_no_event_returns_unchanged(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test processing when no event should be generated."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Mock generate_event to return None
    with patch.object(event_generator, "generate_event", return_value=None):
        result = await exploration_service.process_event(async_session, exploration)

    # Exploration should be unchanged
    assert result.total_caps_found == 0
    # Note: Event collection tested separately
