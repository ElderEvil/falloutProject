"""Daily and weekly quest rotation: offering, rollover, in-flight survival and atomicity."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import event

from app.core.enums import QuestType, RequirementType
from app.crud.game_state import game_state_crud
from app.crud.quest import quest_crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.room import Room
from app.models.vault_quest import VaultQuestCompletionLink
from app.services.progression.quests.rotation import (
    DAILY_COUNT,
    WEEKLY_COUNT,
    ensure_current_quest_rotation,
)
from app.services.progression.quests.service import quest_service
from app.services.team_service import team_service
from app.tests.factory.rooms import create_overseers_office
from app.utils.exceptions import AccessDeniedException

MONDAY = datetime(2026, 11, 16, 12, tzinfo=UTC)
TUESDAY = datetime(2026, 11, 17, 12, tzinfo=UTC)
NEXT_MONDAY = datetime(2026, 11, 23, 12, tzinfo=UTC)


async def _seed_quests(db, quest_type: QuestType, count: int, label: str) -> list[Quest]:
    quests = [
        Quest(
            title=f"{label} {number}",
            short_description=f"{label} fixture",
            long_description=f"{label} rotation fixture quest",
            requirements="None",
            rewards="10 caps",
            quest_type=quest_type,
            duration_minutes=60,
        )
        for number in range(count)
    ]
    db.add_all(quests)
    await db.commit()
    return quests


def _add_link(db, vault_id, quest: Quest, **fields) -> VaultQuestCompletionLink:
    link = VaultQuestCompletionLink(vault_id=vault_id, quest_id=quest.id, **fields)
    db.add(link)
    return link


async def _seed_pools(db) -> list[Quest]:
    daily = await _seed_quests(db, QuestType.DAILY, DAILY_COUNT, "Daily")
    weekly = await _seed_quests(db, QuestType.REPEATABLE, WEEKLY_COUNT, "Weekly")
    return daily + weekly


async def test_rotation_calendar_scenarios(async_session, vault):
    """One calendar walk: first offer, same-period no-op, daily rollover, Monday rollover."""
    quests = await _seed_pools(async_session)

    offered = await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY)
    assert offered == DAILY_COUNT + WEEKLY_COUNT
    state = await game_state_crud.get_by_vault_id(async_session, vault.id)
    assert state is not None
    assert state.daily_quests_period == datetime(2026, 11, 16, tzinfo=UTC)
    assert state.weekly_quests_period == datetime(2026, 11, 16, tzinfo=UTC)
    links = await quest_crud.get_links_for_quest_ids(async_session, vault.id, [quest.id for quest in quests])
    assert len(links) == DAILY_COUNT + WEEKLY_COUNT
    assert all(link.is_visible and not link.is_completed and link.started_at is None for link in links)

    claimed = await quest_crud.get_link(async_session, quest_id=quests[0].id, vault_id=vault.id)
    assert claimed is not None
    claimed.is_completed = True
    await async_session.commit()
    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == 0
    await async_session.refresh(state)
    await async_session.refresh(claimed)
    assert state.daily_quests_period == datetime(2026, 11, 16, tzinfo=UTC)
    assert state.weekly_quests_period == datetime(2026, 11, 16, tzinfo=UTC)
    assert claimed.is_completed

    assert await ensure_current_quest_rotation(async_session, vault.id, now=TUESDAY) == DAILY_COUNT
    await async_session.refresh(state)
    await async_session.refresh(claimed)
    assert state.daily_quests_period == datetime(2026, 11, 17, tzinfo=UTC)
    assert state.weekly_quests_period == datetime(2026, 11, 16, tzinfo=UTC)
    assert not claimed.is_completed

    assert await ensure_current_quest_rotation(async_session, vault.id, now=NEXT_MONDAY) == DAILY_COUNT + WEEKLY_COUNT
    await async_session.refresh(state)
    assert state.daily_quests_period == datetime(2026, 11, 23, tzinfo=UTC)
    assert state.weekly_quests_period == datetime(2026, 11, 23, tzinfo=UTC)


async def test_empty_pool_retries_after_the_catalog_is_seeded(async_session, vault):
    await _seed_quests(async_session, QuestType.DAILY, DAILY_COUNT, "Daily")

    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == DAILY_COUNT
    state = await game_state_crud.get_by_vault_id(async_session, vault.id)
    assert state is not None
    assert state.daily_quests_period == datetime(2026, 11, 16, tzinfo=UTC)
    assert state.weekly_quests_period is None

    await _seed_quests(async_session, QuestType.REPEATABLE, WEEKLY_COUNT, "Weekly")
    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == WEEKLY_COUNT
    await async_session.refresh(state)
    assert state.weekly_quests_period == datetime(2026, 11, 16, tzinfo=UTC)


async def test_populated_pool_records_its_period_even_with_zero_offers(async_session, vault):
    """A populated but fully settled pool records the period: no mid-period re-roll later."""
    daily = await _seed_quests(async_session, QuestType.DAILY, DAILY_COUNT, "Daily")
    for quest in daily:
        _add_link(async_session, vault.id, quest, is_visible=True, started_at=MONDAY, duration_minutes=60)
    await async_session.commit()

    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == 0
    state = await game_state_crud.get_by_vault_id(async_session, vault.id)
    assert state is not None
    assert state.daily_quests_period == datetime(2026, 11, 16, tzinfo=UTC)

    # A later trigger in the same period must not re-roll the settled pool.
    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == 0
    await async_session.refresh(state)
    assert state.daily_quests_period == datetime(2026, 11, 16, tzinfo=UTC)
    assert state.weekly_quests_period is None  # The weekly catalog is empty: still deferred.


async def test_completed_daily_is_reset_and_can_be_started_again(async_session, vault):
    daily = await _seed_quests(async_session, QuestType.DAILY, DAILY_COUNT, "Daily")
    async_session.add(Room(**create_overseers_office(), vault_id=vault.id))
    dweller = Dweller(first_name="Rotating", gender="male", rarity="common", level=1, vault_id=vault.id)
    async_session.add(dweller)
    spent = _add_link(
        async_session,
        vault.id,
        daily[0],
        is_visible=True,
        is_completed=True,
        completed_at=MONDAY,
        started_at=MONDAY,
        duration_minutes=60,
        granted_rewards=[{"reward_type": "caps", "amount": 10}],
    )
    await async_session.commit()

    # Real clock: the offer-period guard in start_quest compares against utcnow().
    assert await ensure_current_quest_rotation(async_session, vault.id) == DAILY_COUNT

    await async_session.refresh(spent)
    assert not spent.is_completed
    assert spent.completed_at is None
    assert spent.granted_rewards is None
    assert spent.started_at is None
    assert spent.is_visible

    await team_service.assign_quest_team(async_session, daily[0].id, vault.id, [dweller.id])
    started = await quest_service.start_quest(async_session, daily[0].id, vault.id)
    assert started.started_at is not None


@pytest.mark.parametrize(
    "link_fields",
    [
        {"started_at": MONDAY, "duration_minutes": 60},
        {"started_at": MONDAY, "return_started_at": MONDAY, "return_completes_at": TUESDAY, "duration_minutes": 60},
        {"is_reward_ready": True, "granted_rewards": [{"reward_type": "caps", "amount": 10}]},
    ],
    ids=["active", "returning", "reward-ready"],
)
async def test_rotation_preserves_unsettled_links_and_excludes_them_from_the_new_draw(
    async_session, vault, link_fields
):
    daily = await _seed_quests(async_session, QuestType.DAILY, DAILY_COUNT + 1, "Daily")
    flying = _add_link(async_session, vault.id, daily[0], **link_fields)
    await async_session.commit()
    expected = flying.model_dump() | {"is_visible": True}

    assert await ensure_current_quest_rotation(async_session, vault.id, now=TUESDAY) == DAILY_COUNT

    await async_session.refresh(flying)
    assert flying.model_dump() == expected
    others = await quest_crud.get_links_for_quest_ids(async_session, vault.id, [quest.id for quest in daily[1:]])
    assert len(others) == DAILY_COUNT
    assert sum(link.is_visible for link in others) == DAILY_COUNT
    assert all(link.started_at is None for link in others)


async def test_side_and_main_quests_are_never_touched(async_session, vault):
    side = (await _seed_quests(async_session, QuestType.SIDE, 1, "Side"))[0]
    main = (await _seed_quests(async_session, QuestType.MAIN, 1, "Main"))[0]
    await _seed_quests(async_session, QuestType.DAILY, DAILY_COUNT, "Daily")
    side_link = _add_link(async_session, vault.id, side, is_visible=True, is_completed=True, completed_at=MONDAY)
    main_link = _add_link(async_session, vault.id, main, is_visible=True)
    await async_session.commit()
    expected = (side_link.model_dump(), main_link.model_dump())

    assert await ensure_current_quest_rotation(async_session, vault.id, now=TUESDAY) == DAILY_COUNT

    for link, before in zip((side_link, main_link), expected, strict=True):
        await async_session.refresh(link)
        assert link.model_dump() == before


async def test_available_only_and_start_gate_exclude_rotated_out_quests(async_session, vault):
    await _seed_quests(async_session, QuestType.DAILY, DAILY_COUNT + 2, "Daily")
    async_session.add(Room(**create_overseers_office(), vault_id=vault.id))
    await async_session.commit()

    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == DAILY_COUNT

    available = await quest_service.get_quests_for_vault(async_session, vault.id, available_only=True)
    assert len(available) == DAILY_COUNT
    full = await quest_service.get_quests_for_vault(async_session, vault.id)
    assert len(full) == DAILY_COUNT + 2
    hidden = [quest_read for quest_read in full if not quest_read.is_visible]
    assert len(hidden) == 2
    assert {quest_read.id for quest_read in available}.isdisjoint({quest_read.id for quest_read in hidden})

    with pytest.raises(AccessDeniedException):
        await quest_service.start_quest(async_session, hidden[0].id, vault.id)


async def test_rotation_skips_quests_beyond_the_reveal_window(async_session, vault):
    eligible = await _seed_quests(async_session, QuestType.DAILY, DAILY_COUNT, "Daily")
    gated = Quest(
        title="Daily Deep",
        short_description="Deep fixture",
        long_description="Level-gated rotation fixture quest",
        requirements="Level 50 dwellers",
        rewards="10 caps",
        quest_type=QuestType.DAILY,
        duration_minutes=60,
        quest_requirements=[
            QuestRequirement(requirement_type=RequirementType.LEVEL, requirement_data={"level": 50}, is_mandatory=True)
        ],
    )
    async_session.add(gated)
    await async_session.commit()

    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == DAILY_COUNT

    links = await quest_crud.get_links_for_quest_ids(
        async_session, vault.id, [quest.id for quest in eligible] + [gated.id]
    )
    by_id = {link.quest_id: link for link in links}
    assert all(by_id[quest.id].is_visible for quest in eligible)
    assert by_id[gated.id].is_visible is False


async def test_failed_roll_persists_nothing(async_session, vault):
    quests = await _seed_pools(async_session)
    vault_id = vault.id
    claimed = _add_link(
        async_session,
        vault_id,
        quests[0],
        is_visible=True,
        is_completed=True,
        completed_at=MONDAY,
        started_at=MONDAY,
        granted_rewards=[{"reward_type": "caps", "amount": 10}],
    )
    state = await game_state_crud.get_or_create(async_session, vault_id)
    await async_session.commit()
    before = claimed.model_dump()
    unlinked_daily_id, weekly_id = quests[1].id, quests[-1].id
    connection = (await async_session.connection()).sync_connection
    insert_count = 0

    def fail_weekly_insert(_conn, _cursor, statement, _params, _context, _executemany):
        nonlocal insert_count
        if statement.startswith("INSERT INTO vaultquestcompletionlink"):
            insert_count += 1
            if insert_count == 2:
                raise RuntimeError("weekly link insert failed")

    event.listen(connection, "before_cursor_execute", fail_weekly_insert)
    try:
        with pytest.raises(RuntimeError, match="weekly link insert failed"):
            await ensure_current_quest_rotation(async_session, vault_id, now=MONDAY)
        assert await quest_crud.get_link(async_session, quest_id=unlinked_daily_id, vault_id=vault_id) is not None
    finally:
        event.remove(connection, "before_cursor_execute", fail_weekly_insert)

    await async_session.rollback()
    await async_session.refresh(claimed)
    await async_session.refresh(state)
    assert claimed.model_dump() == before
    assert not await quest_crud.get_links_for_quest_ids(async_session, vault_id, [unlinked_daily_id, weekly_id])
    assert state.daily_quests_period is None
    assert state.weekly_quests_period is None


async def test_tick_hook_recovers_from_failure_and_rotates_next_tick(async_session, vault, monkeypatch):
    from app.services.game_loop_service import game_loop_service
    from app.services.progression.quests import rotation

    vault_id = vault.id
    await _seed_pools(async_session)
    state = await game_state_crud.get_or_create(async_session, vault_id)
    await async_session.commit()

    original = rotation._roll_pool
    calls = 0

    async def fail_once(db_session, vault_id, quest_type, count, reveal_threshold):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("tick rotation failure")
        return await original(db_session, vault_id, quest_type, count, reveal_threshold)

    monkeypatch.setattr(rotation, "_roll_pool", fail_once)
    await game_loop_service._rotate_quests(async_session, vault_id, state)
    await async_session.refresh(state)
    assert state.daily_quests_period is None

    await game_loop_service._rotate_quests(async_session, vault_id, state)
    await async_session.refresh(state)
    assert state.daily_quests_period is not None
    assert state.weekly_quests_period is not None


async def test_rotation_sweep_finishes_other_vaults_then_fails_retryably(async_session, vault, monkeypatch):
    """The midnight actor keeps rotating the other vaults, then raises so Dramatiq retries."""
    import uuid as uuid_module
    from contextlib import asynccontextmanager

    from app.api import tasks
    from app.crud.vault import vault as vault_crud
    from app.services.progression.quests import rotation as rotation_module

    first = vault.id  # Captured early: the sweep's session recovery expires loaded rows.

    @asynccontextmanager
    async def fake_task_session():
        yield async_session

    monkeypatch.setattr(tasks, "task_session", lambda: fake_task_session())

    stuck = uuid_module.UUID("00000000-0000-0000-0000-0000000000aa")
    calls: list[UUID] = []

    async def rolling(db, vault_id):
        calls.append(vault_id)
        if vault_id == first:
            raise RuntimeError("vault rotation failed")
        return 0

    monkeypatch.setattr(rotation_module, "ensure_current_quest_rotation", rolling)

    async def two_vaults(session):
        return [first, stuck]

    monkeypatch.setattr(vault_crud, "get_non_deleted_ids", two_vaults)

    with pytest.raises(RuntimeError, match="Quest rotation failed for vaults"):
        await tasks._refresh_quest_rotation()
    assert calls == [first, stuck]
