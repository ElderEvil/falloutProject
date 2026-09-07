"""Tests for game loop exploration integration."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.exploration_event import CombatEventSchema, ItemSchema, LootEventSchema, LootSchema
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service
from app.services.game_loop import game_loop_service
from app.services.stream_manager import sse_manager
from app.tests.factory.dwellers import create_fake_adult_dweller, create_fake_dweller

# Note: Event persistence tested separately


@pytest.mark.asyncio
async def test_process_explorations_error_handling(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that errors in one exploration don't affect others."""
    # Create two explorations
    dweller2_data = create_fake_dweller()
    dweller2_data = create_fake_adult_dweller()
    dweller2_data["vault_id"] = vault.id
    dweller2 = await crud.dweller.create(async_session, DwellerCreate(**dweller2_data))

    exploration1 = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    exploration2 = await exploration_service.send_dweller(async_session, vault.id, dweller2.id, duration=4)

    # Make both ready for events
    exploration1.start_time = datetime.utcnow() - timedelta(minutes=10)
    exploration2.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()

    # Mock to cause error on first, success on second
    call_count = 0

    def side_effect_generator(exp):
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
async def test_vault_tick_processes_explorations(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that vault tick includes exploration processing."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=1)

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
    dweller2_data = create_fake_adult_dweller()
    dweller2_data["vault_id"] = vault.id
    dweller2 = await crud.dweller.create(async_session, DwellerCreate(**dweller2_data))

    exploration1 = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=1)

    exploration2 = await exploration_service.send_dweller(async_session, vault.id, dweller2.id, duration=1)

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

    # Note: Loot collection tested separately


@pytest.mark.asyncio
async def test_process_explorations_danger_event_updates_enemies(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that danger events increment enemy counter."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

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
