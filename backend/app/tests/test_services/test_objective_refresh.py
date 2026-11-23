import asyncio
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.enums import NotificationType, ObjectiveCategoryEnum
from app.crud.game_state import game_state_crud
from app.crud.objective import objective_crud
from app.models.game_state import GameState
from app.models.notification import Notification
from app.models.objective import Objective
from app.models.user import User
from app.models.vault import Vault
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.game_loop_service import game_loop_service
from app.services.progression.objectives.refresh_service import ensure_current_objectives as _ensure
from app.services.progression.objectives.refresh_service import objective_periods
from app.utils.time import utcnow

WATER = {"resource_type": "water"}
OCT19 = datetime(2026, 10, 19, tzinfo=UTC)
D20 = datetime(2026, 10, 20, tzinfo=UTC)


def _template(category, number):
    return Objective(
        challenge=f"{category} task {number}",
        reward="10 caps",
        category=category,
        objective_type="collect",
        target_entity=WATER,
        target_amount=100,
    )


def test_periods_are_utc_calendar_days_and_mondays():
    daily, weekly = objective_periods(datetime(2026, 10, 20, 1, tzinfo=timezone(timedelta(hours=3))))
    assert daily == OCT19
    assert weekly == OCT19


async def _catalog(db, vault_id, daily=None, weekly=None):
    for category in (ObjectiveCategoryEnum.DAILY, ObjectiveCategoryEnum.WEEKLY):
        first, second = [_template(category, n) for n in range(2)]
        earned = VaultObjectiveProgressLink(
            vault_id=vault_id, objective_id=first.id, total=100, progress=100, is_completed=True
        )
        db.add_all([first, second, earned])
    state = await game_state_crud.get_or_create(db, vault_id)
    state.daily_objectives_period, state.weekly_objectives_period = daily, weekly
    await db.commit()
    return state


async def test_calendar_refresh_is_idempotent_with_raw_worker_session(async_session, vault):
    db, vault_id = async_session, vault.id
    await _catalog(db, vault_id, daily=OCT19, weekly=OCT19)
    async with RawAsyncSession(
        bind=await db.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as worker:
        assert await _ensure(worker, vault_id, now=D20) == ["daily"]
        daily = [r for r in await objective_crud.get_multi_for_vault(worker, vault_id) if r.category == "daily"]
        assert len(daily) == 2
        assert all(row.progress == 0 and not row.is_completed for row in daily)
        assert await _ensure(worker, vault_id, now=datetime(2026, 10, 20, 23, tzinfo=UTC)) == []
        assert await _ensure(worker, vault_id, now=datetime(2026, 11, 3, tzinfo=UTC)) == ["daily", "weekly"]


async def test_refresh_failure_preserves_period_and_tick_state_then_retries(async_session, vault):
    db, vault_id = async_session, vault.id
    old_period = utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=14)
    state = await _catalog(db, vault_id, daily=old_period, weekly=old_period)
    connection = await db.connection()
    failed = False

    def break_delete(conn, cursor, statement, parameters, context, executemany):
        nonlocal failed
        if statement.startswith("DELETE FROM vaultobjectiveprogresslink") and not failed:
            failed = True
            return "SELECT * FROM missing_refresh_table", ()
        return statement, parameters

    event.listen(connection.sync_connection, "before_cursor_execute", break_delete, retval=True)
    try:
        await game_loop_service._refresh_objectives(db, vault_id, state)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", break_delete)
    assert failed
    assert state.daily_objectives_period == old_period
    assert state.total_game_time == 0
    assert await _ensure(db, vault_id) == ["daily", "weekly"]


@pytest.mark.parametrize("reverse_results", [False, True])
async def test_refresh_keeps_earned_reward_snapshots_and_weekly_has_its_own_period(
    async_session, vault, reverse_results
):
    db, vault_id = async_session, vault.id
    await db.execute(text(f"PRAGMA reverse_unordered_selects = {int(reverse_results)}"))
    try:
        await _catalog(db, vault_id, daily=D20, weekly=datetime(2026, 10, 12, tzinfo=UTC))
        templates = await objective_crud.get_by_category(db, "daily")
        template = next(t for t in templates if t.challenge == "daily task 1")
        earned = VaultObjectiveProgressLink(
            vault_id=vault_id, objective_id=template.id, progress=100, total=100, reward_snapshot="17 caps"
        )
        db.add(earned)
        await db.commit()
        assert await _ensure(db, vault_id, now=D20) == ["weekly"]
        assert await _ensure(db, vault_id, now=datetime(2026, 10, 21, tzinfo=UTC)) == ["daily"]
        await db.refresh(earned)
        assert earned.progress == 100
        assert not earned.is_completed
        assert earned.reward_snapshot == "17 caps"
    finally:
        await db.rollback()
        await db.execute(text("PRAGMA reverse_unordered_selects = OFF"))


@pytest.mark.integration
async def test_concurrent_postgres_refresh_runs_only_once():
    # Opt in against an isolated verification DB; never mutate the development DB.
    uri = str(settings.ASYNC_DATABASE_URI)
    if not (make_url(uri).database or "").startswith("fallout_objectives_verify_"):
        pytest.skip("Concurrency verification requires a disposable fallout_objectives_verify_* PostgreSQL database")
    engine = create_async_engine(uri)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    user = User(username=f"objective-{uuid4().hex[:12]}", email=f"{uuid4().hex}@example.com", hashed_password="unused")
    vault = Vault(number=999, user_id=user.id)
    templates = [_template("daily", n) for n in range(2)]

    async def refresh():
        async with maker() as db:
            return await _ensure(db, vault.id, now=D20)

    try:
        async with maker() as db:
            db.add(user)
            await db.flush()
            db.add(vault)
            await db.flush()
            db.add_all(templates)
            db.add(GameState(vault_id=vault.id, daily_objectives_period=OCT19, weekly_objectives_period=OCT19))
            await db.commit()
        results = await asyncio.gather(refresh(), refresh())
        assert sorted(results, key=len) == [[], ["daily"]]
        async with maker() as db:
            query = (
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.vault_id == vault.id,
                    Notification.notification_type == NotificationType.OBJECTIVES_REFRESHED,
                )
            )
            assert (await db.execute(query)).scalar_one() == 1
    finally:
        async with maker() as db:
            for model, condition in (
                (Notification, Notification.vault_id == vault.id),
                (VaultObjectiveProgressLink, VaultObjectiveProgressLink.vault_id == vault.id),
                (GameState, GameState.vault_id == vault.id),
                (Vault, Vault.id == vault.id),
                (User, User.id == user.id),
                (Objective, Objective.id.in_([o.id for o in templates])),
            ):
                await db.execute(delete(model).where(condition))
            await db.commit()
        await engine.dispose()
