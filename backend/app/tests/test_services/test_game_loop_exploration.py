"""Tests for game loop exploration integration."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.exploration_event import CombatEventSchema, ItemSchema, LootEventSchema, LootSchema
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service
from app.services.game_loop import game_loop_service
from app.tests.factory.dwellers import create_fake_dweller


@pytest.mark.asyncio
async def test_process_explorations_empty_vault(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test processing explorations when vault has none."""
    result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["active_count"] == 0
    assert result["events_generated"] == 0
    assert result["completed"] == 0


@pytest.mark.asyncio
async def test_process_explorations_active_exploration(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test processing an active exploration."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Manipulate time to allow event generation
    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()

    # Mock event generation to ensure it happens
    mock_event = {
        "type": "encounter",
        "description": "Found something interesting",
        "loot": None,
    }

    with patch.object(exploration_service, "generate_event", return_value=mock_event):
        result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["active_count"] == 1
    assert result["events_generated"] == 1
    assert result["completed"] == 0
    # Note: Event persistence tested separately


@pytest.mark.asyncio
async def test_process_explorations_auto_complete(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that explorations auto-complete when time expires."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=1,  # 1 hour
    )

    # Add some rewards
    await crud.exploration.update_stats(
        async_session,
        exploration_id=exploration.id,
        caps=50,
        distance=25,
        enemies=3,
    )

    # Set start time to past (more than 1 hour ago)
    exploration.start_time = datetime.utcnow() - timedelta(hours=2)
    await async_session.commit()
    await async_session.refresh(exploration)

    initial_caps = vault.bottle_caps

    # Process explorations
    result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["active_count"] == 1  # Was active when retrieved
    assert result["completed"] == 1
    assert result["events_generated"] == 0  # No events, just completed

    # Verify exploration is completed
    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.COMPLETED
    assert exploration.end_time is not None

    # Verify caps transferred
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 50


@pytest.mark.asyncio
async def test_process_explorations_multiple_active(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test processing multiple active explorations in one tick."""
    # Create multiple dwellers and explorations
    dweller2_data = create_fake_dweller()
    dweller2_data["vault_id"] = vault.id
    dweller2 = await crud.dweller.create(async_session, DwellerCreate(**dweller2_data))

    dweller3_data = create_fake_dweller()
    dweller3_data["vault_id"] = vault.id
    dweller3 = await crud.dweller.create(async_session, DwellerCreate(**dweller3_data))  # noqa: F841

    # Create explorations
    exploration1 = await crud.exploration.create_with_dweller_stats(  # noqa: F841
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    exploration2 = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller2.id,
        duration=2,
    )

    # Make one ready to complete
    exploration2.start_time = datetime.utcnow() - timedelta(hours=3)
    await async_session.commit()

    # Process explorations
    result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["active_count"] == 2
    # One should be completed, one might have event generated
    assert result["completed"] == 1

    # Verify exploration2 is completed
    await async_session.refresh(exploration2)
    assert exploration2.status == ExplorationStatus.COMPLETED


@pytest.mark.asyncio
async def test_process_explorations_error_handling(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that errors in one exploration don't affect others."""
    # Create two explorations
    dweller2_data = create_fake_dweller()
    dweller2_data["vault_id"] = vault.id
    dweller2 = await crud.dweller.create(async_session, DwellerCreate(**dweller2_data))

    exploration1 = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    exploration2 = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller2.id,
        duration=4,
    )

    # Make both ready for events
    exploration1.start_time = datetime.utcnow() - timedelta(minutes=10)
    exploration2.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()

    # Mock to cause error on first, success on second
    call_count = 0

    def side_effect_generator(exp):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Test error")
        return {
            "type": "encounter",
            "description": "Safe event",
            "loot": None,
        }

    with patch.object(exploration_service, "generate_event", side_effect=side_effect_generator):
        # Should not raise, just log errors
        result = await game_loop_service._process_explorations(async_session, vault.id)

    # Process should continue despite error
    assert result["active_count"] == 2


@pytest.mark.asyncio
async def test_process_explorations_no_event_when_not_ready(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that events are not generated when cooldown not met."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add an event very recently
    await crud.exploration.add_event(
        async_session,
        exploration_id=exploration.id,
        event_type="encounter",
        description="Recent event",
        loot=None,
    )

    # Process immediately after (cooldown not met)
    result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["active_count"] == 1
    assert result["events_generated"] == 0  # No new events due to cooldown


@pytest.mark.asyncio
async def test_vault_tick_processes_explorations(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that vault tick includes exploration processing."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=1,
    )

    # Set to expire
    exploration.start_time = datetime.utcnow() - timedelta(hours=2)
    await async_session.commit()

    # Process full vault tick
    result = await game_loop_service.process_vault_tick(async_session, vault.id)

    assert "explorations" in result["updates"]
    assert result["updates"]["explorations"]["completed"] == 1


@pytest.mark.asyncio
async def test_process_explorations_caps_accumulate(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that caps from multiple completed explorations accumulate."""
    # Create two explorations
    dweller2_data = create_fake_dweller()
    dweller2_data["vault_id"] = vault.id
    dweller2 = await crud.dweller.create(async_session, DwellerCreate(**dweller2_data))

    exploration1 = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=1,
    )

    exploration2 = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller2.id,
        duration=1,
    )

    # Add caps to both
    await crud.exploration.update_stats(
        async_session,
        exploration_id=exploration1.id,
        caps=100,
    )

    await crud.exploration.update_stats(
        async_session,
        exploration_id=exploration2.id,
        caps=150,
    )

    # Make both expire
    exploration1.start_time = datetime.utcnow() - timedelta(hours=2)
    exploration2.start_time = datetime.utcnow() - timedelta(hours=2)
    await async_session.commit()

    initial_caps = vault.bottle_caps

    # Process explorations
    result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["completed"] == 2

    # Verify total caps transferred
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 250  # 100 + 150


@pytest.mark.asyncio
async def test_process_explorations_event_with_loot_updates_stats(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that loot events update exploration stats correctly."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Manipulate time for event generation
    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()

    # Mock loot event
    mock_event = LootEventSchema(
        description="Found treasure!",
        loot=LootSchema(
            item=ItemSchema(name="Duct Tape", rarity="Rare", value=20),
            item_type="junk",
            caps=75,
        ),
    )

    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["events_generated"] == 1

    # Verify stats updated
    await async_session.refresh(exploration)
    assert exploration.total_caps_found == 75
    assert exploration.total_distance > 0  # Some distance added
    # Note: Loot collection tested separately


@pytest.mark.asyncio
async def test_process_explorations_danger_event_updates_enemies(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that danger events increment enemy counter."""
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()

    # Mock combat event (combat events increment enemy counter)
    mock_event = CombatEventSchema(
        description="Attacked by raiders!",
        health_loss=10,
        enemy="Raider gang",
        victory=True,
    )

    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await game_loop_service._process_explorations(async_session, vault.id)

    assert result["events_generated"] == 1

    # Verify enemy count updated
    await async_session.refresh(exploration)
    assert exploration.enemies_encountered == 1
