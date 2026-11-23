import asyncio
import logging
from unittest.mock import patch

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import crud
from app.core.event_bus import GameEvent, event_bus
from app.crud.storage import storage as storage_crud
from app.models.dweller import Dweller
from app.models.objective import Objective
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.vault_objective import VaultObjectiveProgressLink
from app.models.weapon import Weapon
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.item_service import item_service
from app.services.progression.objectives.evaluators import (
    AssignEvaluator,
    BuildEvaluator,
    CollectEvaluator,
    ExpeditionEvaluator,
    ExploreEvaluator,
    LevelUpEvaluator,
    ObjectiveEvaluator,
    ReachEvaluator,
    ScrapEvaluator,
    TrainEvaluator,
)
from app.services.recipe_unlock_service import catalog_entry
from app.services.reward_service import reward_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.tests.utils.query_counter import count_sql_statements
from app.utils.exceptions import ResourceConflictException
from app.utils.item_factory import build_weapon


@pytest.fixture
def fresh_event_bus():
    event_bus.clear()
    yield event_bus
    event_bus.clear()


@pytest.fixture
def patched_session_maker(async_session):
    class MockSessionMaker:
        async def __aenter__(self):
            return async_session

        async def __aexit__(self, *args):
            pass

    with patch("app.services.progression.objectives.evaluators.base.async_session_maker", MockSessionMaker):
        yield


CAPS = {"resource_type": "caps"}
REACH = {"reach_type": "dweller_count", "target": 10}


async def _vault(db):
    user = await crud.user.create(db, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(db, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))


def _obj(challenge, reward, objective_type, target_entity, amount, **kwargs):
    return Objective(
        challenge=challenge,
        reward=reward,
        objective_type=objective_type,
        target_entity=target_entity,
        target_amount=amount,
        **kwargs,
    )


async def _progress(
    db,
    vault,
    objective_type,
    target_entity,
    target_amount,
    challenge="Objective",
    reward="10 caps",
    category="achievement",
    **kwargs,
):
    objective = _obj(challenge, reward, objective_type, target_entity, target_amount, category=category, **kwargs)
    link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, progress=0, total=target_amount)
    db.add_all([objective, link])
    await db.commit()
    await db.refresh(link)
    return objective, link


async def _dwellers(db, vault, count, start=0):
    db.add_all(
        Dweller(first_name=f"Test{i}", gender="male", rarity="common", level=1, vault_id=vault.id)
        for i in range(start, start + count)
    )
    await db.commit()


async def test_collect_evaluator_wrong_resource(async_session, fresh_event_bus, patched_session_maker):
    vault = await _vault(async_session)
    _, link = await _progress(
        async_session, vault, "collect", {"resource_type": "caps"}, 100, challenge="Collect 100 caps"
    )
    CollectEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "food", "amount": 50})

    await async_session.refresh(link)
    assert link.progress == 0


async def test_collect_evaluator_credits_batched_resources(async_session, fresh_event_bus, patched_session_maker):
    vault = await _vault(async_session)
    targets = {
        "power": {"resource_type": "power"},
        "food": {"resource_type": "food"},
        "caps": {"resource_type": "caps"},
        "production_only": {"resource_type": "power", "production_only": True},
        "any": {},
    }
    links = {}
    for label, target_entity in targets.items():
        _, links[label] = await _progress(
            async_session, vault, "collect", target_entity, 100, challenge=f"Collect from {label}", category="daily"
        )

    CollectEvaluator(fresh_event_bus)
    await fresh_event_bus.emit(
        GameEvent.RESOURCE_COLLECTED,
        vault.id,
        {"resources": {"power": 10, "food": 5, "caps": 7}, "source": "rush"},
    )

    for link in links.values():
        await async_session.refresh(link)
    assert links["power"].progress == 10
    assert links["food"].progress == 5
    assert links["caps"].progress == 7
    assert links["production_only"].progress == 0
    assert links["any"].progress == 22


async def test_batched_production_uses_fewer_statements(async_session, fresh_event_bus, patched_session_maker):
    vault = await _vault(async_session)
    links = {}
    for resource_type in ("power", "food"):
        objective = Objective(
            challenge=f"Collect 100 {resource_type}",
            reward="50 caps",
            objective_type="collect",
            target_entity={"resource_type": resource_type},
            target_amount=100,
            category="daily",
        )
        async_session.add(objective)
        await async_session.commit()
        await async_session.refresh(objective)
        link = VaultObjectiveProgressLink(vault_id=vault.id, objective_id=objective.id, progress=0, total=100)
        async_session.add(link)
        links[resource_type] = link
    await async_session.commit()

    CollectEvaluator(fresh_event_bus)

    with count_sql_statements(async_session) as per_resource:
        for resource_type in ("power", "food"):
            await fresh_event_bus.emit(
                GameEvent.RESOURCE_COLLECTED,
                vault.id,
                {"resource_type": resource_type, "amount": 1, "source": "production"},
            )

    for link in links.values():
        link.progress = 0
    await async_session.commit()

    with count_sql_statements(async_session) as batched:
        await fresh_event_bus.emit(
            GameEvent.RESOURCE_COLLECTED,
            vault.id,
            {"resources": {"power": 1, "food": 1}, "source": "production"},
        )

    assert per_resource.value - batched.value >= 2, f"batched={batched.value} per_resource={per_resource.value}"
    for link in links.values():
        await async_session.refresh(link)
        assert link.progress == 1


async def test_batched_production_continues_after_one_payload_fails(
    async_session, fresh_event_bus, patched_session_maker
):
    vault = await _vault(async_session)
    _, link = await _progress(
        async_session, vault, "collect", {}, 100, challenge="Collect any resource", category="daily"
    )

    CollectEvaluator(fresh_event_bus)
    original_credit = ObjectiveEvaluator._credit_event

    async def flaky_credit(self, db_session, vault_id, target, target_link, data):
        if data.get("resource_type") == "power":
            raise RuntimeError("simulated power credit failure")
        return await original_credit(self, db_session, vault_id, target, target_link, data)

    with patch.object(ObjectiveEvaluator, "_credit_event", flaky_credit):
        await fresh_event_bus.emit(
            GameEvent.RESOURCE_COLLECTED,
            vault.id,
            {"resources": {"power": 10, "food": 5}, "source": "production"},
        )

    await async_session.refresh(link)
    assert link.progress == 5


@pytest.mark.parametrize(
    ("evaluator_cls", "objective_type", "target_entity", "amount", "category", "kind", "payload"),
    [
        (
            BuildEvaluator,
            "build",
            {"room_type": "*"},
            3,
            "achievement",
            GameEvent.ROOM_BUILT,
            {"room_type": "Power Generator", "tier": 1, "room_id": "test-id"},
        ),
        (ExploreEvaluator, "explore", {}, 1, "starter", GameEvent.DWELLER_DEPARTED, {"dweller_ids": ["d-1"]}),
        (ExpeditionEvaluator, "expedition", {}, 3, "achievement", GameEvent.QUEST_COMPLETED, {"quest_type": "main"}),
        (
            LevelUpEvaluator,
            "level_up",
            {"min_level": 5},
            2,
            "achievement",
            GameEvent.DWELLER_LEVEL_UP,
            {"new_level": 5},
        ),
    ],
    ids=["build", "explore", "expedition", "level_up"],
)
async def test_single_event_credits_progress(
    async_session,
    fresh_event_bus,
    patched_session_maker,
    evaluator_cls,
    objective_type,
    target_entity,
    amount,
    category,
    kind,
    payload,
):
    vault = await _vault(async_session)
    _, link = await _progress(async_session, vault, objective_type, target_entity, amount, category=category)
    evaluator_cls(fresh_event_bus)

    await fresh_event_bus.emit(kind, vault.id, payload)

    await async_session.refresh(link)
    assert link.progress == 1


@pytest.mark.parametrize(
    ("evaluator_cls", "objective_type", "challenge", "amount", "kind", "extra"),
    [
        (TrainEvaluator, "train", "Train 5 dwellers", 5, GameEvent.DWELLER_TRAINED, {"stat_trained": "strength"}),
        (AssignEvaluator, "assign", "Assign 3 dwellers", 3, GameEvent.DWELLER_ASSIGNED, {"room_id": "test-room"}),
    ],
    ids=["train", "assign"],
)
async def test_dweller_event_evaluator_credits_progress(
    async_session, fresh_event_bus, patched_session_maker, evaluator_cls, objective_type, challenge, amount, kind, extra
):
    vault = await _vault(async_session)
    _, link = await _progress(async_session, vault, objective_type, {}, amount, challenge=challenge)
    dweller = Dweller(first_name="Test", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    evaluator_cls(fresh_event_bus)

    await fresh_event_bus.emit(kind, vault.id, {"dweller_id": str(dweller.id), **extra})

    await async_session.refresh(link)
    assert link.progress == 1


async def test_reach_evaluator_population_reached(async_session, fresh_event_bus, patched_session_maker):
    vault = await _vault(async_session)
    _, link = await _progress(async_session, vault, "reach", REACH, 10, challenge="Reach 10 dwellers")
    ReachEvaluator(fresh_event_bus)

    await _dwellers(async_session, vault, 10)

    await fresh_event_bus.emit(GameEvent.DWELLER_ASSIGNED, vault.id, {"dweller_id": "test", "room_id": "test-room"})

    await async_session.refresh(link)
    assert link.is_completed is False


async def test_reach_evaluator_reacts_to_dweller_added(async_session, fresh_event_bus, patched_session_maker):
    vault = await _vault(async_session)
    _, link = await _progress(async_session, vault, "reach", REACH, 10, challenge="Reach 10 dwellers")
    ReachEvaluator(fresh_event_bus)

    await _dwellers(async_session, vault, 5)
    await fresh_event_bus.emit(GameEvent.DWELLER_ADDED, vault.id, {"dweller_id": "test"})
    await async_session.refresh(link)
    assert link.progress == 5
    assert link.is_completed is False

    await _dwellers(async_session, vault, 5, start=5)
    await fresh_event_bus.emit(GameEvent.DWELLER_ADDED, vault.id, {"dweller_id": "test"})
    await async_session.refresh(link)
    assert link.progress == 10
    assert link.is_completed is False


async def test_reach_evaluator_skips_unchanged_progress_write(
    async_session, vault: Vault, fresh_event_bus, patched_session_maker
):
    _, link = await _progress(async_session, vault, "reach", REACH, 10, challenge="Reach 10 dwellers")
    link.progress = 5
    await _dwellers(async_session, vault, 5)

    ReachEvaluator(fresh_event_bus)
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    connection = await async_session.connection()
    event.listen(connection.sync_connection, "before_cursor_execute", capture)
    try:
        await fresh_event_bus.emit(GameEvent.DWELLER_ASSIGNED, vault.id, {"dweller_id": "test", "room_id": "test-room"})
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", capture)

    await async_session.refresh(link)
    assert link.progress == 5
    assert not [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("UPDATE") and "vaultobjectiveprogresslink" in statement.lower()
    ]


async def test_collect_evaluator_keeps_objective_active_when_reward_fails(
    async_session, fresh_event_bus, patched_session_maker
):
    vault = await _vault(async_session)
    objective, link = await _progress(
        async_session,
        vault,
        "collect",
        {"resource_type": "caps"},
        1,
        challenge="Collect one cap",
        reward="not a valid reward",
    )

    CollectEvaluator(fresh_event_bus)
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})

    await async_session.refresh(link)
    assert link.progress == 1

    with pytest.raises(ValueError, match="Cannot parse objective reward string"):
        await reward_service.claim_objective_reward(async_session, objective.id, vault.id)
    await async_session.refresh(link)
    assert link.progress == 1
    assert link.is_completed is False


async def test_collect_evaluator_does_not_reprocess_its_reward(async_session, fresh_event_bus, patched_session_maker):
    vault = await _vault(async_session)
    objective, link = await _progress(
        async_session, vault, "collect", {"resource_type": "caps"}, 1, challenge="Collect one cap", reward="10 caps"
    )
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

    await reward_service.claim_objective_reward(async_session, objective.id, vault.id)
    await async_session.refresh(vault)
    await async_session.refresh(link)
    assert link.is_completed is True
    assert vault.bottle_caps == initial_caps + 10


async def _starter_chain(db, vault, count, amount, reward="10 food"):
    objectives = [
        _obj(f"Starter collect {s}", reward, "collect", CAPS, amount, category="starter", sequence=s)
        for s in range(count)
    ]
    links = [
        VaultObjectiveProgressLink(vault_id=vault.id, objective_id=o.id, progress=0, total=amount, is_completed=False)
        for o in objectives
    ]
    db.add_all([*objectives, *links])
    await db.commit()
    return objectives, links


async def test_all_assigned_starter_steps_record_early_progress(async_session, fresh_event_bus, patched_session_maker):
    vault = await _vault(async_session)
    _, links = await _starter_chain(async_session, vault, 3, 5)

    CollectEvaluator(fresh_event_bus)
    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})

    for link in links:
        await async_session.refresh(link)
    assert links[0].progress == 1
    assert links[1].progress == 1
    assert links[2].progress == 1


async def test_storage_scrap_counts_early_and_rewards_claim_in_any_order(
    async_session, vault, fresh_event_bus, patched_session_maker
):
    current = _obj(
        "Collect one cap", "10 caps", "collect", {"resource_type": "caps"}, 1, category="starter", sequence=0
    )
    future = _obj(
        "Scrap a rare weapon",
        "300 caps",
        "scrap",
        {"item_type": "weapon", "rarity": "rare"},
        1,
        category="starter",
        sequence=1,
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
    assert announcements == [{"objective_id": str(future.id), "challenge": future.challenge, "ready_to_claim": True}]

    await reward_service.claim_objective_reward(async_session, future.id, vault.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 300

    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})
    await reward_service.claim_objective_reward(async_session, current.id, vault.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 310
    with pytest.raises(ResourceConflictException, match="already claimed"):
        await reward_service.claim_objective_reward(async_session, future.id, vault.id)


async def test_completing_current_starter_step_advances_to_next(async_session, fresh_event_bus, patched_session_maker):
    vault = await _vault(async_session)
    _, links = await _starter_chain(async_session, vault, 2, 1)

    CollectEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})
    await async_session.refresh(links[0])
    assert links[0].is_completed is False

    await reward_service.claim_objective_reward(async_session, links[0].objective_id, vault.id)

    await fresh_event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "caps", "amount": 1})
    await async_session.refresh(links[1])
    assert links[1].progress == 1


@pytest.mark.parametrize(
    ("evaluator_cls", "objective_type", "target_entity", "kind", "data"),
    [
        (BuildEvaluator, "build", {"room_type": "living_room"}, GameEvent.ROOM_BUILT, {"room_type": "Living Quarters"}),
        (CollectEvaluator, "collect", {"item_type": "weapon"}, GameEvent.ITEM_COLLECTED, {"item_type": "Weapons"}),
        (
            AssignEvaluator,
            "assign",
            {"room_type": "living_room"},
            GameEvent.DWELLER_ASSIGNED,
            {"room_type": "Living Quarters"},
        ),
        (ExpeditionEvaluator, "expedition", {"quest_type": "main"}, GameEvent.QUEST_COMPLETED, {"quest_type": "main"}),
    ],
    ids=["build_room_alias", "collect_item_alias", "assign_room_alias", "expedition_quest_type"],
)
def test_evaluator_matches_aliased_target(fresh_event_bus, evaluator_cls, objective_type, target_entity, kind, data):
    objective = Objective(
        challenge="Match target",
        reward="100 caps",
        objective_type=objective_type,
        target_entity=target_entity,
        target_amount=1,
        category="achievement",
    )
    assert evaluator_cls(fresh_event_bus)._matches(objective, kind, data) is True


@pytest.mark.parametrize(
    ("challenge", "target_entity", "payload", "progress"),
    [
        (
            "Scrap a Rare Weapon",
            {"item_type": "weapon", "rarity": "rare"},
            {"item_name": "Baseball bat", "item_type": "weapon", "rarity": "rare"},
            1,
        ),
        (
            "Scrap a Rare Weapon",
            {"item_type": "weapon", "rarity": "rare"},
            {"item_name": "Rusty pipe", "item_type": "weapon", "rarity": "common"},
            0,
        ),
        (
            "Scrap a Rare Weapon",
            {"item_type": "weapon", "rarity": "rare"},
            {"item_name": "Worn vault suit", "item_type": "outfit", "rarity": "rare"},
            0,
        ),
        (
            "Reverse-engineer a Legendary",
            {"rarity": "legendary"},
            {"item_name": "Legendary power armor", "item_type": "outfit", "rarity": "legendary"},
            1,
        ),
    ],
    ids=["rare_weapon", "rarity_mismatch", "item_type_mismatch", "rarity_only"],
)
async def test_scrap_evaluator_matching(
    async_session, fresh_event_bus, patched_session_maker, challenge, target_entity, payload, progress
):
    vault = await _vault(async_session)
    _, link = await _progress(async_session, vault, "scrap", target_entity, 1, challenge=challenge, reward="150 caps")
    ScrapEvaluator(fresh_event_bus)

    await fresh_event_bus.emit(GameEvent.ITEM_SCRAPPED, vault.id, payload)

    await async_session.refresh(link)
    assert link.progress == progress
    assert link.is_completed is False


async def test_full_storage_reward_rollback_preserves_other_objectives_and_retry(
    async_session, vault, fresh_event_bus, caplog
):
    vault_id = vault.id
    initial_caps = vault.bottle_caps
    storage = Storage(vault_id=vault_id, max_space=0)
    blocked = _obj(
        "A collect food for weapon",
        "weapon:Laser Pistol",
        "collect",
        {"resource_type": "food"},
        1,
        category="achievement",
    )
    healthy = _obj(
        "Z collect food for caps", "10 caps", "collect", {"resource_type": "food"}, 1, category="achievement"
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
    async_session, fresh_event_bus, patched_session_maker
):
    vault = await _vault(async_session)
    _, link = await _progress(
        async_session,
        vault,
        "collect",
        {"resource_type": "caps"},
        2,
        challenge="Collect two caps",
        reward="50 caps",
        category="starter",
        sequence=0,
    )
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


@pytest.mark.parametrize(
    ("target", "event", "expected"),
    [
        (
            {"item_type": "junk", "junk_type": "adhesive", "source": "wasteland"},
            {"item_type": "junk", "junk_type": "adhesive", "amount": 1, "source": "wasteland"},
            True,
        ),
        (
            {"item_type": "junk", "junk_type": "adhesive", "source": "wasteland"},
            {"item_type": "junk", "junk_type": "circuitry", "amount": 1, "source": "wasteland"},
            False,
        ),
        (
            {"item_type": "junk", "junk_type": "adhesive", "source": "wasteland"},
            {"item_type": "junk", "junk_type": "adhesive", "amount": 1},
            False,
        ),
        ({"item_type": "junk"}, {"item_type": "junk", "junk_type": "circuitry", "amount": 1}, True),
        ({"item_type": "junk"}, {"item_type": "junk", "amount": 1, "source": "wasteland"}, True),
    ],
)
def test_collect_matches_material_and_source(target: dict, event: dict, expected: bool, fresh_event_bus) -> None:
    objective = Objective(
        challenge="Collect junk",
        reward="50 caps",
        objective_type="collect",
        target_entity=target,
        target_amount=6,
        category="weekly",
    )

    assert CollectEvaluator(fresh_event_bus)._matches(objective, GameEvent.ITEM_COLLECTED, event) is expected
