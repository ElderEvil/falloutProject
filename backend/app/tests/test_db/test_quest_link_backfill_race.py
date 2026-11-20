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
async def test_concurrent_first_backfill_keeps_one_link_per_quest(
    race_session_maker: async_sessionmaker, live_pg_engine: AsyncEngine
) -> None:
    """Two first reads racing the same fresh vault insert one link per quest.

    This is the PostgreSQL failure mode SQLite cannot reproduce: the composite PK
    (vault_id, quest_id) rejects a duplicate plain INSERT. The shared insert path
    must conflict no-op instead, and the winner's visibility must survive. Each
    racer commits inside its own operation so the loser resolves against the
    winner's committed row instead of blocking on it forever.
    """
    cleanup_vault_id: UUID | None = None
    cleanup_user_id: UUID | None = None
    try:
        async with race_session_maker() as setup:
            user = await crud.user.create(setup, obj_in=UserCreate(**create_fake_user()))
            vault = await crud.vault.create_with_user_id(
                db_session=setup, obj_in=VaultCreate(**create_fake_vault()), user_id=user.id
            )
            quest_ids = [
                (
                    await crud.quest_crud.create(
                        setup,
                        obj_in=QuestCreate(
                            title=f"Race backfill {number}",
                            short_description="Backfill race fixture",
                            long_description="Concurrent first reads must not violate the link key.",
                            requirements="No prerequisites",
                            rewards="10 caps",
                        ),
                    )
                ).id
                for number in range(3)
            ]
            await setup.commit()
            cleanup_vault_id = vault.id
            cleanup_user_id = user.id

            async def race_insert(session: AsyncSession, visibility: Mapping[UUID, bool]) -> None:
                await crud.quest_crud.insert_links_if_absent(session, vault.id, visibility)
                await session.commit()

            async with race_session_maker() as first, race_session_maker() as second:
                offered = dict.fromkeys(quest_ids, True)
                hidden = dict.fromkeys(quest_ids, False)
                await asyncio.wait_for(
                    asyncio.gather(
                        race_insert(first, offered),
                        race_insert(second, hidden),
                    ),
                    timeout=RACE_TIMEOUT_SECONDS,
                )

                # Whoever inserted first owns the row; the loser's conflict no-op
                # must leave that row exactly as the winner wrote it.
                first_links = await _link_map(first, vault.id)
                second_links = await _link_map(second, vault.id)
                assert set(first_links) == set(quest_ids)
                for quest_id in quest_ids:
                    assert first_links[quest_id].is_visible == second_links[quest_id].is_visible

            links = list(
                (
                    await setup.exec(
                        select(VaultQuestCompletionLink).where(VaultQuestCompletionLink.vault_id == vault.id)
                    )
                ).all()
            )
            assert sorted(link.quest_id for link in links) == sorted(quest_ids)
    finally:
        if cleanup_vault_id is not None:
            await _cleanup(live_pg_engine, cleanup_vault_id, cleanup_user_id)


async def _cleanup(engine: AsyncEngine, vault_id: UUID | None, user_id: UUID | None) -> None:
    """Delete the fixture rows in FK-safe order (vault children are ON DELETE CASCADE)."""
    async with engine.begin() as conn:
        if vault_id is not None:
            await conn.execute(
                text("DELETE FROM vaultquestcompletionlink WHERE vault_id = :vault_id"), {"vault_id": vault_id}
            )
            await conn.execute(text("DELETE FROM quest WHERE title LIKE 'Race backfill %'"))
            await conn.execute(text("DELETE FROM vault WHERE id = :vault_id"), {"vault_id": vault_id})
        if user_id is not None:
            await conn.execute(text('DELETE FROM "user" WHERE id = :user_id'), {"user_id": user_id})


async def _link_map(session: AsyncSession, vault_id: UUID) -> dict[UUID, VaultQuestCompletionLink]:
    return {
        link.quest_id: link
        for link in (
            await session.exec(select(VaultQuestCompletionLink).where(VaultQuestCompletionLink.vault_id == vault_id))
        ).all()
    }
