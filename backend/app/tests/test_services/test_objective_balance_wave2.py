"""Wave 2 objectives pay for distinct achievements and truthful actions."""

import json
from uuid import uuid4

import pytest

from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.core.event_bus import EventBus, GameEvent
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.progression.objectives.evaluators import AssignEvaluator, BuildEvaluator, TrainEvaluator
from app.utils.seed_objectives import seed_objectives_from_json


def test_build_objective_does_not_count_upgrade():
    objective = Objective(challenge="Build 2 Rooms", reward="50 caps", category="daily", target_entity={})
    assert not BuildEvaluator(EventBus())._matches(objective, GameEvent.ROOM_UPGRADED, {})


@pytest.mark.parametrize("stat_name", ["strength", "Strength"])
@pytest.mark.parametrize(("value", "expected"), [(9, False), (10, True), (11, True), (None, False)])
def test_training_requires_target_stat_value(value, expected, stat_name):
    objective = Objective(
        challenge="Train Strength to 10",
        reward="100 caps",
        category="achievement",
        target_entity={"stat": "strength", "target_value": 10},
    )
    assert (
        TrainEvaluator(EventBus())._matches(
            objective, GameEvent.DWELLER_TRAINED, {"stat_trained": stat_name, "new_value": value}
        )
        == expected
    )


async def test_same_dweller_cannot_farm_assignment_progress(async_session, vault):
    objective = Objective(
        challenge="Assign 3 Dwellers",
        reward="60 caps",
        category="daily",
        objective_type="assign",
        target_amount=3,
        target_entity={"distinct_dwellers": True},
    )
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, total=3)
    async_session.add_all([objective, link])
    await async_session.commit()
    evaluator = AssignEvaluator(EventBus())
    for _ in range(3):
        await evaluator._credit_event(async_session, vault.id, objective, link, {"dweller_id": "one"})
    assert link.progress == 1
    await evaluator._credit_event(async_session, vault.id, objective, link, {"dweller_id": "two"})
    assert link.progress == 2


async def test_identical_labels_in_different_categories_are_seeded(async_session, tmp_path):
    (tmp_path / "test.json").write_text(
        json.dumps(
            [
                {"challenge": "Collect 150 Power", "reward": "15 caps", "category": category}
                for category in ("starter", "daily")
            ]
        )
    )
    assert await seed_objectives_from_json(async_session, tmp_path) == 2
    assert await seed_objectives_from_json(async_session, tmp_path) == 0


async def test_fractional_production_counts_at_full_storage(async_session, vault):
    from app.models import Dweller, Room
    from app.models.game_state import GameState
    from app.services.resource_manager import ResourceManager

    vault.power = vault.power_max = 100
    state = GameState(vault_id=vault.id)
    room = Room(name="Power", category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.STRENGTH, output=1, size=1, tier=1)
    manager = ResourceManager()
    events = []
    for _ in range(10):
        _, tick = manager.calculate_resource_window(vault, [room], 0, [(room, [Dweller(strength=1)])], 60, state=state)
        events.append(tick)
    assert sum(event.objective_production.power for event in events) == 0  # 0.72 output, retained for a later tick
    for _ in range(10):
        _, tick = manager.calculate_resource_window(vault, [room], 0, [(room, [Dweller(strength=1)])], 60, state=state)
        events.append(tick)
    assert sum(event.objective_production.power for event in events) == 1


@pytest.mark.parametrize("item_type", ["weapon", "outfit", "junk"])
def test_item_collection_does_not_count_resource_events(item_type):
    from app.services.progression.objectives.evaluators import CollectEvaluator

    objective = Objective(
        challenge="Collect items", reward="25 caps", category="daily", target_entity={"item_type": item_type}
    )
    assert not CollectEvaluator(EventBus())._matches(
        objective, GameEvent.RESOURCE_COLLECTED, {"resource_type": "power"}
    )


async def test_earned_reward_snapshot_is_used_for_claim(async_session, vault):
    from app.services.rewards.settlement import claim_objective_reward

    objective = Objective(
        challenge="Earned objective", reward="20 caps", category="daily", objective_type="collect", target_amount=1
    )
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=1, total=1, reward_snapshot="100 caps"
    )
    async_session.add_all([objective, link])
    await async_session.commit()
    initial_caps = vault.bottle_caps
    await claim_objective_reward(async_session, objective.id, vault.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 100
    from app.crud.objective import objective_crud

    read = await objective_crud.get_multi_for_vault(async_session, vault.id)
    assert next(item for item in read if item.id == objective.id).reward == "100 caps"


def test_produce_objectives_reject_resource_gifts():
    from app.services.progression.objectives.evaluators import CollectEvaluator

    objective = Objective(
        challenge="Collect 150 Power",
        reward="15 caps",
        category="daily",
        target_entity={"resource_type": "power", "production_only": True},
    )
    evaluator = CollectEvaluator(EventBus())
    assert not evaluator._matches(objective, GameEvent.RESOURCE_COLLECTED, {"resource_type": "power", "amount": 150})
    assert evaluator._matches(
        objective, GameEvent.RESOURCE_COLLECTED, {"resource_type": "power", "amount": 150, "source": "production"}
    )


async def test_gross_production_at_capacity_advances_an_objective(async_session, vault):
    from app.core.enums import RoomTypeEnum, SPECIALEnum
    from app.models import Dweller, Room
    from app.models.game_state import GameState
    from app.services.progression.objectives.evaluators import CollectEvaluator
    from app.services.resource_manager import ResourceManager

    vault.power = vault.power_max = 100
    objective = Objective(
        challenge="Collect 150 Power",
        reward="15 caps",
        category="daily",
        objective_type="collect",
        target_entity={"resource_type": "power", "production_only": True},
        target_amount=150,
    )
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, total=150)
    async_session.add_all([objective, link])
    await async_session.commit()
    room = Room(name="Power", category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.STRENGTH, output=28, size=3, tier=1)
    manager = ResourceManager()
    update, events = manager.calculate_resource_window(
        vault, [room], 0, [(room, [Dweller(strength=5)])], 60, state=GameState(vault_id=vault.id)
    )
    assert update.power == 100
    assert events.objective_production.power == 10
    evaluator = CollectEvaluator(EventBus())
    await evaluator._credit_event(
        async_session,
        vault.id,
        objective,
        link,
        {"resource_type": "power", "amount": events.objective_production.power, "source": "production"},
    )
    assert link.progress == 10


@pytest.mark.parametrize("event_type", [GameEvent.RESOURCE_COLLECTED, GameEvent.ITEM_COLLECTED])
def test_medical_collection_accepts_the_storage_spelling(event_type):
    from app.services.progression.objectives.evaluators import CollectEvaluator

    objective = Objective(
        challenge="Collect 5 Stimpaks",
        reward="125 caps",
        category="achievement",
        target_entity={"item_type": "stimpak"},
    )
    assert CollectEvaluator(EventBus())._matches(
        objective, event_type, {"resource_type": "stimpack", "item_type": "stimpack"}
    )
