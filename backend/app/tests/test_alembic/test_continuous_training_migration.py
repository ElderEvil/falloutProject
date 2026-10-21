"""Existing vaults retain single-round training after the migration."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.tests.test_alembic import test_data_migrations as legacy

harness = legacy.harness


def test_continuous_training_upgrade_preserves_existing_behavior():
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_23_0002-f2a7c9d4e810_continuous_training.py"
    spec = importlib.util.spec_from_file_location("continuous_training_migration", path)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE vault (id INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO vault (id) VALUES (1)"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert connection.execute(text("SELECT continuous_training FROM vault WHERE id = 1")).scalar() == 0
                connection.execute(text("INSERT INTO vault (id) VALUES (2)"))
                assert connection.execute(text("SELECT continuous_training FROM vault WHERE id = 2")).scalar() == 0
                connection.execute(text("UPDATE vault SET continuous_training = 1 WHERE id = 1"))
                migration.downgrade()
                assert [column["name"] for column in inspect(connection).get_columns("vault")] == ["id"]
                assert connection.execute(text("SELECT COUNT(*) FROM vault")).scalar() == 2
    finally:
        engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("other_operation", ["complete", "goal"])
def test_concurrent_completions_create_only_one_successor(harness, monkeypatch, other_operation):
    """A tick and a manual completion cannot award twice or fork a repeat chain."""
    import asyncio
    from unittest.mock import AsyncMock
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.enums import DwellerStatusEnum, GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
    from app.crud.vault import vault as vault_crud
    from app.models.dweller import Dweller
    from app.models.room import Room
    from app.models.training import Training, TrainingStatus
    from app.services.notification_service import notification_service
    from app.services.training_service import training_service
    from app.utils.exceptions import VaultOperationException

    harness.upgrade("head")
    vault_id = UUID(legacy._seed_vault(harness, number=927))
    monkeypatch.setattr(notification_service, "_deliver", AsyncMock())

    async def race():
        engine = create_async_engine(harness.url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as db:
                vault = await vault_crud.get(db, vault_id)
                vault.continuous_training = True
                dweller = Dweller(
                    first_name="Repeat",
                    gender=GenderEnum.MALE,
                    rarity=RarityEnum.COMMON,
                    vault_id=vault_id,
                    strength=5,
                    health=100,
                    max_health=100,
                )
                room = Room(
                    name="Weight Room",
                    category=RoomTypeEnum.TRAINING,
                    ability=SPECIALEnum.STRENGTH,
                    vault_id=vault_id,
                    base_cost=100,
                    size=3,
                    size_min=3,
                    size_max=9,
                    capacity=1,
                )
                db.add_all([vault, dweller, room])
                await db.commit()
                training = await training_service.start_training(db, dweller.id, room.id)
                training_id, dweller_id = training.id, dweller.id

            async def operate(operation):
                async with sessions() as db:
                    try:
                        if operation == "complete":
                            await training_service.complete_training(db, training_id)
                        else:
                            await training_service.set_training_goal(db, training_id, 7)
                    except VaultOperationException:
                        await db.rollback()
                        return False
                    else:
                        return True

            results = await asyncio.gather(operate("complete"), operate(other_operation))
            if other_operation == "complete":
                assert sorted(results) == [False, True]
            else:
                assert results[0] is True
            async with sessions() as db:
                rounds = (await db.execute(select(Training).where(Training.dweller_id == dweller_id))).scalars().all()
                assert len(rounds) == 2
                assert sorted(session.status.value for session in rounds) == [
                    TrainingStatus.ACTIVE.value,
                    TrainingStatus.COMPLETED.value,
                ]
                successor = next(session for session in rounds if session.is_active())
                assert successor.goal_stat_value == (7 if other_operation == "goal" and results[1] else 10)
                dweller = await db.get(Dweller, dweller_id)
                assert dweller.strength == 6
                assert dweller.status == DwellerStatusEnum.TRAINING
        finally:
            await engine.dispose()

    asyncio.run(race())


def test_training_goals_backfill_and_round_trip():
    path = Path(__file__).parents[2] / "alembic/versions/2026_10_23_0003-a3c7e9b1d602_training_goals.py"
    spec = importlib.util.spec_from_file_location("training_goal_migration", path)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE training (id INTEGER PRIMARY KEY, target_stat_value INTEGER)"))
            connection.execute(text("INSERT INTO training VALUES (1, 6), (2, 10)"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert connection.execute(text("SELECT goal_stat_value FROM training ORDER BY id")).scalars().all() == [
                    10,
                    10,
                ]
                connection.execute(text("INSERT INTO training (id, target_stat_value) VALUES (3, 7)"))
                assert connection.execute(text("SELECT goal_stat_value FROM training WHERE id = 3")).scalar() == 10
                connection.execute(text("UPDATE training SET goal_stat_value = 7 WHERE id = 1"))
                migration.downgrade()
                assert connection.execute(text("SELECT COUNT(*) FROM training")).scalar() == 3
                assert "goal_stat_value" not in [
                    column["name"] for column in inspect(connection).get_columns("training")
                ]
    finally:
        engine.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("active_round", [True, False])
def test_destroy_training_room_preserves_history_and_cancels_active_round(harness, monkeypatch, active_round):
    """Real PostgreSQL must allow demolition after any training status, without losing history."""
    import asyncio
    from unittest.mock import AsyncMock
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.enums import DwellerStatusEnum, GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
    from app.models.dweller import Dweller
    from app.models.room import Room
    from app.models.training import Training, TrainingStatus
    from app.models.vault import Vault
    from app.services.notification_service import notification_service
    from app.services.room_service import room_service
    from app.services.training_service import training_service

    harness.upgrade("head")
    harness.downgrade("a3c7e9b1d602")
    harness.upgrade("head")
    vault_id = UUID(legacy._seed_vault(harness, number=928))
    monkeypatch.setattr(notification_service, "_deliver", AsyncMock())

    async def demolish():
        engine = create_async_engine(harness.url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as db:
                vault = await db.get(Vault, vault_id)
                vault.continuous_training = True
                dweller = Dweller(
                    first_name="Demolition",
                    gender=GenderEnum.MALE,
                    rarity=RarityEnum.COMMON,
                    vault_id=vault_id,
                    strength=5,
                    health=100,
                    max_health=100,
                )
                room = Room(
                    name="Weight Room",
                    category=RoomTypeEnum.TRAINING,
                    ability=SPECIALEnum.STRENGTH,
                    vault_id=vault_id,
                    base_cost=100,
                    size=3,
                    size_min=3,
                    size_max=9,
                    capacity=2,
                    coordinate_x=7,
                    coordinate_y=0,
                )
                db.add_all([vault, dweller, room])
                await db.commit()
                training = await training_service.start_training(db, dweller.id, room.id)
                await training_service.complete_training(db, training.id)
                from app.crud.training import training as training_crud

                successor = await training_crud.get_active_by_dweller(db, dweller.id)
                await training_service.cancel_training(db, successor.id)
                active = await training_service.start_training(db, dweller.id, room.id)
                if not active_round:
                    await training_service.cancel_training(db, active.id)
                room_id, dweller_id = room.id, dweller.id
                before_caps = vault.bottle_caps
                await room_service.destroy_room(db, room_id)
                await db.refresh(dweller)
                await db.refresh(vault)
                assert dweller.strength == 6
                assert dweller.status == DwellerStatusEnum.IDLE
                assert dweller.room_id is None
                assert vault.bottle_caps > before_caps
            async with sessions() as db:
                assert await db.get(Room, room_id) is None
                history = (await db.execute(select(Training).where(Training.dweller_id == dweller_id))).scalars().all()
                assert len(history) == 3
                assert all(record.room_id is None for record in history)
                assert sorted(record.status for record in history) == [
                    TrainingStatus.CANCELLED,
                    TrainingStatus.CANCELLED,
                    TrainingStatus.COMPLETED,
                ]
                assert next(record for record in history if record.id == active.id).completed_at is not None
        finally:
            await engine.dispose()

    asyncio.run(demolish())
    with pytest.raises(RuntimeError, match="Cannot downgrade"):
        harness.downgrade("a3c7e9b1d602")
