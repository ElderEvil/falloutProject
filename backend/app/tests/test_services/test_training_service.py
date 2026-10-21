"""Tests for training service logic."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud import training as training_crud
from app.crud.room import room as room_crud
from app.models.dweller import Dweller
from app.models.pet import Pet
from app.models.vault import Vault
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate
from app.services.training_service import TrainingService
from app.utils.exceptions import VaultOperationException


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


@pytest.fixture
async def continuous_trainee(async_session, vault, dweller, training_service):
    """A real, assigned trainee in a vault that opted into repeat training."""
    vault.continuous_training = True
    dweller.age_group = "adult"
    dweller.health = 100
    async_session.add(vault)
    await _idle_dweller(async_session, dweller)
    room = await room_crud.create(async_session, _training_room(vault.id))
    training = await training_service.start_training(async_session, dweller.id, room.id)
    return training, room


async def test_continuous_training_starts_next_round_atomically(
    async_session, vault, dweller, training_service, continuous_trainee
):
    from datetime import datetime, timedelta

    training, room = continuous_trainee
    training.estimated_completion_at = datetime.utcnow() - timedelta(seconds=1)
    async_session.add(training)
    await async_session.commit()
    original_commit = async_session.commit
    observations = []

    async def observe_first_commit():
        await original_commit()
        if not observations:
            observations.append(True)
            persisted_next = await training_crud.training.get_active_by_dweller(async_session, dweller.id)
            assert persisted_next is not None
            assert persisted_next.target_stat_value == 7
            await async_session.refresh(dweller)
            assert dweller.strength == 6
            assert dweller.status == DwellerStatusEnum.TRAINING

    with patch.object(async_session, "commit", new=observe_first_commit):
        completed = await training_service.update_training_progress(async_session, training)
    assert observations == [True]
    next_round = await training_crud.training.get_active_by_dweller(async_session, dweller.id)
    await async_session.refresh(dweller)
    assert completed.is_completed()
    assert dweller.strength == 6
    assert dweller.status == DwellerStatusEnum.TRAINING
    assert dweller.room_id == room.id
    assert next_round is not None
    assert next_round.id != completed.id
    assert (next_round.current_stat_value, next_round.target_stat_value) == (6, 7)
    assert (next_round.estimated_completion_at - next_round.started_at).total_seconds() == (
        training_service.calculate_training_duration(6, room.tier)
    )
    with pytest.raises(VaultOperationException):
        await training_service.complete_training(async_session, completed.id)
    await async_session.refresh(dweller)
    assert dweller.strength == 6
    assert len(await training_crud.training.get_active_by_room(async_session, room.id)) == 1


async def test_continuous_training_stops_at_ten(async_session, dweller, training_service, continuous_trainee):
    training, _ = continuous_trainee
    while dweller.strength < 10:
        await training_service.complete_training(async_session, training.id)
        await async_session.refresh(dweller)
        training = await training_crud.training.get_active_by_dweller(async_session, dweller.id)
        if dweller.strength < 10:
            assert training is not None
    assert training is None
    assert dweller.strength == 10
    assert dweller.status == DwellerStatusEnum.IDLE
    assert dweller.room_id is None


@pytest.mark.parametrize("action", ["disable", "cancel", "reassign", "death"])
async def test_continuous_training_can_be_stopped(
    async_session, vault, dweller, training_service, continuous_trainee, action
):
    training, _ = continuous_trainee
    if action == "disable":
        from app.crud.vault import vault as vault_crud
        from app.schemas.vault import VaultUpdate

        await vault_crud.update(async_session, vault.id, VaultUpdate(continuous_training=False))
    elif action == "reassign":
        dweller.room_id = None
        dweller.status = DwellerStatusEnum.IDLE
    elif action == "death":
        dweller.health = 0
        dweller.status = DwellerStatusEnum.DEAD
    async_session.add(dweller)
    await async_session.commit()
    if action == "cancel":
        await training_service.cancel_training(async_session, training.id)
    else:
        await training_service.complete_training(async_session, training.id)
    await async_session.refresh(dweller)
    assert await training_crud.training.get_active_by_dweller(async_session, dweller.id) is None
    assert dweller.strength == (6 if action == "disable" else 5)
    if action == "death":
        assert dweller.status == DwellerStatusEnum.DEAD


async def test_continuous_training_supports_raw_tick_session(
    async_session, db_connection, dweller, training_service, continuous_trainee
):
    from sqlalchemy.ext.asyncio import AsyncSession as RawSession

    training_id = continuous_trainee[0].id
    dweller_id = dweller.id
    async with RawSession(bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as raw:
        assert not hasattr(raw, "exec")
        await training_service.complete_training(raw, training_id)
        next_round = await training_crud.training.get_active_by_dweller(raw, dweller_id)
        assert next_round is not None
        assert next_round.target_stat_value == 7


async def test_continuous_training_uses_current_pet_bonus(async_session, dweller, training_service, continuous_trainee):
    from app import crud

    training, room = continuous_trainee
    pet = await crud.pet.create(async_session, obj_in={"name": "Vault-Tec Parrot", "rarity": "Legendary", "value": 500})
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)
    await training_service.complete_training(async_session, training.id)
    next_round = await training_crud.training.get_active_by_dweller(async_session, dweller.id)
    assert next_round is not None
    assert (next_round.estimated_completion_at - next_round.started_at).total_seconds() == int(
        training_service.calculate_training_duration(6, room.tier) * 0.75
    )


async def test_continuous_training_rolls_back_if_next_round_cannot_persist(
    async_session, dweller, training_service, continuous_trainee
):
    from sqlalchemy import event

    from app.models.training import Training

    training, _ = continuous_trainee

    def fail_successor(_mapper, _connection, target):
        if target.target_stat_value == 7:
            raise RuntimeError("next training write failed")

    event.listen(Training, "before_insert", fail_successor)
    try:
        with pytest.raises(RuntimeError, match="next training write failed"):
            await training_service.complete_training(async_session, training.id)
    finally:
        event.remove(Training, "before_insert", fail_successor)
        await async_session.rollback()
    await async_session.refresh(training)
    await async_session.refresh(dweller)
    assert training.is_active()
    assert dweller.strength == 5
    assert dweller.status == DwellerStatusEnum.TRAINING


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
async def test_start_training_duration_reduced_by_pet_training_speed_bonus(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """An equipped training-speed pet shortens the snapshotted duration."""
    room = await room_crud.create(async_session, _training_room(vault.id))
    await _idle_dweller(async_session, dweller)

    # Simulate the B7 eager-load: the pet sits in the dweller's __dict__.
    # refresh() is no-op'd so it does not wipe the untracked __dict__ entry
    # (a real selectinload pet survives refresh by being re-loaded).
    dweller.__dict__["pet"] = Pet(name="Vault-Tec Parrot", rarity="Legendary")

    with (
        patch(
            "app.services.training_service.dweller_crud.get",
            new=AsyncMock(return_value=dweller),
        ),
        patch.object(async_session, "refresh", new=AsyncMock()),
    ):
        training = await training_service.start_training(async_session, dweller.id, room.id)

    base_duration = training_service.calculate_training_duration(5, 1)
    expected = int(base_duration * (1 - 0.25))
    actual = (training.estimated_completion_at - training.started_at).total_seconds()
    assert actual == expected
    assert actual < base_duration


@pytest.mark.asyncio
async def test_start_training_duration_reduced_by_pet_real_path(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """A pet equipped via crud.pet.equip shortens the duration through the real path.

    start_training reads the dweller via dweller_crud.get, which eager-loads the
    pet (Phase A); no __dict__ hand-set and no mocks, so this proves the B7
    eager-load reaches the training-speed snapshot.
    """
    room = await room_crud.create(async_session, _training_room(vault.id))
    await _idle_dweller(async_session, dweller)

    from app import crud

    pet = await crud.pet.create(
        async_session,
        obj_in={"name": "Vault-Tec Parrot", "rarity": "Legendary", "value": 500},
    )
    await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)

    training = await training_service.start_training(async_session, dweller.id, room.id)

    base_duration = training_service.calculate_training_duration(5, 1)
    expected = int(base_duration * (1 - 0.25))
    actual = (training.estimated_completion_at - training.started_at).total_seconds()
    assert actual == expected
    assert actual < base_duration


@pytest.mark.asyncio
async def test_start_training_duration_unchanged_without_pet(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    training_service: TrainingService,
):
    """Without an equipped pet the duration is the plain calculated duration."""
    room = await room_crud.create(async_session, _training_room(vault.id))
    await _idle_dweller(async_session, dweller)

    training = await training_service.start_training(async_session, dweller.id, room.id)

    expected = training_service.calculate_training_duration(5, 1)
    actual = (training.estimated_completion_at - training.started_at).total_seconds()
    assert actual == expected


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


@pytest.mark.asyncio
@pytest.mark.parametrize("age_group", ["child", "teen"])
async def test_youth_cannot_start_training(async_session, vault, dweller, training_service, age_group):
    from app.core.enums import AgeGroupEnum
    from app.utils.exceptions import VaultOperationException

    dweller.age_group = AgeGroupEnum(age_group)
    async_session.add(dweller)
    room = await room_crud.create(
        async_session,
        RoomCreate(
            name="Weight Room",
            category=RoomTypeEnum.TRAINING,
            ability=SPECIALEnum.STRENGTH,
            tier=1,
            size=1,
            capacity=2,
            base_cost=1000,
            t2_upgrade_cost=2500,
            t3_upgrade_cost=5000,
            size_min=1,
            size_max=3,
            vault_id=vault.id,
        ),
    )
    with pytest.raises(VaultOperationException, match="adult"):
        await training_service.start_training(async_session, dweller.id, room.id)
    assert await training_crud.training.get_active_by_dweller(async_session, dweller.id) is None


async def test_individual_goal_survives_rounds_and_stops_at_goal(
    async_session, dweller, training_service, continuous_trainee
):
    training, _ = continuous_trainee
    original_end = training.estimated_completion_at
    saved = await training_service.set_training_goal(async_session, training.id, 7)
    assert saved.goal_stat_value == 7
    assert saved.estimated_completion_at == original_end
    await training_service.complete_training(async_session, training.id)
    successor = await training_crud.training.get_active_by_dweller(async_session, dweller.id)
    assert successor.goal_stat_value == 7
    assert successor.target_stat_value == 7
    await training_service.complete_training(async_session, successor.id)
    await async_session.refresh(dweller)
    assert dweller.strength == 7
    assert dweller.status == DwellerStatusEnum.IDLE
    assert await training_crud.training.get_active_by_dweller(async_session, dweller.id) is None


async def test_lowering_goal_to_next_gain_finishes_current_round(
    async_session, dweller, training_service, continuous_trainee
):
    training, _ = continuous_trainee
    await training_service.set_training_goal(async_session, training.id, 6)
    await training_service.complete_training(async_session, training.id)
    assert await training_crud.training.get_active_by_dweller(async_session, dweller.id) is None
    await async_session.refresh(dweller)
    assert dweller.strength == 6


@pytest.mark.parametrize("goal", [0, 5, 11])
async def test_invalid_goal_does_not_change_session(async_session, training_service, continuous_trainee, goal):
    from app.utils.exceptions import VaultOperationException

    training, _ = continuous_trainee
    with pytest.raises(VaultOperationException, match="goal"):
        await training_service.set_training_goal(async_session, training.id, goal)
    await async_session.refresh(training)
    assert training.goal_stat_value == 10


async def test_finished_session_goal_cannot_be_changed(async_session, training_service, continuous_trainee):
    from app.utils.exceptions import VaultOperationException

    training, _ = continuous_trainee
    await training_service.complete_training(async_session, training.id)
    with pytest.raises(VaultOperationException, match="cannot"):
        await training_service.set_training_goal(async_session, training.id, 7)


async def test_roomless_training_cancels_without_stat_gain(
    async_session, dweller, training_service, continuous_trainee
):
    """A room removed outside the service cannot leave a payable training round behind."""
    training, _ = continuous_trainee
    training.room_id = None
    dweller.room_id = None
    async_session.add_all([training, dweller])
    await async_session.commit()
    result = await training_service.complete_training(async_session, training.id)
    await async_session.refresh(dweller)
    assert result.is_cancelled()
    assert dweller.strength == 5
    assert dweller.status == DwellerStatusEnum.IDLE


async def test_failed_demolition_rolls_back_training_cancellation(
    async_session, dweller, training_service, continuous_trainee
):
    from sqlalchemy import event

    from app.models.room import Room
    from app.services.room_service import room_service

    training, room = continuous_trainee
    room_id = room.id

    def fail_delete(_mapper, _connection, _target):
        raise RuntimeError("demolition failed")

    event.listen(Room, "before_delete", fail_delete)
    try:
        with pytest.raises(RuntimeError, match="demolition failed"):
            await room_service.destroy_room(async_session, room_id)
    finally:
        event.remove(Room, "before_delete", fail_delete)
        await async_session.rollback()
    await async_session.refresh(training)
    await async_session.refresh(dweller)
    assert training.is_active()
    assert training.room_id == room_id
    assert dweller.room_id == room_id
    assert dweller.status == DwellerStatusEnum.TRAINING
    assert dweller.strength == 5


@pytest.mark.parametrize(
    ("repeat", "goal", "outcome"),
    [(True, 10, "Training continues"), (True, 6, "Goal reached"), (False, 10, "Training complete")],
)
async def test_training_notification_explains_round_outcome(
    async_session, vault, dweller, training_service, continuous_trainee, repeat, goal, outcome
):
    from app.crud.notification import notification as notification_crud
    from app.models.notification import NotificationType

    training, _ = continuous_trainee
    vault.continuous_training = repeat
    async_session.add(vault)
    await async_session.commit()
    await training_service.set_training_goal(async_session, training.id, goal)
    await training_service.complete_training(async_session, training.id)
    notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
    completed = next(item for item in notifications if item.notification_type == NotificationType.TRAINING_COMPLETE)
    assert completed.title == f"{dweller.first_name} {dweller.last_name or ''}".strip() + f" — {outcome}"
    assert completed.message == f"[Vault {vault.number}] Strength +1 (6). {outcome}."
