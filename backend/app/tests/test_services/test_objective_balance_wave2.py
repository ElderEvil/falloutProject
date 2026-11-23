import json

import pytest

from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.core.event_bus import EventBus, GameEvent
from app.crud.objective import objective_crud
from app.models import Dweller, Room
from app.models.game_state import GameState
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.progression.objectives.evaluators import (
    AssignEvaluator,
    BuildEvaluator,
    CollectEvaluator,
    TrainEvaluator,
)
from app.services.resource_manager_service import ResourceManager
from app.services.rewards.settlement import claim_objective_reward
from app.utils.seed_objectives import seed_objectives_from_json

POWER = {"resource_type": "power"}
PROD_ONLY = {**POWER, "production_only": True}
STIMPAK = {"item_type": "stimpak"}
ASSIGN = {"objective_type": "assign", "target_amount": 3, "target_entity": {"distinct_dwellers": True}}


def _objective(challenge="Objective", *, reward="50 caps", category="daily", **kwargs):
    return Objective(
        challenge=challenge, reward=reward, category=category, target_entity=kwargs.pop("target_entity", {}), **kwargs
    )


def _collect(challenge, entity, amount, **kw):
    return _objective(challenge, objective_type="collect", target_entity=entity, target_amount=amount, **kw)


async def _linked(db, vault, objective, total):
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, total=total)
    db.add_all([objective, link])
    await db.commit()
    return link


def _room(output=1, size=1):
    return Room(
        name="Power", category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.STRENGTH, output=output, size=size, tier=1
    )


def test_build_objective_does_not_count_upgrade():
    assert not BuildEvaluator(EventBus())._matches(_objective("Build 2 Rooms"), GameEvent.ROOM_UPGRADED, {})


@pytest.mark.parametrize("stat_name", ["strength", "Strength"])
@pytest.mark.parametrize(("value", "expected"), [(9, False), (10, True), (11, True), (None, False)])
def test_training_requires_target_stat_value(value, expected, stat_name):
    objective = _objective(
        "Train Strength to 10", category="achievement", target_entity={"stat": "strength", "target_value": 10}
    )
    data = {"stat_trained": stat_name, "new_value": value}
    assert TrainEvaluator(EventBus())._matches(objective, GameEvent.DWELLER_TRAINED, data) == expected


async def test_same_dweller_cannot_farm_assignment_progress(async_session, vault):
    objective = _objective("Assign 3 Dwellers", reward="60 caps", **ASSIGN)
    link = await _linked(async_session, vault, objective, 3)
    evaluator = AssignEvaluator(EventBus())
    for _ in range(3):
        await evaluator._credit_event(async_session, vault.id, objective, link, {"dweller_id": "one"})
    assert link.progress == 1
    await evaluator._credit_event(async_session, vault.id, objective, link, {"dweller_id": "two"})
    assert link.progress == 2


async def test_identical_labels_in_different_categories_are_seeded(async_session, tmp_path):
    (tmp_path / "test.json").write_text(
        json.dumps(
            [{"challenge": "Collect 150 Power", "reward": "15 caps", "category": c} for c in ("starter", "daily")]
        )
    )
    assert await seed_objectives_from_json(async_session, tmp_path) == 2
    assert await seed_objectives_from_json(async_session, tmp_path) == 0


async def test_fractional_production_counts_at_full_storage(async_session, vault):
    vault.power = vault.power_max = 100
    state = GameState(vault_id=vault.id)
    room = _room()
    manager = ResourceManager()
    events = []
    for _ in range(20):
        _, tick = manager.calculate_resource_window(vault, [room], 0, [(room, [Dweller(strength=1)])], 60, state=state)
        events.append(tick)
        if len(events) == 10:
            assert sum(e.objective_production.power for e in events) == 0  # 0.72 output, retained for a later tick
    assert sum(e.objective_production.power for e in events) == 1


@pytest.mark.parametrize("item_type", ["weapon", "outfit", "junk"])
def test_item_collection_does_not_count_resource_events(item_type):
    objective = _objective("Collect items", reward="25 caps", target_entity={"item_type": item_type})
    assert not CollectEvaluator(EventBus())._matches(objective, GameEvent.RESOURCE_COLLECTED, POWER)


async def test_earned_reward_snapshot_is_used_for_claim(async_session, vault):
    objective = _objective("Earned objective", reward="20 caps", objective_type="collect", target_amount=1)
    link = VaultObjectiveProgressLink(
        vault_id=vault.id, objective_id=objective.id, progress=1, total=1, reward_snapshot="100 caps"
    )
    async_session.add_all([objective, link])
    vault.bottle_caps = 500
    await async_session.commit()
    await claim_objective_reward(async_session, objective.id, vault.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == 600
    read = await objective_crud.get_multi_for_vault(async_session, vault.id)
    assert next(item for item in read if item.id == objective.id).reward == "100 caps"


def test_produce_objectives_reject_resource_gifts():
    objective = _collect("Collect 150 Power", PROD_ONLY, 150, reward="15 caps")
    evaluator = CollectEvaluator(EventBus())
    assert not evaluator._matches(objective, GameEvent.RESOURCE_COLLECTED, {**POWER, "amount": 150})
    assert evaluator._matches(objective, GameEvent.RESOURCE_COLLECTED, {**POWER, "amount": 150, "source": "production"})


async def test_gross_production_at_capacity_advances_an_objective(async_session, vault):
    vault.power = vault.power_max = 100
    objective = _collect("Collect 150 Power", PROD_ONLY, 150, reward="15 caps")
    link = await _linked(async_session, vault, objective, 150)
    room = _room(output=28, size=3)
    update, events = ResourceManager().calculate_resource_window(
        vault, [room], 0, [(room, [Dweller(strength=5)])], 60, state=GameState(vault_id=vault.id)
    )
    assert update.power == 100
    assert events.objective_production.power == 10
    await CollectEvaluator(EventBus())._credit_event(
        async_session,
        vault.id,
        objective,
        link,
        {**POWER, "amount": events.objective_production.power, "source": "production"},
    )
    assert link.progress == 10


@pytest.mark.parametrize("event_type", [GameEvent.RESOURCE_COLLECTED, GameEvent.ITEM_COLLECTED])
def test_medical_collection_accepts_the_storage_spelling(event_type):
    objective = _objective("Collect 5 Stimpaks", reward="125 caps", category="achievement", target_entity=STIMPAK)
    assert CollectEvaluator(EventBus())._matches(
        objective, event_type, {"resource_type": "stimpack", "item_type": "stimpack"}
    )
