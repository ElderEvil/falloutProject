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
    ExpeditionEvaluator,
    LevelUpEvaluator,
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
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
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
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
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
async def test_build_evaluator_room_built(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
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
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
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
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
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
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
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
async def test_evaluator_already_completed(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
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


@pytest.mark.asyncio
async def test_collect_evaluator_item_collected_weapon(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test CollectEvaluator updates progress on weapon collection."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective
    objective = Objective(
        challenge="Collect 3 weapons",
        reward="300 caps",
        objective_type="collect",
        target_entity={"item_type": "weapon"},
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
    CollectEvaluator(fresh_event_bus)

    # Emit item collected event for weapon
    await fresh_event_bus.emit(GameEvent.ITEM_COLLECTED, vault.id, {"item_type": "weapon", "amount": 1})

    # Refresh and check progress
    await async_session.refresh(link)
    assert link.progress == 1


@pytest.mark.asyncio
async def test_collect_evaluator_item_collected_outfit(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test CollectEvaluator updates progress on outfit collection."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective
    objective = Objective(
        challenge="Collect 3 outfits",
        reward="300 caps",
        objective_type="collect",
        target_entity={"item_type": "outfit"},
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
    CollectEvaluator(fresh_event_bus)

    # Emit item collected event for outfit
    await fresh_event_bus.emit(GameEvent.ITEM_COLLECTED, vault.id, {"item_type": "outfit", "amount": 1})

    # Refresh and check progress
    await async_session.refresh(link)
    assert link.progress == 1


@pytest.mark.asyncio
async def test_collect_evaluator_item_collected_stimpak(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test CollectEvaluator updates progress on stimpak collection."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective
    objective = Objective(
        challenge="Collect 5 stimpaks",
        reward="250 caps",
        objective_type="collect",
        target_entity={"item_type": "stimpak"},
        target_amount=5,
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
    CollectEvaluator(fresh_event_bus)

    # Emit item collected event for stimpak (collecting 2 at once)
    await fresh_event_bus.emit(GameEvent.ITEM_COLLECTED, vault.id, {"item_type": "stimpak", "amount": 2})

    # Refresh and check progress
    await async_session.refresh(link)
    assert link.progress == 2


@pytest.mark.asyncio
async def test_collect_evaluator_item_wrong_type(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test CollectEvaluator ignores wrong item type."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    # Create objective for weapons only
    objective = Objective(
        challenge="Collect 3 weapons",
        reward="300 caps",
        objective_type="collect",
        target_entity={"item_type": "weapon"},
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
    CollectEvaluator(fresh_event_bus)

    # Emit item collected event for outfit (should not count)
    await fresh_event_bus.emit(GameEvent.ITEM_COLLECTED, vault.id, {"item_type": "outfit", "amount": 1})

    # Refresh and check progress unchanged
    await async_session.refresh(link)
    assert link.progress == 0


class TestAliasMatching:
    """Tests for evaluator alias matching functionality."""

    def test_build_evaluator_matches_room_alias(self, fresh_event_bus):
        """Test BuildEvaluator matches room aliases like 'living quarters' -> 'living_room'."""
        evaluator = BuildEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Build a Living Room",
            reward="100 caps",
            objective_type="build",
            target_entity={"room_type": "living_room"},
            target_amount=1,
        )
        # Event uses alias "Living Quarters"
        data = {"room_type": "Living Quarters"}
        assert evaluator._matches(objective, GameEvent.ROOM_BUILT, data) is True

    def test_build_evaluator_matches_power_plant_alias(self, fresh_event_bus):
        """Test BuildEvaluator matches 'Power Plant' -> 'power_generator'."""
        evaluator = BuildEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Build a Power Generator",
            reward="100 caps",
            objective_type="build",
            target_entity={"room_type": "power_generator"},
            target_amount=1,
        )
        # Event uses alias "Power Plant"
        data = {"room_type": "Power Plant"}
        assert evaluator._matches(objective, GameEvent.ROOM_BUILT, data) is True

    def test_collect_evaluator_matches_resource_alias_caps(self, fresh_event_bus):
        """Test CollectEvaluator matches 'Caps' -> 'caps'."""
        evaluator = CollectEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Collect 100 caps",
            reward="50 caps",
            objective_type="collect",
            target_entity={"resource_type": "caps"},
            target_amount=100,
        )
        # Event uses capitalized "Caps"
        data = {"resource_type": "Caps"}
        assert evaluator._matches(objective, GameEvent.RESOURCE_COLLECTED, data) is True

    def test_collect_evaluator_matches_item_alias_weapons(self, fresh_event_bus):
        """Test CollectEvaluator matches 'Weapons' -> 'weapon'."""
        evaluator = CollectEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Collect 3 weapons",
            reward="100 caps",
            objective_type="collect",
            target_entity={"item_type": "weapon"},
            target_amount=3,
        )
        # Event uses plural "Weapons"
        data = {"item_type": "Weapons"}
        assert evaluator._matches(objective, GameEvent.ITEM_COLLECTED, data) is True

    def test_collect_evaluator_matches_item_alias_outfits(self, fresh_event_bus):
        """Test CollectEvaluator matches 'Outfits' -> 'outfit'."""
        evaluator = CollectEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Collect 3 outfits",
            reward="100 caps",
            objective_type="collect",
            target_entity={"item_type": "outfit"},
            target_amount=3,
        )
        # Event uses plural "Outfits"
        data = {"item_type": "Outfits"}
        assert evaluator._matches(objective, GameEvent.ITEM_COLLECTED, data) is True

    def test_assign_evaluator_matches_room_alias(self, fresh_event_bus):
        """Test AssignEvaluator matches room aliases."""
        evaluator = AssignEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Assign to Living Room",
            reward="50 caps",
            objective_type="assign",
            target_entity={"room_type": "living_room"},
            target_amount=1,
        )
        # Event uses alias "Living Quarters"
        data = {"room_type": "Living Quarters"}
        assert evaluator._matches(objective, GameEvent.DWELLER_ASSIGNED, data) is True

    def test_assign_evaluator_optional_room_type(self, fresh_event_bus):
        """Test AssignEvaluator matches when no room_type specified (any assignment)."""
        evaluator = AssignEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Assign 5 dwellers",
            reward="100 caps",
            objective_type="assign",
            target_entity={},
            target_amount=5,
        )
        data = {"room_type": "power_generator"}
        assert evaluator._matches(objective, GameEvent.DWELLER_ASSIGNED, data) is True


class TestExpeditionEvaluator:
    """Tests for ExpeditionEvaluator functionality."""

    def test_matches_any_quest_type(self, fresh_event_bus):
        """Test ExpeditionEvaluator matches any quest when no quest_type specified."""
        evaluator = ExpeditionEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Complete 3 Expeditions",
            reward="800 caps",
            objective_type="expedition",
            target_entity={},
            target_amount=3,
        )
        data = {"quest_type": "main"}
        assert evaluator._matches(objective, GameEvent.QUEST_COMPLETED, data) is True

    def test_matches_specific_quest_type(self, fresh_event_bus):
        """Test ExpeditionEvaluator matches specific quest type."""
        evaluator = ExpeditionEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Complete 1 Main Quest",
            reward="2000 caps",
            objective_type="expedition",
            target_entity={"quest_type": "main"},
            target_amount=1,
        )
        data = {"quest_type": "main"}
        assert evaluator._matches(objective, GameEvent.QUEST_COMPLETED, data) is True

    def test_does_not_match_wrong_quest_type(self, fresh_event_bus):
        """Test ExpeditionEvaluator does not match wrong quest type."""
        evaluator = ExpeditionEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Complete 1 Main Quest",
            reward="2000 caps",
            objective_type="expedition",
            target_entity={"quest_type": "main"},
            target_amount=1,
        )
        data = {"quest_type": "side"}
        assert evaluator._matches(objective, GameEvent.QUEST_COMPLETED, data) is False

    def test_matches_wildcard_quest_type(self, fresh_event_bus):
        """Test ExpeditionEvaluator matches wildcard quest type."""
        evaluator = ExpeditionEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Complete 3 Expeditions",
            reward="800 caps",
            objective_type="expedition",
            target_entity={"quest_type": "*"},
            target_amount=3,
        )
        data = {"quest_type": "daily"}
        assert evaluator._matches(objective, GameEvent.QUEST_COMPLETED, data) is True


class TestLevelUpEvaluator:
    """Tests for LevelUpEvaluator functionality."""

    def test_matches_min_level_met(self, fresh_event_bus):
        """Test LevelUpEvaluator matches when min_level is met."""
        evaluator = LevelUpEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Level up 2 Dwellers to Lv.5",
            reward="1000 caps",
            objective_type="level_up",
            target_entity={"min_level": 5},
            target_amount=2,
        )
        data = {"new_level": 5}
        assert evaluator._matches(objective, GameEvent.DWELLER_LEVEL_UP, data) is True

    def test_matches_exceeds_min_level(self, fresh_event_bus):
        """Test LevelUpEvaluator matches when level exceeds min_level."""
        evaluator = LevelUpEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Level up 2 Dwellers to Lv.5",
            reward="1000 caps",
            objective_type="level_up",
            target_entity={"min_level": 5},
            target_amount=2,
        )
        data = {"new_level": 10}
        assert evaluator._matches(objective, GameEvent.DWELLER_LEVEL_UP, data) is True

    def test_does_not_match_below_min_level(self, fresh_event_bus):
        """Test LevelUpEvaluator does not match when below min_level."""
        evaluator = LevelUpEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Level up 2 Dwellers to Lv.5",
            reward="1000 caps",
            objective_type="level_up",
            target_entity={"min_level": 5},
            target_amount=2,
        )
        data = {"new_level": 4}
        assert evaluator._matches(objective, GameEvent.DWELLER_LEVEL_UP, data) is False

    def test_matches_no_min_level_requirement(self, fresh_event_bus):
        """Test LevelUpEvaluator matches any level when no min_level specified."""
        evaluator = LevelUpEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Level up a Dweller",
            reward="500 caps",
            objective_type="level_up",
            target_entity={},
            target_amount=1,
        )
        data = {"new_level": 2}
        assert evaluator._matches(objective, GameEvent.DWELLER_LEVEL_UP, data) is True
