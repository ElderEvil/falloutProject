"""Quest link backfill races on PostgreSQL, where the link-key violation is real."""

import asyncio
from collections.abc import AsyncGenerator, Mapping
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.models.vault_quest import VaultQuestCompletionLink
from app.schemas.quest import QuestCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreate
from app.services.progression.quests.rotation import ensure_current_quest_rotation
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault

RACE_TIMEOUT_SECONDS = 15


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncEngine:
    """Connect to live PostgreSQL (schema migrated), skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping backfill race check")

    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            migrated = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'vault' AND column_name = 'scenario_key'"
                )
            )
            if migrated.scalar() != 1:
                pytest.skip("database schema predates the current migrations; run alembic upgrade head")
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def race_session_maker(live_pg_engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_backfill_and_rotation_race_without_deadlock(
    race_session_maker: async_sessionmaker, live_pg_engine: AsyncEngine
) -> None:
    """A first quest-screen read and the rotation sweep race the same fresh vault.

    This is the PostgreSQL failure mode SQLite cannot reproduce: the composite PK
    (vault_id, quest_id) rejects a duplicate plain INSERT, and backfill plus
    rotation must agree on a lock order or they deadlock across the vault and
    link keys. Both paths run for real (the vault-quest list and the rotation
    sweep), each commits inside its own operation, and the wait is bounded.
    """
    cleanup_quest_ids: list[UUID] = []
    cleanup_vault_id: UUID | None = None
    cleanup_user_id: UUID | None = None
    try:
        async with race_session_maker() as setup:
            user = await crud.user.create(setup, obj_in=UserCreate(**create_fake_user()))
            vault = await crud.vault.create_with_user_id(
                db_session=setup, obj_in=VaultCreate(**create_fake_vault()), user_id=user.id
            )
            for label, quest_type, count in (("Side", "side", 3), ("Daily", "daily", 3), ("Weekly", "repeatable", 2)):
                for number in range(count):
                    quest = await crud.quest_crud.create(
                        setup,
                        obj_in=QuestCreate(
                            title=f"{label} race {number}",
                            short_description="Backfill race fixture",
                            long_description="Concurrent first reads must not deadlock or duplicate links.",
                            requirements="No prerequisites",
                            rewards="10 caps",
                            quest_type=quest_type,
                        ),
                    )
                    cleanup_quest_ids.append(quest.id)
            await setup.commit()
            cleanup_vault_id = vault.id
            cleanup_user_id = user.id

            async def read_quest_screen(session: AsyncSession) -> None:
                await crud.quest_crud.get_multi_for_vault(db_session=session, skip=0, limit=100, vault_id=vault.id)
                await session.commit()

            async def run_rotation(session: AsyncSession) -> None:
                await ensure_current_quest_rotation(session, vault.id)
                await session.commit()

            async with race_session_maker() as reader, race_session_maker() as rotator:
                await asyncio.wait_for(
                    asyncio.gather(
                        read_quest_screen(reader),
                        run_rotation(rotator),
                    ),
                    timeout=RACE_TIMEOUT_SECONDS,
                )

            links = list(
                (
                    await setup.exec(
                        select(VaultQuestCompletionLink).where(VaultQuestCompletionLink.vault_id == vault.id)
                    )
                ).all()
            )
            assert sorted(link.quest_id for link in links) == sorted(cleanup_quest_ids)
            visibility = {link.quest_id: link.is_visible for link in links}
            side_quests = cleanup_quest_ids[:3]
            daily_quests = cleanup_quest_ids[3:6]
            weekly_quests = cleanup_quest_ids[6:8]
            assert all(visibility[quest_id] for quest_id in side_quests)
            assert sum(visibility[quest_id] for quest_id in daily_quests) == 3
            assert sum(visibility[quest_id] for quest_id in weekly_quests) == 1
    finally:
        if cleanup_vault_id is not None:
            await _cleanup(live_pg_engine, cleanup_quest_ids, cleanup_vault_id, cleanup_user_id)


async def _cleanup(engine: AsyncEngine, quest_ids: list[UUID], vault_id: UUID | None, user_id: UUID | None) -> None:
    """Delete exactly the fixture rows, by id, in FK-safe order."""
    async with engine.begin() as conn:
        if vault_id is not None:
            await conn.execute(
                text("DELETE FROM vaultquestcompletionlink WHERE vault_id = :vault_id"), {"vault_id": vault_id}
            )
        if quest_ids:
            await conn.execute(text("DELETE FROM quest WHERE id = ANY(:quest_ids)"), {"quest_ids": quest_ids})
        if vault_id is not None:
            await conn.execute(text("DELETE FROM vault WHERE id = :vault_id"), {"vault_id": vault_id})
        if user_id is not None:
            await conn.execute(text('DELETE FROM "user" WHERE id = :user_id'), {"user_id": user_id})
