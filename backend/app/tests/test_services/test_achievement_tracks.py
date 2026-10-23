"""Staged achievements exercise real services and database state."""

from contextlib import asynccontextmanager

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from app.core.event_bus import EventBus, GameEvent, event_bus
from app.crud.objective import objective_crud
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.progression.objectives.assignment import ObjectiveAssignmentService
from app.services.progression.objectives.evaluators.base import current_session_maker
from app.services.progression.objectives.evaluators.concrete import CollectEvaluator
from app.services.rewards.settlement import claim_objective_reward
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException


async def water_stages(db):
    stages = [
        Objective(
            challenge=f"Collect {amount} Water",
            reward="10 caps",
            category="achievement",
            objective_type="collect",
            target_entity={"resource_type": "water"},
            target_amount=amount,
            track_key="collect:water",
            sequence=stage,
        )
        for stage, amount in enumerate((100, 500, 1500), 1)
    ]
    db.add_all(stages)
    await db.commit()
    return stages


@pytest.fixture
async def water_events(async_session):
    bus = EventBus()
    CollectEvaluator(bus)
    notifications = []

    async def completed(_kind, _vault, data):
        notifications.append(data)

    bus.subscribe(GameEvent.OBJECTIVE_COMPLETED, completed)
    event_bus.subscribe(GameEvent.OBJECTIVE_COMPLETED, completed)

    @asynccontextmanager
    async def scope():
        yield async_session

    token = current_session_maker.set(scope)
    yield bus, notifications
    event_bus.unsubscribe(GameEvent.OBJECTIVE_COMPLETED, completed)
    current_session_maker.reset(token)


async def test_achievement_unlocks_only_on_claim(async_session, vault, water_events):
    stages = await water_stages(async_session)
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id, auto_commit=False)
    await async_session.commit()
    assert [link.objective_id for link in await objective_crud.get_links_for_vault(async_session, vault.id)] == [
        stages[0].id
    ]
    bus, notifications = water_events
    await bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "water", "amount": 150})
    links = {link.objective_id: link for link in await objective_crud.get_links_for_vault(async_session, vault.id)}
    assert links[stages[0].id].progress == 100
    assert not links[stages[0].id].is_completed
    assert stages[1].id not in links
    assert "next_achievement" not in notifications[0]
    await bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "water", "amount": 60})
    links = {link.objective_id: link for link in await objective_crud.get_links_for_vault(async_session, vault.id)}
    assert stages[1].id not in links
    assert links[stages[0].id].progress == 100
    await claim_objective_reward(async_session, stages[0].id, vault.id)
    with pytest.raises(ResourceConflictException):
        await claim_objective_reward(async_session, stages[0].id, vault.id)
    links = {link.objective_id: link for link in await objective_crud.get_links_for_vault(async_session, vault.id)}
    assert links[stages[1].id].progress == 0
    assert not links[stages[1].id].is_locked
    await bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "water", "amount": 60})
    assert links[stages[1].id].progress == 60
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id, auto_commit=False)
    assert links[stages[1].id].progress == 60


async def test_legacy_parallel_progress_is_kept_until_the_next_counting_window(async_session, vault, water_events):
    stages = await water_stages(async_session)
    async_session.add_all(
        [
            VaultObjectiveProgressLink(vault_id=vault.id, objective_id=stages[0].id, progress=90, total=100),
            VaultObjectiveProgressLink(vault_id=vault.id, objective_id=stages[1].id, progress=300, total=500),
            VaultObjectiveProgressLink(
                vault_id=vault.id, objective_id=stages[2].id, progress=1500, total=1500, reward_snapshot="7 caps"
            ),
        ]
    )
    await async_session.commit()
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id, auto_commit=False)
    await async_session.commit()
    visible = await objective_crud.get_multi_for_vault(async_session, vault.id)
    assert {row.id for row in visible} == {stages[0].id, stages[2].id}
    hidden = await objective_crud.get_link_for_update(async_session, stages[1].id, vault.id)
    assert hidden.progress == 300
    assert hidden.is_locked
    await water_events[0].emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "water", "amount": 20})
    assert hidden.progress == 300
    assert hidden.is_locked
    await claim_objective_reward(async_session, stages[0].id, vault.id)
    await async_session.refresh(hidden)
    assert hidden.progress == 0
    assert not hidden.is_locked
    pending = await objective_crud.get_link_for_update(async_session, stages[2].id, vault.id)
    assert pending.reward_snapshot == "7 caps"
    assert not pending.is_completed


async def test_later_stage_cannot_be_claimed_before_the_active_stage(async_session, vault, water_events):
    stages = await water_stages(async_session)
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id, auto_commit=False)
    await async_session.commit()
    for amount in (100, 500, 1500):
        await water_events[0].emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "water", "amount": amount})
    links = await objective_crud.get_links_for_vault(async_session, vault.id)
    assert [link.objective_id for link in links] == [stages[0].id]
    with pytest.raises(ResourceNotFoundException):
        await claim_objective_reward(async_session, stages[2].id, vault.id)
    await claim_objective_reward(async_session, stages[0].id, vault.id)
    second = await objective_crud.get_link_for_update(async_session, stages[1].id, vault.id)
    assert second is not None
    assert not second.is_locked


async def test_distinct_dwellers_get_a_fresh_counting_window(async_session, vault, water_events):
    from uuid import uuid4

    from app.services.progression.objectives.evaluators.concrete import AssignCorrectEvaluator

    stages = [
        Objective(
            challenge=f"Correctly assign {amount}",
            reward="10 caps",
            category="achievement",
            objective_type="assign_correct",
            target_entity={"distinct_dwellers": True},
            target_amount=amount,
            track_key="assign_correct:any",
            sequence=stage,
        )
        for stage, amount in enumerate((1, 2), 1)
    ]
    async_session.add_all(stages)
    await async_session.commit()
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id, auto_commit=False)
    await async_session.commit()
    bus = water_events[0]
    AssignCorrectEvaluator(bus)
    dweller_id = str(uuid4())
    for _ in range(3):
        await bus.emit(GameEvent.DWELLER_ASSIGNED_CORRECTLY, vault.id, {"dweller_id": dweller_id, "is_correct": True})
    await claim_objective_reward(async_session, stages[0].id, vault.id)
    next_dweller = str(uuid4())
    await bus.emit(GameEvent.DWELLER_ASSIGNED_CORRECTLY, vault.id, {"dweller_id": next_dweller, "is_correct": True})
    second = await objective_crud.get_link_for_update(async_session, stages[1].id, vault.id)
    assert second.progress == 1
    assert second.credited_dweller_ids == [next_dweller]


async def test_claim_unlock_failure_rolls_back_the_claim(async_session, vault, water_events):
    stages = await water_stages(async_session)
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id, auto_commit=False)
    await async_session.commit()
    vault_id, first_id, next_id = vault.id, stages[0].id, stages[1].id
    await water_events[0].emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"resource_type": "water", "amount": 100})
    connection = await async_session.connection()

    def break_unlock(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO vaultobjectiveprogresslink"):
            return "SELECT * FROM missing_unlock_table", ()
        return statement, parameters

    event.listen(connection.sync_connection, "before_cursor_execute", break_unlock, retval=True)
    try:
        with pytest.raises(OperationalError):
            await claim_objective_reward(async_session, first_id, vault_id)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", break_unlock)
        await async_session.rollback()
    first = await objective_crud.get_link_for_update(async_session, first_id, vault_id)
    assert not first.is_completed
    assert await objective_crud.get_link_for_update(async_session, next_id, vault_id) is None
    await claim_objective_reward(async_session, first_id, vault_id)
    assert await objective_crud.get_link_for_update(async_session, next_id, vault_id) is not None


async def test_existing_vault_initializes_tracks_without_waiting_for_a_calendar_reset(async_session, vault):
    from datetime import datetime

    from app.crud.game_state import game_state_crud
    from app.services.progression.objectives.refresh_service import ensure_current_objectives

    stages = await water_stages(async_session)
    state = await game_state_crud.get_or_create(async_session, vault.id)
    state.daily_objectives_period = datetime(2026, 10, 19)
    state.weekly_objectives_period = datetime(2026, 10, 19)
    await async_session.commit()
    assert await ensure_current_objectives(async_session, vault.id, now=datetime(2026, 10, 19)) == []
    assert state.achievement_tracks_initialized
    links = await objective_crud.get_links_for_vault(async_session, vault.id)
    assert [(link.objective_id, link.progress) for link in links] == [(stages[0].id, 0)]


async def test_renewal_discovers_new_families_without_resetting_current_progress(async_session, vault):
    from datetime import datetime

    from app.services.progression.objectives.refresh_service import ensure_current_objectives

    stages = await water_stages(async_session)
    async_session.add(Objective(challenge="Daily water", category="daily", reward="10 caps", objective_type="collect"))
    await async_session.commit()
    await ensure_current_objectives(async_session, vault.id, now=datetime(2026, 10, 19))
    current = await objective_crud.get_link_for_update(async_session, stages[0].id, vault.id)
    current.progress = 42
    added = Objective(
        challenge="Collect 100 Food",
        category="achievement",
        reward="10 caps",
        objective_type="collect",
        target_entity={"resource_type": "food"},
        target_amount=100,
        track_key="collect:food",
        sequence=1,
    )
    async_session.add(added)
    await async_session.commit()
    assert await ensure_current_objectives(async_session, vault.id, now=datetime(2026, 10, 20)) == ["daily"]
    links = {link.objective_id: link for link in await objective_crud.get_links_for_vault(async_session, vault.id)}
    assert links[stages[0].id].progress == 42
    assert links[added.id].progress == 0
    assert stages[1].id not in links


async def existing_population(db, vault_id, count, *, level=1):
    from app import crud
    from app.schemas.dweller import DwellerCreate
    from app.tests.factory.dwellers import create_random_common_dweller

    for _ in range(count):
        await crud.dweller.create(
            db,
            obj_in=DwellerCreate(**(create_random_common_dweller() | {"level": level}), vault_id=vault_id),
        )


async def population_stages(db):
    stages = [
        Objective(
            challenge=f"Reach {amount} Dwellers",
            reward="10 caps",
            category="achievement",
            objective_type="reach",
            target_entity={"reach_type": "dweller_count"},
            target_amount=amount,
            track_key="reach:dweller_count",
            sequence=sequence,
        )
        for sequence, amount in enumerate((10, 25, 50), 1)
    ]
    db.add_all(stages)
    await db.commit()
    return stages


@pytest.mark.parametrize("population", [4, 15, 30])
@pytest.mark.parametrize("through_refresh", [False, True], ids=["assignment", "refresh"])
async def test_new_population_milestone_credits_existing_residents(
    async_session, vault, water_events, population, through_refresh
):
    from app.services.progression.objectives.refresh_service import ensure_current_objectives

    await existing_population(async_session, vault.id, population)
    stages = await population_stages(async_session)
    if through_refresh:
        from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession

        async with RawAsyncSession(
            bind=await async_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as worker:
            await ensure_current_objectives(worker, vault.id)
    else:
        await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id)
    links = {link.objective_id: link for link in await objective_crud.get_links_for_vault(async_session, vault.id)}
    first = links[stages[0].id]
    assert first.progress == min(population, 10)
    assert not first.is_completed
    if population < 10:
        assert first.reward_snapshot is None
        assert stages[1].id not in links
        assert water_events[1] == []
    else:
        assert first.reward_snapshot == "10 caps"
        assert stages[1].id not in links
        assert stages[2].id not in links
        assert water_events[1] == [
            {
                "objective_id": str(stages[0].id),
                "challenge": "Reach 10 Dwellers",
                "ready_to_claim": True,
            }
        ]
        await claim_objective_reward(async_session, stages[0].id, vault.id)
        await async_session.refresh(first)
        assert first.is_completed
        unlocked = await objective_crud.get_link_for_update(async_session, stages[1].id, vault.id)
        assert unlocked is not None
        assert unlocked.progress == 0
    before = len(water_events[1])
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id)
    assert len(water_events[1]) == before
    if population >= 10:
        refreshed = await objective_crud.get_link_for_update(async_session, stages[1].id, vault.id)
        assert refreshed is not None
        assert refreshed.progress == 0


async def test_initial_population_completion_is_not_announced_before_commit(async_session, vault, water_events):
    from app.services.progression.objectives.refresh_service import ensure_current_objectives

    vault_id = vault.id
    await existing_population(async_session, vault_id, 15)
    stages = await population_stages(async_session)
    first_id = stages[0].id

    def fail_commit(_session):
        raise RuntimeError("Assignment commit failed")

    event.listen(async_session.sync_session, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="Assignment commit failed"):
            await ensure_current_objectives(async_session, vault_id)
        assert water_events[1] == []
    finally:
        event.remove(async_session.sync_session, "before_commit", fail_commit)
        await async_session.rollback()
    assert await objective_crud.get_link_for_update(async_session, first_id, vault_id) is None
    await ensure_current_objectives(async_session, vault_id)
    assert len(water_events[1]) == 1
    assert water_events[1][0]["objective_id"] == str(first_id)


async def test_new_level_milestone_credits_existing_experience(async_session, vault, water_events):
    await existing_population(async_session, vault.id, 1, level=8)
    milestone = Objective(
        challenge="Reach Level 5",
        reward="10 caps",
        category="achievement",
        objective_type="reach",
        target_entity={"reach_type": "level"},
        target_amount=5,
        track_key="reach:level",
        sequence=1,
    )
    async_session.add(milestone)
    await async_session.commit()
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id)
    link = await objective_crud.get_link_for_update(async_session, milestone.id, vault.id)
    assert link.progress == 5
    assert link.reward_snapshot == "10 caps"
    assert water_events[1] == [
        {"objective_id": str(milestone.id), "challenge": "Reach Level 5", "ready_to_claim": True}
    ]
