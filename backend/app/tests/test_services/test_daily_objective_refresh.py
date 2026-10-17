"""Issue #1042 — the momentum wall: dailies that never come back.

The starter arc stalls at seq 5 (~3,500-cap wall) partly because the "daily"
objective claimed once never regenerates in game time. Fix under test: the
game loop refreshes the daily category for a vault whose tick crosses the
configured boundary in *game time* — a caps drip that works for vaults that
never tick across a wall-clock midnight.
"""

from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ObjectiveCategoryEnum
from app.crud.objective import objective_crud
from app.models.vault_objective import VaultObjectiveProgressLink
from app.schemas.vault import VaultNumber
from app.services.progression.objectives.evaluators import evaluator_manager
from app.services.progression.objectives.evaluators.base import current_session_maker
from app.services.vault_service import vault_service
from app.tests.factory.vaults import random_vault_number
from app.utils.seed_objectives import seed_objectives_from_json


@pytest.fixture
def objective_events(async_session):
    """Bind real event handlers to this test's SQLite transaction."""

    @asynccontextmanager
    async def session_scope():
        yield async_session

    token = current_session_maker.set(session_scope)
    was_initialized = evaluator_manager.is_initialized
    evaluator_manager.initialize()
    yield
    if not was_initialized:
        evaluator_manager.shutdown()
    current_session_maker.reset(token)


@pytest_asyncio.fixture
async def fresh_vault(async_session: AsyncSession, superuser):
    return await vault_service.initiate_vault(
        async_session,
        VaultNumber(number=random_vault_number()),
        superuser.id,
    )


async def _daily_links(async_session: AsyncSession, vault_id) -> list[VaultObjectiveProgressLink]:
    daily_ids = {o.id for o in await objective_crud.get_by_category(async_session, ObjectiveCategoryEnum.DAILY)}
    return [
        link
        for link in await objective_crud.get_links_for_vault(async_session, vault_id)
        if link.objective_id in daily_ids
    ]


@pytest.mark.asyncio
async def test_new_vault_gets_one_daily(async_session, fresh_vault, objective_events) -> None:
    await seed_objectives_from_json(async_session)
    await objective_crud.assign_initial(async_session, fresh_vault.id, is_boosted=False)
    links = await _daily_links(async_session, fresh_vault.id)
    assert len(links) == 1
    assert not links[0].is_completed


@pytest.mark.asyncio
async def test_daily_refresh_replaces_completed_daily(async_session, fresh_vault, objective_events) -> None:
    from app.services.progression.objectives.assignment import ObjectiveAssignmentService

    await seed_objectives_from_json(async_session)
    await objective_crud.assign_initial(async_session, fresh_vault.id, is_boosted=False)

    links = await _daily_links(async_session, fresh_vault.id)
    assert len(links) == 1
    links[0].is_completed = True
    async_session.add(links[0])
    await async_session.commit()

    service = ObjectiveAssignmentService(async_session)
    await service.refresh_daily_objectives(fresh_vault.id)

    fresh = await _daily_links(async_session, fresh_vault.id)
    assert len(fresh) == ObjectiveAssignmentService.DAILY_COUNT
    assert all(not link.is_completed for link in fresh)


@pytest.mark.asyncio
async def test_game_loop_refreshes_daily_after_configured_hours(async_session, fresh_vault, objective_events):
    """The tick hook refreshes dailies once game time crosses the daily boundary."""
    from unittest.mock import patch

    from app.core.game_config import game_config
    from app.services.game_loop import game_loop_service

    await seed_objectives_from_json(async_session)
    await objective_crud.assign_initial(async_session, fresh_vault.id, is_boosted=False)

    links = await _daily_links(async_session, fresh_vault.id)
    assert len(links) == 1
    links[0].is_completed = True
    async_session.add(links[0])
    await async_session.commit()

    game_state = await game_loop_service._get_or_create_game_state(async_session, fresh_vault.id)
    daily_boundary = game_config.objectives.daily_refresh_game_hours * 3600

    # One tick under the boundary: no refresh, the claimed daily stays.
    game_state.total_game_time = daily_boundary - 60
    await game_loop_service._maybe_refresh_objectives(async_session, fresh_vault.id, game_state)
    still = await _daily_links(async_session, fresh_vault.id)
    assert len(still) == 1
    assert still[0].is_completed

    # Crossing the boundary: the claimed daily is replaced by fresh ones.
    game_state.total_game_time = daily_boundary
    await game_loop_service._maybe_refresh_objectives(async_session, fresh_vault.id, game_state)
    refreshed = await _daily_links(async_session, fresh_vault.id)
    assert refreshed
    assert all(not link.is_completed for link in refreshed)
    assert links[0].objective_id not in {link.objective_id for link in refreshed}
