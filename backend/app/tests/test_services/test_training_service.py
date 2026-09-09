"""Tests for training service logic."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud.room import room as room_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate
from app.services.training_service import TrainingService


@pytest.fixture
def training_service():
    """Get training service instance."""
    return TrainingService()


@pytest.mark.asyncio
async def test_can_start_training_not_training_room(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """Test cannot start training in non-training room."""
    # Create a production room
    room_data = {
        "name": "Power Generator",
        "category": RoomTypeEnum.PRODUCTION,
        "tier": 1,
        "size": 2,
        "capacity": 6,
        "ability": None,
        "base_cost": 1000,
        "t2_upgrade_cost": 2500,
        "t3_upgrade_cost": 5000,
        "size_min": 1,
        "size_max": 3,
    }
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await room_crud.create(async_session, room_in)

    can_train, reason = await training_service.can_start_training(async_session, dweller, room)

    assert can_train is False
    assert "not a training room" in reason.lower()


@pytest.mark.asyncio
async def test_can_start_training_stat_maxed(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """Test cannot start training when stat is already maxed."""
    # Create a training room
    room_data = {
        "name": "Weight Room",
        "category": RoomTypeEnum.TRAINING,
        "tier": 1,
        "size": 2,
        "capacity": 6,
        "ability": SPECIALEnum.STRENGTH,
        "base_cost": 1000,
        "t2_upgrade_cost": 2500,
        "t3_upgrade_cost": 5000,
        "size_min": 1,
        "size_max": 3,
    }
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await room_crud.create(async_session, room_in)

    # Max out dweller's strength
    dweller.status = DwellerStatusEnum.IDLE
    dweller.strength = game_config.training.special_stat_max
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)

    can_train, reason = await training_service.can_start_training(async_session, dweller, room)

    assert can_train is False
    assert "already at maximum" in reason.lower()


@pytest.mark.asyncio
async def test_can_start_training_dweller_not_idle(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """Test cannot start training when dweller is not idle."""
    # Create a training room
    room_data = {
        "name": "Weight Room",
        "category": RoomTypeEnum.TRAINING,
        "tier": 1,
        "size": 2,
        "capacity": 6,
        "ability": SPECIALEnum.STRENGTH,
        "base_cost": 1000,
        "t2_upgrade_cost": 2500,
        "t3_upgrade_cost": 5000,
        "size_min": 1,
        "size_max": 3,
    }
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await room_crud.create(async_session, room_in)

    # Set dweller to EXPLORING
    dweller.status = DwellerStatusEnum.EXPLORING
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)

    can_train, reason = await training_service.can_start_training(async_session, dweller, room)

    assert can_train is False
    assert "exploring" in reason.lower()


@pytest.mark.asyncio
async def test_complete_training(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """Test completing a training session increases stat."""
    # Create a training room
    room_data = {
        "name": "Weight Room",
        "category": RoomTypeEnum.TRAINING,
        "tier": 1,
        "size": 2,
        "capacity": 6,
        "ability": SPECIALEnum.STRENGTH,
        "base_cost": 1000,
        "t2_upgrade_cost": 2500,
        "t3_upgrade_cost": 5000,
        "size_min": 1,
        "size_max": 3,
    }
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await room_crud.create(async_session, room_in)

    # Set dweller to IDLE and reasonable strength
    dweller.status = DwellerStatusEnum.IDLE
    initial_strength = 5
    dweller.strength = initial_strength
    async_session.add(dweller)
    await async_session.commit()

    # Start training
    training = await training_service.start_training(async_session, dweller.id, room.id)

    # Complete training
    completed_training = await training_service.complete_training(async_session, training.id)

    assert completed_training.is_completed()
    assert completed_training.progress == 1.0
    assert completed_training.completed_at is not None

    # Verify dweller's strength increased
    await async_session.refresh(dweller)
    assert dweller.strength == initial_strength + 1
    assert dweller.status == DwellerStatusEnum.IDLE


@pytest.mark.asyncio
async def test_cancel_training(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """Test cancelling a training session does not increase stat."""
    # Create a training room
    room_data = {
        "name": "Weight Room",
        "category": RoomTypeEnum.TRAINING,
        "tier": 1,
        "size": 2,
        "capacity": 6,
        "ability": SPECIALEnum.STRENGTH,
        "base_cost": 1000,
        "t2_upgrade_cost": 2500,
        "t3_upgrade_cost": 5000,
        "size_min": 1,
        "size_max": 3,
    }
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    room = await room_crud.create(async_session, room_in)

    # Set dweller to IDLE and reasonable strength
    dweller.status = DwellerStatusEnum.IDLE
    initial_strength = 5
    dweller.strength = initial_strength
    async_session.add(dweller)
    await async_session.commit()

    # Start training
    training = await training_service.start_training(async_session, dweller.id, room.id)

    # Cancel training
    cancelled_training = await training_service.cancel_training(async_session, training.id)

    assert cancelled_training.is_cancelled()
    assert cancelled_training.completed_at is not None

    # Verify dweller's strength did NOT increase
    await async_session.refresh(dweller)
    assert dweller.strength == initial_strength
    assert dweller.status == DwellerStatusEnum.IDLE
