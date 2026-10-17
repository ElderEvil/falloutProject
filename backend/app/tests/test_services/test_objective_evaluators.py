"""Tests for ObjectiveEvaluators."""

import asyncio
import logging
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import crud
from app.core.event_bus import GameEvent, event_bus
from app.crud.storage import storage as storage_crud
from app.models.dweller import Dweller
from app.models.objective import Objective
from app.models.storage import Storage
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.common import ObjectiveCategoryEnum
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.progression.objectives.evaluators import (
    AssignEvaluator,
    BuildEvaluator,
    CollectEvaluator,
    ExpeditionEvaluator,
    ExploreEvaluator,
    LevelUpEvaluator,
    ReachEvaluator,
    ScrapEvaluator,
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

    with patch("app.services.progression.objectives.evaluators.base.async_session_maker", MockSessionMaker):
        yield


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
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
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
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
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
        challenge="Train 5 dwellers",
        reward="200 caps",
        objective_type="train",
        target_entity={},
        target_amount=5,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
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
        challenge="Assign 3 dwellers",
        reward="150 caps",
        objective_type="assign",
        target_entity={},
        target_amount=3,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
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
async def test_explore_evaluator_credits_at_departure(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """An 'explore' objective advances on departure, not on the hour-scale return."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))

    objective = Objective(
        challenge="Send a dweller exploring",
        reward="50 caps",
        objective_type="explore",
        target_entity={},
        target_amount=1,
        category=ObjectiveCategoryEnum.STARTER,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=1, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    ExploreEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(GameEvent.DWELLER_DEPARTED, vault.id, {"dweller_ids": ["d-1"]})

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
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
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
    assert link.is_completed is False


@pytest.mark.asyncio
async def test_reach_evaluator_reacts_to_dweller_added(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Population growth via DWELLER_ADDED (radio/birth) must drive a dweller-count reach objective."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    objective = Objective(
        challenge="Reach 10 dwellers",
        reward="500 caps",
        objective_type="reach",
        target_entity={"reach_type": "dweller_count", "target": 10},
        target_amount=10,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=10, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    ReachEvaluator(fresh_event_bus)

    for i in range(5):
        dweller = Dweller(first_name=f"Test{i}", gender="male", rarity="common", level=1, vault_id=vault.id)
        async_session.add(dweller)
    await async_session.commit()

    await fresh_event_bus.emit(GameEvent.DWELLER_ADDED, vault.id, {"dweller_id": "test"})
    await async_session.refresh(link)
    assert link.progress == 5
    assert link.is_completed is False

    for i in range(5, 10):
        dweller = Dweller(first_name=f"Test{i}", gender="male", rarity="common", level=1, vault_id=vault.id)
        async_session.add(dweller)
    await async_session.commit()

    await fresh_event_bus.emit(GameEvent.DWELLER_ADDED, vault.id, {"dweller_id": "test"})
    await async_session.refresh(link)
    assert link.progress == 10
    assert link.is_completed is False


@pytest.mark.asyncio
async def test_collect_evaluator_keeps_objective_active_when_reward_fails(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """A failed reward must not permanently consume a completed objective."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    objective = Objective(
        challenge="Collect one cap",
        reward="not a valid reward",
        objective_type="collect",
        target_entity={"resource_type": "caps"},
        target_amount=1,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, progress=0, total=1)
    async_session.add_all([objective, link])
    await async_session.commit()

    CollectEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})

    await async_session.refresh(link)
    assert link.progress == 1
    from app.services.reward_service import reward_service

    with pytest.raises(ValueError):
        await reward_service.claim_objective_reward(async_session, objective.id, vault.id)
    await async_session.refresh(link)
    assert link.progress == 1
    assert link.is_completed is False


@pytest.mark.asyncio
async def test_collect_evaluator_does_not_reprocess_its_reward(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """A collect reward must not recursively trigger its own evaluator."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    objective = Objective(
        challenge="Collect one cap",
        reward="10 caps",
        objective_type="collect",
        target_entity={"resource_type": "caps"},
        target_amount=1,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, progress=0, total=1)
    async_session.add_all([objective, link])
    await async_session.commit()
    initial_caps = vault.bottle_caps

    CollectEvaluator(fresh_event_bus)

    await asyncio.wait_for(
        fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1}),
        timeout=10,
    )

    await async_session.refresh(link)
    await async_session.refresh(vault)
    assert link.is_completed is False
    assert vault.bottle_caps == initial_caps
    from app.services.reward_service import reward_service

    await reward_service.claim_objective_reward(async_session, objective.id, vault.id)
    await async_session.refresh(vault)
    await async_session.refresh(link)
    assert link.is_completed is True
    assert vault.bottle_caps == initial_caps + 10


@pytest.mark.asyncio
async def test_all_assigned_starter_steps_record_early_progress(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Events count toward later starter steps before their rewards become claimable."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )

    links = []
    for sequence in range(3):
        objective = Objective(
            challenge=f"Starter collect {sequence}",
            reward="10 food",
            objective_type="collect",
            target_entity={"resource_type": "caps"},
            target_amount=5,
            category=ObjectiveCategoryEnum.STARTER,
            sequence=sequence,
        )
        async_session.add(objective)
        await async_session.flush()
        link = VaultObjectiveProgressLink(
            vault_id=vault.id, objective_id=objective.id, progress=0, total=5, is_completed=False
        )
        async_session.add(link)
        links.append(link)
    await async_session.commit()

    CollectEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})

    await async_session.refresh(links[0])
    await async_session.refresh(links[1])
    await async_session.refresh(links[2])
    assert links[0].progress == 1
    assert links[1].progress == 1
    assert links[2].progress == 1


@pytest.mark.asyncio
async def test_storage_scrap_counts_early_and_rewards_claim_in_any_order(
    async_session: AsyncSession, vault, fresh_event_bus, patched_session_maker
) -> None:
    from app.models.weapon import Weapon
    from app.services.item_service import item_service
    from app.services.recipe_unlock_service import catalog_entry
    from app.services.reward_service import reward_service
    from app.utils.exceptions import ResourceConflictException
    from app.utils.item_factory import build_weapon

    current = Objective(
        challenge="Collect one cap",
        reward="10 caps",
        category="starter",
        sequence=0,
        objective_type="collect",
        target_entity={"resource_type": "caps"},
        target_amount=1,
    )
    future = Objective(
        challenge="Scrap a rare weapon",
        reward="300 caps",
        category="starter",
        sequence=1,
        objective_type="scrap",
        target_entity={"item_type": "weapon", "rarity": "rare"},
        target_amount=1,
    )
    links = [VaultObjectiveProgressLink(vault_id=vault.id, objective_id=o.id, total=1) for o in (current, future)]
    async_session.add_all([current, future, *links])
    storage = await crud.vault.create_storage(db_session=async_session, vault_id=vault.id)
    storage.max_space = 20
    entry = catalog_entry("weapon", "Hunting rifle")
    weapon = build_weapon(entry, rarity="rare", storage_id=storage.id)
    weapon_id = weapon.id
    async_session.add(weapon)
    await async_session.commit()
    initial_caps = vault.bottle_caps
    announcements = []

    async def observe(_event, _vault_id, data):
        announcements.append(data)

    fresh_event_bus.subscribe(GameEvent.OBJECTIVE_COMPLETED, observe)
    ScrapEvaluator(fresh_event_bus)
    CollectEvaluator(fresh_event_bus)
    junk = await item_service.scrap_item(async_session, item_id=weapon_id, model=Weapon)

    assert junk
    assert await crud.weapon.get_or_none(async_session, weapon_id) is None
    await async_session.refresh(links[1])
    await async_session.refresh(vault)
    assert links[1].progress == 1
    assert links[1].is_completed is False
    assert vault.bottle_caps == initial_caps
    assert announcements == [
        {
            "objective_id": str(future.id),
            "challenge": future.challenge,
            "ready_to_claim": True,
        }
    ]

    await reward_service.claim_objective_reward(async_session, future.id, vault.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 300

    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})
    await reward_service.claim_objective_reward(async_session, current.id, vault.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 310
    with pytest.raises(ResourceConflictException, match="already claimed"):
        await reward_service.claim_objective_reward(async_session, future.id, vault.id)


@pytest.mark.asyncio
async def test_completing_current_starter_step_advances_to_next(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Completing the current step makes the next step current on the following read."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )

    links = []
    for sequence in range(2):
        objective = Objective(
            challenge=f"Starter collect {sequence}",
            reward="10 food",
            objective_type="collect",
            target_entity={"resource_type": "caps"},
            target_amount=1,
            category=ObjectiveCategoryEnum.STARTER,
            sequence=sequence,
        )
        async_session.add(objective)
        await async_session.flush()
        link = VaultObjectiveProgressLink(
            vault_id=vault.id, objective_id=objective.id, progress=0, total=1, is_completed=False
        )
        async_session.add(link)
        links.append(link)
    await async_session.commit()

    CollectEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})
    await async_session.refresh(links[0])
    assert links[0].is_completed is False
    from app.services.reward_service import reward_service

    await reward_service.claim_objective_reward(async_session, links[0].objective_id, vault.id)

    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})
    await async_session.refresh(links[1])
    assert links[1].progress == 1


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
            category=ObjectiveCategoryEnum.ACHIEVEMENT,
        )
        # Event uses alias "Living Quarters"
        data = {"room_type": "Living Quarters"}
        assert evaluator._matches(objective, GameEvent.ROOM_BUILT, data) is True

    def test_collect_evaluator_matches_item_alias_weapons(self, fresh_event_bus):
        """Test CollectEvaluator matches 'Weapons' -> 'weapon'."""
        evaluator = CollectEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Collect 3 weapons",
            reward="100 caps",
            objective_type="collect",
            target_entity={"item_type": "weapon"},
            target_amount=3,
            category=ObjectiveCategoryEnum.ACHIEVEMENT,
        )
        # Event uses plural "Weapons"
        data = {"item_type": "Weapons"}
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
            category=ObjectiveCategoryEnum.ACHIEVEMENT,
        )
        # Event uses alias "Living Quarters"
        data = {"room_type": "Living Quarters"}
        assert evaluator._matches(objective, GameEvent.DWELLER_ASSIGNED, data) is True


class TestExpeditionEvaluator:
    """Tests for ExpeditionEvaluator functionality."""

    def test_matches_specific_quest_type(self, fresh_event_bus):
        """Test ExpeditionEvaluator matches specific quest type."""
        evaluator = ExpeditionEvaluator(fresh_event_bus)
        objective = Objective(
            challenge="Complete 1 Main Quest",
            reward="2000 caps",
            objective_type="expedition",
            target_entity={"quest_type": "main"},
            target_amount=1,
            category=ObjectiveCategoryEnum.ACHIEVEMENT,
        )
        data = {"quest_type": "main"}
        assert evaluator._matches(objective, GameEvent.QUEST_COMPLETED, data) is True


@pytest.mark.asyncio
async def test_expedition_evaluator_quest_completed(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test ExpeditionEvaluator updates progress on quest completion."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    objective = Objective(
        challenge="Complete 3 quests",
        reward="800 caps",
        objective_type="expedition",
        target_entity={},
        target_amount=3,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=3, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    ExpeditionEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(GameEvent.QUEST_COMPLETED, vault.id, {"quest_type": "main"})

    await async_session.refresh(link)
    assert link.progress == 1


@pytest.mark.asyncio
async def test_level_up_evaluator_dweller_leveled_up(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test LevelUpEvaluator updates progress on dweller level up."""
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    objective = Objective(
        challenge="Level up 2 dwellers to Lv.5",
        reward="1000 caps",
        objective_type="level_up",
        target_entity={"min_level": 5},
        target_amount=2,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=2, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    LevelUpEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(GameEvent.DWELLER_LEVEL_UP, vault.id, {"new_level": 5})

    await async_session.refresh(link)
    assert link.progress == 1


@pytest.mark.asyncio
async def test_scrap_evaluator_matches_rare_weapon(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test ScrapEvaluator completes a rare-weapon objective on a matching scrap."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    objective = Objective(
        challenge="Scrap a Rare Weapon",
        reward="150 caps",
        objective_type="scrap",
        target_entity={"item_type": "weapon", "rarity": "rare"},
        target_amount=1,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=1, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    ScrapEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(
        GameEvent.ITEM_SCRAPPED,
        vault.id,
        {"item_name": "Baseball bat", "item_type": "weapon", "rarity": "rare"},
    )

    await async_session.refresh(link)
    assert link.progress == 1
    assert link.is_completed is False


@pytest.mark.asyncio
async def test_scrap_evaluator_ignores_rarity_mismatch(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test ScrapEvaluator ignores a common scrap for a rare objective."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    objective = Objective(
        challenge="Scrap a Rare Weapon",
        reward="150 caps",
        objective_type="scrap",
        target_entity={"item_type": "weapon", "rarity": "rare"},
        target_amount=1,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=1, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    ScrapEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(
        GameEvent.ITEM_SCRAPPED,
        vault.id,
        {"item_name": "Rusty pipe", "item_type": "weapon", "rarity": "common"},
    )

    await async_session.refresh(link)
    assert link.progress == 0
    assert link.is_completed is False


@pytest.mark.asyncio
async def test_scrap_evaluator_ignores_item_type_mismatch(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test ScrapEvaluator ignores an outfit scrap for a weapon objective."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    objective = Objective(
        challenge="Scrap a Rare Weapon",
        reward="150 caps",
        objective_type="scrap",
        target_entity={"item_type": "weapon", "rarity": "rare"},
        target_amount=1,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=1, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    ScrapEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(
        GameEvent.ITEM_SCRAPPED,
        vault.id,
        {"item_name": "Worn vault suit", "item_type": "outfit", "rarity": "rare"},
    )

    await async_session.refresh(link)
    assert link.progress == 0
    assert link.is_completed is False


@pytest.mark.asyncio
async def test_scrap_evaluator_rarity_only_matches_any_item_type(
    async_session: AsyncSession,
    fresh_event_bus,
    patched_session_maker,
) -> None:
    """Test a rarity-only scrap objective matches any item type."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    objective = Objective(
        challenge="Reverse-engineer a Legendary",
        reward="5000 caps",
        objective_type="scrap",
        target_entity={"rarity": "legendary"},
        target_amount=1,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    async_session.add(objective)
    await async_session.commit()
    await async_session.refresh(objective)

    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=0, total=1, is_completed=False
    )
    async_session.add(link)
    await async_session.commit()

    ScrapEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(
        GameEvent.ITEM_SCRAPPED,
        vault.id,
        {"item_name": "Legendary power armor", "item_type": "outfit", "rarity": "legendary"},
    )

    await async_session.refresh(link)
    assert link.progress == 1
    assert link.is_completed is False


def test_facade_reexports_canonical_evaluator_surface() -> None:
    """The top-level facade forwards the canonical module's public names by identity.

    The facade is a value re-export only: monkeypatching the facade's
    ``async_session_maker`` would NOT affect the canonical module, so the surface
    must stay in lockstep with ``progression.objectives.evaluators``.
    """
    from app.services import objective_evaluators as facade
    from app.services.progression.objectives import evaluators as canonical

    names = (
        "AssignCorrectEvaluator",
        "AssignEvaluator",
        "BuildEvaluator",
        "CollectEvaluator",
        "ExpeditionEvaluator",
        "ExploreEvaluator",
        "LevelUpEvaluator",
        "ObjectiveEvaluator",
        "ObjectiveEvaluatorManager",
        "ReachEvaluator",
        "TrainEvaluator",
        "async_session_maker",
        "current_session_maker",
        "evaluator_manager",
        "set_current_session_maker",
    )
    for name in names:
        assert getattr(facade, name) is getattr(canonical, name)


@pytest.mark.asyncio
async def test_full_storage_reward_rollback_preserves_other_objectives_and_retry(
    async_session, vault, fresh_event_bus, caplog
):
    """Earned rewards survive a blocked claim; independent rewards and retry still work."""
    vault_id = vault.id
    initial_caps = vault.bottle_caps
    storage = Storage(vault_id=vault_id, max_space=0)
    blocked = Objective(
        challenge="A collect food for weapon",
        reward="weapon:Laser Pistol",
        objective_type="collect",
        target_entity={"resource_type": "food"},
        target_amount=1,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    healthy = Objective(
        challenge="Z collect food for caps",
        reward="10 caps",
        objective_type="collect",
        target_entity={"resource_type": "food"},
        target_amount=1,
        category=ObjectiveCategoryEnum.ACHIEVEMENT,
    )
    blocked_link = VaultObjectiveProgressLink(vault_id=vault_id, objective_id=blocked.id, total=1)
    healthy_link = VaultObjectiveProgressLink(vault_id=vault_id, objective_id=healthy.id, total=1)
    async_session.add_all([storage, blocked, healthy, blocked_link, healthy_link])
    await async_session.commit()
    blocked_id, healthy_id, storage_id = blocked.id, healthy.id, storage.id
    evaluator = CollectEvaluator(fresh_event_bus)
    completions = []

    async def record_completion(_event, _vault, data):
        completions.append(data["objective_id"])

    fresh_event_bus.subscribe(GameEvent.OBJECTIVE_COMPLETED, record_completion)
    load_active = evaluator._get_active_objectives

    async def sorted_active(session, target_vault):
        return sorted(await load_active(session, target_vault), key=lambda pair: pair[0].challenge)

    # Match Dramatiq's raw SQLAlchemy sessions, which have no SQLModel .exec().
    maker = async_sessionmaker(
        async_session.bind, class_=AsyncSession, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    with (
        patch("app.services.progression.objectives.evaluators.base.async_session_maker", maker),
        patch.object(evaluator, "_get_active_objectives", side_effect=sorted_active),
        caplog.at_level(logging.ERROR),
    ):
        await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"resource_type": "food", "amount": 1})
        await async_session.refresh(blocked_link)
        await async_session.refresh(healthy_link)
        await async_session.refresh(vault)
        assert blocked_link.progress == 1
        assert blocked_link.is_completed is False
        assert healthy_link.is_completed is False
        assert completions == [str(blocked_id), str(healthy_id)]
        assert vault.bottle_caps == initial_caps
        from app.services.reward_service import reward_service
        from app.utils.exceptions import ResourceConflictException

        with pytest.raises(ResourceConflictException, match="Storage full"):
            await reward_service.claim_objective_reward(async_session, blocked_id, vault_id)
        await async_session.refresh(blocked_link)
        assert blocked_link.progress == 1
        assert blocked_link.is_completed is False
        await reward_service.claim_objective_reward(async_session, healthy_id, vault_id)
        await async_session.refresh(vault)
        assert vault.bottle_caps == initial_caps + 10
        assert await storage_crud.count_items(async_session, storage_id) == 0

        await async_session.refresh(storage)
        storage.max_space = 1
        await async_session.commit()
        # Freeing capacity permits exactly one delivery; the already-settled caps are not repeated.
        for _ in range(2):
            await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"resource_type": "food", "amount": 1})
        await reward_service.claim_objective_reward(async_session, blocked_id, vault_id)
        await async_session.refresh(blocked_link)
        await async_session.refresh(vault)
        assert blocked_link.is_completed is True
        assert completions == [str(blocked_id), str(healthy_id)]
        assert vault.bottle_caps == initial_caps + 10
        await async_session.refresh(storage)
        assert await storage_crud.count_items(async_session, storage_id) == 1


async def test_objective_target_waits_for_claim_and_announces_once(
    async_session: AsyncSession, fresh_event_bus, patched_session_maker
) -> None:
    """Reaching a target makes rewards ready; repeated events never pay or notify again."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    objective = Objective(
        challenge="Collect two caps",
        reward="50 caps",
        category=ObjectiveCategoryEnum.STARTER,
        objective_type="collect",
        target_entity={"resource_type": "caps"},
        target_amount=2,
        sequence=0,
    )
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, total=2)
    async_session.add_all([objective, link])
    await async_session.commit()
    initial_caps = vault.bottle_caps
    announced = []

    async def record(_event, _vault, data):
        announced.append(data)

    fresh_event_bus.subscribe(GameEvent.OBJECTIVE_COMPLETED, record)
    CollectEvaluator(fresh_event_bus)
    for _ in range(2):
        await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 2})
    await async_session.refresh(link)
    await async_session.refresh(vault)
    assert link.progress == 2
    assert link.is_completed is False
    assert vault.bottle_caps == initial_caps
    assert len(announced) == 1
    assert announced[0]["ready_to_claim"] is True
