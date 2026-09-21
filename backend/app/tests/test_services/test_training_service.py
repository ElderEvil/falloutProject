"""Tests for training service logic."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud import training as training_crud
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


# =============================================================================
# Single-transaction contract (AUDIT.md: one commit per state transition)
# =============================================================================


def _training_room(vault_id) -> RoomCreate:
    """A tier-1 STRENGTH training room."""
    return RoomCreate(
        name="Weight Room",
        category=RoomTypeEnum.TRAINING,
        tier=1,
        size=2,
        capacity=6,
        ability=SPECIALEnum.STRENGTH,
        base_cost=1000,
        t2_upgrade_cost=2500,
        t3_upgrade_cost=5000,
        size_min=1,
        size_max=3,
        vault_id=vault_id,
    )


async def _idle_dweller(async_session: AsyncSession, dweller: Dweller) -> None:
    dweller.status = DwellerStatusEnum.IDLE
    dweller.strength = 5
    async_session.add(dweller)
    await async_session.commit()


@pytest.mark.asyncio
async def test_start_training_commits_once(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """The training row and the dweller assignment land in ONE commit, not two."""
    room = await room_crud.create(async_session, _training_room(vault.id))
    await _idle_dweller(async_session, dweller)

    original_commit = async_session.commit
    commits: list[int] = []

    async def counting_commit(*args, **kwargs):
        commits.append(1)
        return await original_commit(*args, **kwargs)

    with patch.object(async_session, "commit", new=counting_commit):
        training = await training_service.start_training(async_session, dweller.id, room.id)

    assert len(commits) == 1
    assert training.is_active()


@pytest.mark.asyncio
async def test_start_training_leaves_no_partial_state_when_the_second_write_fails(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """A failure between the two writes must not persist a training row without the assignment.

    Before the fix the training row was committed on its own first, so it survived
    the later failure; now nothing is committed until both writes are staged.
    """
    room = await room_crud.create(async_session, _training_room(vault.id))
    await _idle_dweller(async_session, dweller)
    vault_id = vault.id

    with (
        patch(
            "app.services.training_service.dweller_crud.update",
            new=AsyncMock(side_effect=RuntimeError("dweller update failed")),
        ),
        pytest.raises(RuntimeError),
    ):
        await training_service.start_training(async_session, dweller.id, room.id)

    await async_session.rollback()

    assert await training_crud.training.get_active_by_vault(async_session, vault_id) == []
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.IDLE


@pytest.mark.asyncio
async def test_complete_training_persists_stat_and_release_in_the_first_commit(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """The stat gain and the dweller release are both durable after the FIRST commit."""
    room = await room_crud.create(async_session, _training_room(vault.id))
    await _idle_dweller(async_session, dweller)
    training = await training_service.start_training(async_session, dweller.id, room.id)

    original_commit = async_session.commit
    observations: list[str] = []

    async def first_commit(*args, **kwargs):
        result = await original_commit(*args, **kwargs)
        if not observations:
            observations.append("first")
            await async_session.refresh(training)
            await async_session.refresh(dweller)
            assert training.is_completed()
            assert dweller.status == DwellerStatusEnum.IDLE
        return result

    with patch.object(async_session, "commit", new=first_commit):
        completed = await training_service.complete_training(async_session, training.id)

    assert observations == ["first"]
    assert completed.is_completed()


@pytest.mark.asyncio
async def test_cancel_training_persists_status_and_release_in_the_first_commit(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """The cancelled session and the dweller release are both durable after the FIRST commit."""
    room = await room_crud.create(async_session, _training_room(vault.id))
    await _idle_dweller(async_session, dweller)
    training = await training_service.start_training(async_session, dweller.id, room.id)

    original_commit = async_session.commit
    observations: list[str] = []

    async def first_commit(*args, **kwargs):
        result = await original_commit(*args, **kwargs)
        if not observations:
            observations.append("first")
            await async_session.refresh(training)
            await async_session.refresh(dweller)
            assert training.is_cancelled()
            assert dweller.status == DwellerStatusEnum.IDLE
        return result

    with patch.object(async_session, "commit", new=first_commit):
        cancelled = await training_service.cancel_training(async_session, training.id)

    assert observations == ["first"]
    assert cancelled.is_cancelled()
