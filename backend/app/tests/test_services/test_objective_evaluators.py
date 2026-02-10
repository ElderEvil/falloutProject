"""Tests for ObjectiveEvaluators."""

from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.event_bus import GameEvent, event_bus
from app.services.objective_evaluators import (
    AssignEvaluator,
    BuildEvaluator,
    CollectEvaluator,
    ReachEvaluator,
    TrainEvaluator,
)
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.fixture
def fresh_event_bus():
    """Clear event bus before each test."""
    event_bus.clear()
    yield event_bus
    event_bus.clear()


@pytest.fixture
def patched_session_maker(async_session):
    """Patch async_session_maker to use test session."""

    class MockSessionMaker:
        async def __aenter__(self):
            return async_session

        async def __aexit__(self, *args):
            pass

    with patch("app.services.objective_evaluators.async_session_maker", MockSessionMaker):
        yield


@pytest.mark.asyncio
async def test_collect_evaluator_resource_collected(
    async_session: AsyncSession, fresh_event_bus, patched_session_maker
) -> None:
    """Test CollectEvaluator updates progress on resource event."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective
    objective = Objective(
        challenge="Collect 100 caps",
        reward="50 caps",
        objective_type="collect",
        target_entity={"resource_type": "caps"},
        target_amount=100,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    # Create progress link
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=100, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    # Create evaluator
    CollectEvaluator(fresh_event_bus)

    # Emit resource collected event
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 50})

    # Refresh and check progress
    await async_session.refresh(link)
    assert link.progress == 50


@pytest.mark.asyncio
async def test_collect_evaluator_wrong_resource(
    async_session: AsyncSession, fresh_event_bus, patched_session_maker
) -> None:
    """Test CollectEvaluator ignores wrong resource type."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective for caps
    objective = Objective(
        challenge="Collect 100 caps",
        reward="50 caps",
        objective_type="collect",
        target_entity={"resource_type": "caps"},
        target_amount=100,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    # Create progress link
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=100, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    # Create evaluator
    CollectEvaluator(fresh_event_bus)

    # Emit wrong resource type event
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "food", "amount": 50})

    # Refresh and check progress unchanged
    await async_session.refresh(link)
    assert link.progress == 0


@pytest.mark.asyncio
async def test_build_evaluator_room_built(async_session: AsyncSession, fresh_event_bus, patched_session_maker) -> None:
    """Test BuildEvaluator updates progress on room built."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective
    objective = Objective(
        challenge="Build 3 rooms",
        reward="100 caps",
        objective_type="build",
        target_entity={"room_type": "*"},
        target_amount=3,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    # Create progress link
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=3, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    # Create evaluator
    BuildEvaluator(fresh_event_bus)

    # Emit room built event
    await fresh_event_bus.emit(
        GameEvent.ROOM_BUILT, vault.id, {"room_type": "Power Generator", "tier": 1, "room_id": "test-id"}
    )

    # Refresh and check progress
    await async_session.refresh(link)
    assert link.progress == 1


@pytest.mark.asyncio
async def test_train_evaluator_dweller_trained(
    async_session: AsyncSession, fresh_event_bus, patched_session_maker
) -> None:
    """Test TrainEvaluator updates progress on training complete."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective
    objective = Objective(
        challenge="Train 5 dwellers", reward="200 caps", objective_type="train", target_entity={}, target_amount=5
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    # Create progress link
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=5, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    # Create evaluator
    TrainEvaluator(fresh_event_bus)

    # Create dweller
    dweller = Dweller(first_name="Test", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)

    # Emit dweller trained event
    await fresh_event_bus.emit(
        GameEvent.DWELLER_TRAINED, vault.id, {"dweller_id": str(dweller.id), "stat_trained": "strength"}
    )

    # Refresh and check progress
    await async_session.refresh(link)
    assert link.progress == 1


@pytest.mark.asyncio
async def test_assign_evaluator_dweller_assigned(
    async_session: AsyncSession, fresh_event_bus, patched_session_maker
) -> None:
    """Test AssignEvaluator updates progress on dweller assignment."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective
    objective = Objective(
        challenge="Assign 3 dwellers", reward="150 caps", objective_type="assign", target_entity={}, target_amount=3
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    # Create progress link
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=3, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    # Create evaluator
    AssignEvaluator(fresh_event_bus)

    # Create dweller
    dweller = Dweller(first_name="Test", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)

    # Emit dweller assigned event
    await fresh_event_bus.emit(
        GameEvent.DWELLER_ASSIGNED, vault.id, {"dweller_id": str(dweller.id), "room_id": "test-room"}
    )

    # Refresh and check progress
    await async_session.refresh(link)
    assert link.progress == 1


@pytest.mark.asyncio
async def test_reach_evaluator_population_reached(
    async_session: AsyncSession, fresh_event_bus, patched_session_maker
) -> None:
    """Test ReachEvaluator completes when population target met."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective
    objective = Objective(
        challenge="Reach 10 dwellers",
        reward="500 caps",
        objective_type="reach",
        target_entity={"reach_type": "dweller_count", "target": 10},
        target_amount=10,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    # Create progress link
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=10, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    # Create evaluator
    ReachEvaluator(fresh_event_bus)

    # Create 10 dwellers
    for i in range(10):
        dweller = Dweller(first_name=f"Test{i}", gender="male", rarity="common", level=1, vault_id=vault.id)
        async_session.add(dweller)
    await async_session.commit()

    # Emit dweller assigned event to trigger check
    await fresh_event_bus.emit(GameEvent.DWELLER_ASSIGNED, vault.id, {"dweller_id": "test", "room_id": "test-room"})

    # Refresh and check completion
    await async_session.refresh(link)
    assert link.is_completed is True


@pytest.mark.asyncio
async def test_evaluator_already_completed(async_session: AsyncSession, fresh_event_bus, patched_session_maker) -> None:
    """Test evaluator does not update already completed objectives."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective
    objective = Objective(
        challenge="Collect 100 caps",
        reward="50 caps",
        objective_type="collect",
        target_entity={"resource_type": "caps"},
        target_amount=100,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    # Create already completed progress link
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=100, total=100, is_completed=True
    )
    async_session.add(link)
    await async_session.commit()

    # Create evaluator
    CollectEvaluator(fresh_event_bus)

    # Emit event
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 50})

    # Progress should remain unchanged
    await async_session.refresh(link)
    assert link.progress == 100
    assert link.is_completed is True
