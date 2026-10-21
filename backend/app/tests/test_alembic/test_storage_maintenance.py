"""Real PostgreSQL migration and concurrent trial regression."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.game_config import game_config
from app.models.game_state import GameState
from app.models.storage import Storage
from app.services.catalog_service import load_weapons
from app.services.game_tick.storage_tick import process_storage_maintenance
from app.services.notification_service import notification_service
from app.tests.test_alembic import test_data_migrations as legacy
from app.tests.test_alembic.test_data_migrations import _seed_vault
from app.utils.item_factory import build_weapon

pytestmark = pytest.mark.integration
harness = legacy.harness


def test_two_sessions_trial_one_weapon_once(harness, monkeypatch):
    harness.upgrade("b7e3d9c1a5f2")
    vault_id = _seed_vault(harness, number=926)
    harness.upgrade("c8a4d6e2f901")
    assert (
        harness.scalar(
            "SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid WHERE t.typname='notificationtype' AND e.enumlabel IN ('STORAGE_ITEM_DEGRADED', 'STORAGE_ITEM_UPGRADED')"
        )
        == 2
    )
    # The runtime service reads today's Vault model; keep its later columns available.
    harness.upgrade("head")
    monkeypatch.setattr(game_config.storage, "maintenance_enabled", True)
    monkeypatch.setattr(notification_service, "_deliver", AsyncMock())
    rng = Mock(return_value=0.0)

    async def race():
        from uuid import UUID

        engine = create_async_engine(harness.url)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as db:
                storage = Storage(vault_id=UUID(vault_id))
                entry = next(e for e in load_weapons() if e["name"] == "Gauss pistol")
                weapon = build_weapon(entry, entry["rarity"], storage.id)
                weapon.last_maintenance_trial_at = datetime.utcnow() - timedelta(hours=2)
                db.add_all([storage, weapon, GameState(vault_id=UUID(vault_id))])
                await db.commit()

            async def run():
                async with sessions() as db:
                    return await process_storage_maintenance(db, UUID(vault_id), rng)

            results = await asyncio.gather(run(), run())
            assert sum(result["changed"] for result in results) == 1
            assert rng.call_count == 1
        finally:
            await engine.dispose()

    asyncio.run(race())
    assert harness.scalar("SELECT count(*) FROM notification WHERE vault_id = CAST(:id AS uuid)", id=vault_id) == 1
