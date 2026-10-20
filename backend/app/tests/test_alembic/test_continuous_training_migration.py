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
def test_concurrent_completions_create_only_one_successor(harness, monkeypatch):
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

            async def complete():
                async with sessions() as db:
                    try:
                        await training_service.complete_training(db, training_id)
                    except VaultOperationException:
                        await db.rollback()
                        return False
                    else:
                        return True

            results = await asyncio.gather(complete(), complete())
            assert sorted(results) == [False, True]
            async with sessions() as db:
                rounds = (await db.execute(select(Training).where(Training.dweller_id == dweller_id))).scalars().all()
                assert len(rounds) == 2
                assert sorted(session.status.value for session in rounds) == [
                    TrainingStatus.ACTIVE.value,
                    TrainingStatus.COMPLETED.value,
                ]
                dweller = await db.get(Dweller, dweller_id)
                assert dweller.strength == 6
                assert dweller.status == DwellerStatusEnum.TRAINING
        finally:
            await engine.dispose()

    asyncio.run(race())
