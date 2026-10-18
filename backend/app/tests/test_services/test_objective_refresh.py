"""UTC renewals exercise real services and database state."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession

from app.core.enums import ObjectiveCategoryEnum
from app.crud.game_state import game_state_crud
from app.crud.objective import objective_crud
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.progression.objectives.refresh_service import ensure_current_objectives, objective_periods


def test_periods_are_utc_calendar_days_and_mondays():
    from datetime import timezone

    daily, weekly = objective_periods(datetime(2026, 10, 20, 1, tzinfo=timezone(timedelta(hours=3))))
    assert daily == datetime(2026, 10, 19)
    assert weekly == datetime(2026, 10, 19)


async def calendar_catalog(db, vault_id):
    for category in (ObjectiveCategoryEnum.DAILY, ObjectiveCategoryEnum.WEEKLY):
        for number in range(2):
            objective = Objective(
                challenge=f"{category} task {number}",
                reward="10 caps",
                category=category,
                objective_type="collect",
                target_entity={"resource_type": "water"},
                target_amount=100,
            )
            db.add(objective)
            if number == 0:
                db.add(
                    VaultObjectiveProgressLink(
                        vault_id=vault_id, objective_id=objective.id, total=100, progress=100, is_completed=True
                    )
                )
    await db.commit()


async def test_calendar_refresh_is_idempotent_with_raw_worker_session(async_session, vault):
    await calendar_catalog(async_session, vault.id)
    state = await game_state_crud.get_or_create(async_session, vault.id)
    state.daily_objectives_period = datetime(2026, 10, 19)
    state.weekly_objectives_period = datetime(2026, 10, 19)
    await async_session.commit()
    async with RawAsyncSession(
        bind=await async_session.connection(), expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as db:
        assert await ensure_current_objectives(db, vault.id, now=datetime(2026, 10, 20, tzinfo=UTC)) == ["daily"]
        fresh = await objective_crud.get_multi_for_vault(db, vault.id)
        daily = [row for row in fresh if row.category == "daily"]
        assert len(daily) == 2
        assert all(row.progress == 0 and not row.is_completed for row in daily)
        assert await ensure_current_objectives(db, vault.id, now=datetime(2026, 10, 20, 23, tzinfo=UTC)) == []
        assert await ensure_current_objectives(db, vault.id, now=datetime(2026, 11, 3, tzinfo=UTC)) == [
            "daily",
            "weekly",
        ]


async def test_refresh_failure_preserves_period_and_tick_state_then_retries(async_session, vault):
    from app.services.game_loop import game_loop_service

    vault_id = vault.id
    await calendar_catalog(async_session, vault_id)
    state = await game_state_crud.get_or_create(async_session, vault_id)
    old_period = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=14)
    state.daily_objectives_period = old_period
    state.weekly_objectives_period = old_period
    await async_session.commit()
    connection = await async_session.connection()
    failed = False

    def break_delete(conn, cursor, statement, parameters, context, executemany):
        nonlocal failed
        if statement.startswith("DELETE FROM vaultobjectiveprogresslink") and not failed:
            failed = True
            return "SELECT * FROM missing_refresh_table", ()
        return statement, parameters

    event.listen(connection.sync_connection, "before_cursor_execute", break_delete, retval=True)
    try:
        await game_loop_service._refresh_objectives(async_session, vault_id, state)
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", break_delete)
    assert failed
    assert state.daily_objectives_period == old_period
    assert state.total_game_time == 0
    assert await ensure_current_objectives(async_session, vault_id) == ["daily", "weekly"]


@pytest.mark.parametrize("reverse_results", [False, True])
async def test_refresh_keeps_earned_reward_snapshots_and_weekly_has_its_own_period(
    async_session, vault, reverse_results
):
    await async_session.execute(text(f"PRAGMA reverse_unordered_selects = {int(reverse_results)}"))
    try:
        await calendar_catalog(async_session, vault.id)
        daily_templates = await objective_crud.get_by_category(async_session, "daily")
        unlinked = next(template for template in daily_templates if template.challenge == "daily task 1")
        earned = VaultObjectiveProgressLink(
            vault_id=vault.id, objective_id=unlinked.id, progress=100, total=100, reward_snapshot="17 caps"
        )
        async_session.add(earned)
        state = await game_state_crud.get_or_create(async_session, vault.id)
        state.daily_objectives_period = datetime(2026, 10, 20)
        state.weekly_objectives_period = datetime(2026, 10, 12)
        await async_session.commit()
        assert await ensure_current_objectives(async_session, vault.id, now=datetime(2026, 10, 20)) == ["weekly"]
        assert await ensure_current_objectives(async_session, vault.id, now=datetime(2026, 10, 21)) == ["daily"]
        await async_session.refresh(earned)
        assert earned.progress == 100
        assert not earned.is_completed
        assert earned.reward_snapshot == "17 caps"
    finally:
        await async_session.rollback()
        await async_session.execute(text("PRAGMA reverse_unordered_selects = OFF"))


@pytest.mark.integration
async def test_concurrent_postgres_refresh_runs_only_once():
    """Opt in against an isolated verification DB; never mutate the development DB."""
    import asyncio
    from uuid import uuid4

    from sqlalchemy import delete, func, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.models.game_state import GameState
    from app.models.notification import Notification, NotificationType
    from app.models.user import User
    from app.models.vault import Vault

    uri = str(settings.ASYNC_DATABASE_URI)
    if not (make_url(uri).database or "").startswith("fallout_objectives_verify_"):
        pytest.skip("Concurrency verification requires a disposable fallout_objectives_verify_* PostgreSQL database")
    engine = create_async_engine(uri)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    user = User(username=f"objective-{uuid4().hex[:12]}", email=f"{uuid4().hex}@example.com", hashed_password="unused")
    vault = Vault(number=999, user_id=user.id)
    templates = [
        Objective(
            challenge=f"Concurrency water {n}",
            reward="10 caps",
            category="daily",
            objective_type="collect",
            target_amount=100,
            target_entity={"resource_type": "water"},
        )
        for n in range(2)
    ]
    try:
        async with maker() as db:
            db.add(user)
            await db.flush()
            db.add(vault)
            await db.flush()
            db.add_all(templates)
            db.add(
                GameState(
                    vault_id=vault.id,
                    daily_objectives_period=datetime(2026, 10, 19),
                    weekly_objectives_period=datetime(2026, 10, 19),
                )
            )
            await db.commit()

        async def refresh():
            async with maker() as db:
                return await ensure_current_objectives(db, vault.id, now=datetime(2026, 10, 20))

        results = await asyncio.gather(refresh(), refresh())
        assert sorted(results, key=len) == [[], ["daily"]]
        async with maker() as db:
            assert (
                await db.execute(
                    select(func.count())
                    .select_from(Notification)
                    .where(
                        Notification.vault_id == vault.id,
                        Notification.notification_type == NotificationType.OBJECTIVES_REFRESHED,
                    )
                )
            ).scalar_one() == 1
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
