"""Tests for wasteland service logic."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.storage import Storage
from app.models.vault import Vault
from app.schemas.exploration_event import (
    CombatEventSchema,
    DangerEventSchema,
    ItemSchema,
    LootEventSchema,
    LootSchema,
    RestEventSchema,
)
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service

# Note: Detailed SPECIAL stat calculation tests removed for simplicity
# These are tested implicitly through integration tests


async def _finish_exploration(async_session: AsyncSession, exploration) -> None:
    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)


@pytest.mark.asyncio
async def test_send_dweller_deducts_vault_supplies_only_once(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Supplies taken from storage must not also be removed from the dweller."""
    dweller.stimpack = 2
    dweller.radaway = 1
    storage = Storage(vault_id=vault.id, stimpack=5, radaway=3)
    async_session.add_all([dweller, storage])
    await async_session.commit()

    exploration = await exploration_service.send_dweller(
        async_session,
        vault.id,
        dweller.id,
        duration=4,
        stimpaks=4,
        radaways=2,
    )

    await async_session.refresh(dweller)
    await async_session.refresh(storage)

    assert exploration.stimpaks == 4
    assert exploration.radaways == 2
    assert storage.stimpack == 1
    assert storage.radaway == 1
    assert dweller.stimpack == 2
    assert dweller.radaway == 1


@pytest.mark.asyncio
async def test_send_dweller_rejects_a_dweller_from_another_vault(
    async_session: AsyncSession,
    dweller: Dweller,
) -> None:
    """The requested vault cannot send a dweller it does not own."""
    from uuid import uuid4

    with pytest.raises(ValueError, match="does not belong to this vault"):
        await exploration_service.send_dweller(async_session, uuid4(), dweller.id, duration=4)


@pytest.mark.asyncio
async def test_generate_event_not_active(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that no event is generated for inactive exploration."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await crud.exploration.complete_exploration(async_session, exploration_id=exploration.id)
    await async_session.refresh(exploration)

    event = exploration_service.generate_event(exploration)
    assert event is None

    # This is probabilistic but timing check should prevent generation
    # We can't assert None because it might have been 5+ minutes in test


@pytest.mark.asyncio
async def test_generate_event_with_loot(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test event generation can produce loot."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

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
    valid_types = ["combat", "loot", "danger", "rest", "discovery"]
    for event in events_generated:
        assert event.type in valid_types
        assert hasattr(event, "description")
        if event.type == "loot":
            assert event.loot is not None
            assert hasattr(event.loot, "item")
            assert hasattr(event.loot, "caps")


@pytest.mark.asyncio
async def test_complete_exploration_transfers_caps(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test completing exploration transfers caps to vault."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

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
    await async_session.refresh(dweller)
    # 65/80 passes the 70% survival check, but 65/100 would not: radiation makes
    # this a guard against reverting the bonus to base max health.
    dweller.max_health = 100
    dweller.health = 65
    dweller.radiation = 20
    async_session.add(dweller)
    await async_session.commit()
    initial_caps = vault.bottle_caps

    # Calculate expected XP BEFORE completion (XP uses pre-level-up dweller state)
    base_xp = (75 * 10) + (10 * 50) + (0 * 20)  # distance*10 + enemies*50 + events*20
    expected_xp = base_xp

    # Add survival bonus if dweller has >70% health
    if dweller.health / dweller.effective_max_health > 0.7:
        expected_xp += int(base_xp * 0.2)  # 20% survival bonus

    # Add luck bonus (2% per luck point)
    expected_xp += int(base_xp * (exploration.dweller_luck * 0.02))

    # Complete exploration — returns RewardsSchema (Pydantic model)
    await _finish_exploration(async_session, exploration)
    rewards = await exploration_service.complete_exploration(async_session, exploration.id)

    # Verify rewards via attribute access (RewardsSchema is a Pydantic model)
    assert rewards.caps == 150
    assert rewards.distance == 75
    assert rewards.enemies_defeated == 10
    assert rewards.experience == expected_xp
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
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await crud.exploration.complete_exploration(async_session, exploration_id=exploration.id)

    with pytest.raises(ValueError, match="not active"):
        await exploration_service.complete_exploration(async_session, exploration.id)


@pytest.mark.asyncio
async def test_complete_exploration_before_duration_raises_error(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """Full completion is unavailable until the expedition duration has elapsed."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    with pytest.raises(ValueError, match="has not finished yet"):
        await exploration_service.complete_exploration(async_session, exploration.id)


@pytest.mark.asyncio
async def test_recall_exploration_reduced_rewards(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test recalling exploration gives reduced experience based on progress."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

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
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await crud.exploration.recall_exploration(async_session, exploration_id=exploration.id)

    with pytest.raises(ValueError, match="not active"):
        await exploration_service.recall_exploration(async_session, exploration.id)

    # Note: Event collection tested separately


@pytest.mark.asyncio
async def test_process_danger_radiation_applies_to_dweller(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """A radiation danger event raises dweller.radiation and logs it on the journey."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()
    await async_session.refresh(exploration)
    await async_session.refresh(dweller)
    initial_radiation = dweller.radiation

    mock_event = DangerEventSchema(
        description="Caught in unexpected radiation burst. Took 11 rads.",
        health_loss=0,
        radiation_gain=11,
    )

    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await exploration_service.process_event(async_session, exploration)

    await async_session.refresh(dweller)
    assert dweller.radiation == initial_radiation + 11
    assert result.events[-1]["radiation_gain"] == 11


@pytest.mark.asyncio
async def test_rest_event_logs_actual_healing_after_radiation_cap(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
) -> None:
    """A rest heal capped by radiation must log the HP actually restored (PR #534)."""
    dweller.max_health = 100
    dweller.radiation = 50  # effective max 50
    dweller.health = 48  # only 2 HP of headroom
    async_session.add(dweller)
    await async_session.commit()

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()
    await async_session.refresh(exploration)

    mock_event = RestEventSchema(
        description="Rested in a safe location and recovered. Gained 10 HP.",
        health_restored=10,
    )

    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await exploration_service.process_event(async_session, exploration)

    await async_session.refresh(dweller)
    assert dweller.health == 50
    rest_event = next(e for e in result.events if e["type"] == "rest")
    assert rest_event["health_restored"] == 2
    assert "Gained 2 HP" in rest_event["description"]


@pytest.mark.parametrize(
    ("heal_percent", "expected_health", "expected_healing"),
    [(0.4, 50, 30), (0.001, 21, 1)],
)
@pytest.mark.asyncio
async def test_auto_stimpak_logs_actual_healing_after_radiation_cap(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    monkeypatch: pytest.MonkeyPatch,
    heal_percent: float,
    expected_health: int,
    expected_healing: int,
) -> None:
    """A Stimpak heal capped by radiation must log the HP actually restored (PR #534)."""
    monkeypatch.setattr(game_config.health, "stimpack_heal_percent", heal_percent)
    dweller.max_health = 100
    dweller.radiation = 50  # effective max 50
    dweller.health = 20  # below the 50% auto-heal threshold
    async_session.add(dweller)
    await async_session.commit()

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    exploration.stimpaks = 1
    await async_session.commit()
    await async_session.refresh(exploration)

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

    await async_session.refresh(dweller)
    assert dweller.health == expected_health
    assert result.stimpaks == 0
    item_use = next(e for e in result.events if e["type"] == "item_use")
    assert item_use["health_restored"] == expected_healing
    assert f"Healed {expected_healing} HP" in item_use["description"]
