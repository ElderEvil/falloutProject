from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import event

from app import crud
from app.api import tasks
from app.core.enums import QuestType, RequirementType
from app.crud.game_state import game_state_crud
from app.crud.quest import quest_crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.quest_requirement import QuestRequirement
from app.models.room import Room
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.game_loop_service import game_loop_service
from app.services.progression.quests.rotation import DAILY_COUNT, WEEKLY_COUNT, ensure_current_quest_rotation
from app.services.progression.quests.service import quest_service
from app.services.team_service import team_service
from app.tests.factory.rooms import create_overseers_office
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import AccessDeniedException

pytestmark = pytest.mark.asyncio

MONDAY = datetime(2026, 11, 16, 12, tzinfo=UTC)
TUESDAY = datetime(2026, 11, 17, 12, tzinfo=UTC)
NEXT_MONDAY = datetime(2026, 11, 23, 12, tzinfo=UTC)
MONDAY_PERIOD = datetime(2026, 11, 16, tzinfo=UTC)
TUESDAY_PERIOD = datetime(2026, 11, 17, tzinfo=UTC)
NEXT_MONDAY_PERIOD = datetime(2026, 11, 23, tzinfo=UTC)
INSERT_LINK = "INSERT INTO vaultquestcompletionlink"


def _base(**kw) -> dict:
    base = {
        "title": "Quest",
        "short_description": "Test",
        "long_description": "Test quest",
        "requirements": "None",
        "rewards": "10 caps",
    }
    return base | kw


async def _seed_quests(db, quest_type: QuestType, count: int, label: str) -> list[Quest]:
    quests = [Quest(**_base(title=f"{label} {number}", quest_type=quest_type)) for number in range(count)]
    db.add_all(quests)
    await db.commit()
    return quests


def _add_link(db, vault_id, quest: Quest, **fields) -> VaultQuestCompletionLink:
    link = VaultQuestCompletionLink(vault_id=vault_id, quest_id=quest.id, **fields)
    db.add(link)
    return link


async def _seed_pools(db) -> list[Quest]:
    return await _seed_quests(db, QuestType.DAILY, DAILY_COUNT, "Daily") + await _seed_quests(
        db, QuestType.REPEATABLE, WEEKLY_COUNT, "Weekly"
    )


def _assert_periods(state, daily, weekly) -> None:
    assert (state.daily_quests_period, state.weekly_quests_period) == (daily, weekly)


async def _state(async_session, vault):
    state = await game_state_crud.get_by_vault_id(async_session, vault.id)
    assert state is not None
    return state


def _fail_insert(bind, nth: int, message: str):
    calls = 0

    def listener(_conn, _cursor, statement, _params, _context, _executemany):
        nonlocal calls
        if statement.startswith(INSERT_LINK):
            calls += 1
            if calls == nth:
                raise RuntimeError(message)

    event.listen(bind, "before_cursor_execute", listener)
    return listener


async def test_rotation_calendar_scenarios(async_session, vault):
    quests = await _seed_pools(async_session)
    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == DAILY_COUNT + WEEKLY_COUNT
    state = await _state(async_session, vault)
    _assert_periods(state, MONDAY_PERIOD, MONDAY_PERIOD)
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
    _assert_periods(state, MONDAY_PERIOD, MONDAY_PERIOD)
    assert claimed.is_completed
    assert await ensure_current_quest_rotation(async_session, vault.id, now=TUESDAY) == DAILY_COUNT
    await async_session.refresh(state)
    await async_session.refresh(claimed)
    _assert_periods(state, TUESDAY_PERIOD, MONDAY_PERIOD)
    assert not claimed.is_completed
    assert await ensure_current_quest_rotation(async_session, vault.id, now=NEXT_MONDAY) == DAILY_COUNT + WEEKLY_COUNT
    await async_session.refresh(state)
    _assert_periods(state, NEXT_MONDAY_PERIOD, NEXT_MONDAY_PERIOD)


async def test_empty_pool_retries_after_the_catalog_is_seeded(async_session, vault):
    await _seed_quests(async_session, QuestType.DAILY, DAILY_COUNT, "Daily")
    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == DAILY_COUNT
    state = await _state(async_session, vault)
    _assert_periods(state, MONDAY_PERIOD, None)
    await _seed_quests(async_session, QuestType.REPEATABLE, WEEKLY_COUNT, "Weekly")
    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == WEEKLY_COUNT
    await async_session.refresh(state)
    assert state.weekly_quests_period == MONDAY_PERIOD


async def test_populated_pool_records_its_period_even_with_zero_offers(async_session, vault):
    daily = await _seed_quests(async_session, QuestType.DAILY, DAILY_COUNT, "Daily")
    for quest in daily:
        _add_link(async_session, vault.id, quest, is_visible=True, started_at=MONDAY, duration_minutes=60)
    await async_session.commit()
    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == 0
    state = await _state(async_session, vault)
    assert state.daily_quests_period == MONDAY_PERIOD
    # A later trigger in the same period must not re-roll the settled pool.
    assert await ensure_current_quest_rotation(async_session, vault.id, now=MONDAY) == 0
    await async_session.refresh(state)
    _assert_periods(state, MONDAY_PERIOD, None)  # The weekly catalog is empty: still deferred.


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
    assert (spent.is_completed, spent.completed_at, spent.granted_rewards, spent.started_at, spent.is_visible) == (
        False,
        None,
        None,
        None,
        True,
    )
    await team_service.assign_quest_team(async_session, daily[0].id, vault.id, [dweller.id])
    assert (await quest_service.start_quest(async_session, daily[0].id, vault.id)).started_at is not None


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
        **_base(
            title="Daily Deep",
            quest_type=QuestType.DAILY,
            quest_requirements=[
                QuestRequirement(
                    requirement_type=RequirementType.LEVEL, requirement_data={"level": 50}, is_mandatory=True
                )
            ],
        )
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
    listener = _fail_insert(connection, 2, "weekly link insert failed")
    try:
        with pytest.raises(RuntimeError, match="weekly link insert failed"):
            await ensure_current_quest_rotation(async_session, vault_id, now=MONDAY)
        assert await quest_crud.get_link(async_session, quest_id=unlinked_daily_id, vault_id=vault_id) is not None
    finally:
        event.remove(connection, "before_cursor_execute", listener)
    await async_session.rollback()
    await async_session.refresh(claimed)
    await async_session.refresh(state)
    assert claimed.model_dump() == before
    assert not await quest_crud.get_links_for_quest_ids(async_session, vault_id, [unlinked_daily_id, weekly_id])
    assert (state.daily_quests_period, state.weekly_quests_period) == (None, None)


async def test_tick_hook_recovers_from_failure_and_rotates_next_tick(async_session, vault):
    vault_id = vault.id
    await _seed_pools(async_session)
    state = await game_state_crud.get_or_create(async_session, vault_id)
    await async_session.commit()
    engine = async_session.get_bind().engine
    # Statement-boundary fault: the first link insert fails, the recovery write succeeds.
    listener = _fail_insert(engine, 1, "tick rotation failure")
    try:
        await game_loop_service._rotate_quests(async_session, vault_id, state)
        await async_session.refresh(state)
        assert state.daily_quests_period is None
        await game_loop_service._rotate_quests(async_session, vault_id, state)
        await async_session.refresh(state)
        assert state.daily_quests_period is not None
        assert state.weekly_quests_period is not None
    finally:
        event.remove(engine, "before_cursor_execute", listener)


async def test_rotation_sweep_finishes_other_vaults_then_fails_retryably(async_session, vault, monkeypatch):
    first = vault.id  # Captured early: the sweep's session recovery expires loaded rows.
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    second = await crud.vault.create(
        async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id)
    )
    ids = [quest.id for quest in await _seed_pools(async_session)]

    @asynccontextmanager
    async def fake_task_session():
        yield async_session

    monkeypatch.setattr(tasks, "task_session", lambda: fake_task_session())
    # One-shot fault on the sweep's first link insert; the vault it belonged to is captured so the
    # rollback assertions stay order-independent.
    failing_hex: str | None = None

    def fail_first_vault_insert(conn, cursor, statement, parameters, context, executemany):
        nonlocal failing_hex
        if failing_hex is not None or not statement.startswith(INSERT_LINK):
            return
        # asyncpg renders uuid params in the compact hex form; the first param is vault_id.
        rows = parameters if isinstance(parameters, list) else [parameters]
        first_row = next((row for row in rows if row), None)
        failing_hex = str(first_row[0]) if isinstance(first_row, tuple) else ""
        raise RuntimeError("vault rotation failure")

    engine = async_session.get_bind().engine
    event.listen(engine, "before_cursor_execute", fail_first_vault_insert)
    try:
        with pytest.raises(RuntimeError, match="Quest rotation failed for vaults"):
            await tasks._refresh_quest_rotation()
    finally:
        event.remove(engine, "before_cursor_execute", fail_first_vault_insert)
    assert failing_hex is not None
    failing = next(v for v in (first, second.id) if v.hex == failing_hex)
    rotating = second.id if failing == first else first
    # The failing vault rolled back entirely, so its retry starts from a clean slate.
    assert await quest_crud.get_links_for_quest_ids(async_session, failing, ids) == []
    assert await game_state_crud.get_by_vault_id(async_session, failing) is None
    assert len(await quest_crud.get_links_for_quest_ids(async_session, rotating, ids)) == DAILY_COUNT + WEEKLY_COUNT
    rotating_state = await game_state_crud.get_by_vault_id(async_session, rotating)
    assert (rotating_state is not None, rotating_state.daily_quests_period is not None) == (True, True)
