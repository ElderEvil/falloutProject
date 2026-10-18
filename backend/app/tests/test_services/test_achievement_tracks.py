"""Staged achievements exercise real services and database state."""

from contextlib import asynccontextmanager

import pytest
from sqlalchemy import event

from app.core.event_bus import EventBus, GameEvent
from app.crud.objective import objective_crud
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.progression.objectives.assignment import ObjectiveAssignmentService
from app.services.progression.objectives.evaluators.base import current_session_maker
from app.services.progression.objectives.evaluators.concrete import CollectEvaluator
from app.services.rewards.settlement import claim_objective_reward
from app.utils.exceptions import ResourceConflictException


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

    @asynccontextmanager
    async def scope():
        yield async_session

    token = current_session_maker.set(scope)
    yield bus, notifications
    current_session_maker.reset(token)


async def test_achievement_unlocks_on_earning_at_zero_and_claims_stay_independent(async_session, vault, water_events):
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
    assert links[stages[1].id].progress == 0
    assert stages[2].id not in links
    assert notifications[0]["next_achievement"] == "Collect 500 Water"
    await bus.emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "water", "amount": 60})
    await claim_objective_reward(async_session, stages[0].id, vault.id)
    with pytest.raises(ResourceConflictException):
        await claim_objective_reward(async_session, stages[0].id, vault.id)
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
    assert hidden.progress == 0
    assert not hidden.is_locked
    pending = await objective_crud.get_link_for_update(async_session, stages[2].id, vault.id)
    assert pending.reward_snapshot == "7 caps"
    assert not pending.is_completed


async def test_final_stage_can_be_claimed_before_older_rewards(async_session, vault, water_events):
    stages = await water_stages(async_session)
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id, auto_commit=False)
    await async_session.commit()
    for amount in (100, 500, 1500):
        await water_events[0].emit(GameEvent.RESOURCE_COLLECTED, vault.id, {"resource_type": "water", "amount": amount})
    links = await objective_crud.get_links_for_vault(async_session, vault.id)
    assert len(links) == 3
    assert all(link.progress == link.total and not link.is_completed for link in links)
    assert "next_achievement" not in water_events[1][-1]
    await claim_objective_reward(async_session, stages[2].id, vault.id)
    first = await objective_crud.get_link_for_update(async_session, stages[0].id, vault.id)
    assert not first.is_completed
    assert first.reward_snapshot == "10 caps"


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
    second = await objective_crud.get_link_for_update(async_session, stages[1].id, vault.id)
    assert second.progress == 1
    assert second.credited_dweller_ids == [dweller_id]


async def test_stage_unlock_database_failure_rolls_back_completion(async_session, vault, water_events):
    stages = await water_stages(async_session)
    await ObjectiveAssignmentService(async_session).assign_achievement_objectives(vault.id, auto_commit=False)
    await async_session.commit()
    vault_id, first_id, next_id = vault.id, stages[0].id, stages[1].id
    connection = await async_session.connection()

    def break_unlock(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO vaultobjectiveprogresslink"):
            return "SELECT * FROM missing_unlock_table", ()
        return statement, parameters

    event.listen(connection.sync_connection, "before_cursor_execute", break_unlock, retval=True)
    try:
        await water_events[0].emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"resource_type": "water", "amount": 100})
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", break_unlock)
    assert not water_events[1]
    first = await objective_crud.get_link_for_update(async_session, first_id, vault_id)
    assert first.progress == 0
    assert first.reward_snapshot is None
    assert await objective_crud.get_link_for_update(async_session, next_id, vault_id) is None
    await water_events[0].emit(GameEvent.RESOURCE_COLLECTED, vault_id, {"resource_type": "water", "amount": 100})
    assert first.progress == 100
    assert (await objective_crud.get_link_for_update(async_session, next_id, vault_id)).progress == 0


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
