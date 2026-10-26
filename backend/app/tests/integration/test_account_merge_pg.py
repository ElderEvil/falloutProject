"""PostgreSQL concurrency coverage for the account merge service.

Each test owns one event loop via ``asyncio.run`` so the asyncpg pool is never
shared across pytest-asyncio's fixture/test loops. Schema comes from Alembic:
the harness fails loudly when the ``account_merge`` table has not been migrated
instead of creating it on the shared database.
"""

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy import delete, or_, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.models.account_merge import AccountMerge
from app.models.chat_message import ChatMessage
from app.models.llm_interaction import LLMInteraction
from app.models.notification import Notification
from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.vault import Vault
from app.schemas.user import UserCreate
from app.services.account_merge_service import merge_users
from app.tests.factory.vaults import random_vault_number
from app.utils.exceptions import DomainError, ResourceConflictException

pytestmark = pytest.mark.integration


def _postgres_uri() -> str:
    uri = str(settings.ASYNC_DATABASE_URI or "")
    if not uri:
        pytest.skip("ASYNC_DATABASE_URI is not configured")
    try:
        url = make_url(uri)
    except Exception as exc:  # pragma: no cover - malformed configuration is not an optional DB
        pytest.fail(f"ASYNC_DATABASE_URI is malformed: {exc}")
    if url.drivername not in {"postgresql+asyncpg", "postgresql+psycopg"}:
        pytest.skip(f"PostgreSQL-only concurrency test; ASYNC_DATABASE_URI uses {url.drivername}")
    return uri


@asynccontextmanager
async def _sessions():
    engine = create_async_engine(_postgres_uri(), pool_size=5, max_overflow=5)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            table = (await connection.execute(text("SELECT to_regclass('public.account_merge')"))).scalar_one()
    except Exception as exc:  # pragma: no cover - optional local PostgreSQL
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    if table is None:
        await engine.dispose()
        pytest.fail("account_merge table is missing; run `uv run alembic upgrade head` first")
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as first, maker() as second:
            yield maker, first, second
    finally:
        await engine.dispose()


def _vault_number(used: set[int]) -> int:
    while True:
        number = random_vault_number()
        if number not in used:
            used.add(number)
            return number


async def _seed(
    maker, *, sources: int, targets: int, user_ids: list, vault_ids: list
) -> tuple[list[User], list[User], User, list[Vault]]:
    """Create an active superuser actor, source/target users, and one vault per source.

    IDs are recorded as rows are committed so a mid-setup failure still cleans up.
    """
    suffix = uuid4().hex[:10]
    async with maker() as session:
        actor = await crud.user.create(
            session,
            UserCreate(username=f"mergepgact{suffix}", email=f"mergepgact{suffix}@example.com", password="Secret123!"),
        )
        user_ids.append(actor.id)
        actor.is_superuser = True
        await session.commit()

        source_users = []
        for i in range(sources):
            source_user = await crud.user.create(
                session,
                UserCreate(
                    username=f"mergepgsrc{i}{suffix}",
                    email=f"mergepgsrc{i}{suffix}@example.com",
                    password="Secret123!",
                ),
            )
            user_ids.append(source_user.id)
            source_users.append(source_user)
        target_users = []
        for i in range(targets):
            target_user = await crud.user.create(
                session,
                UserCreate(
                    username=f"mergepgtgt{i}{suffix}",
                    email=f"mergepgtgt{i}{suffix}@example.com",
                    password="Secret123!",
                ),
            )
            user_ids.append(target_user.id)
            target_users.append(target_user)
        used_numbers: set[int] = set()
        vaults = [Vault(user_id=source_user.id, number=_vault_number(used_numbers)) for source_user in source_users]
        session.add_all(vaults)
        await session.commit()
        vault_ids.extend(vault.id for vault in vaults)
    return source_users, target_users, actor, vaults


async def _attempt(session: AsyncSession, source_id, target_id, actor_id):
    try:
        return await merge_users(
            session,
            str(source_id),
            str(target_id),
            actor=str(actor_id),
            reason="concurrency",
            dry_run=False,
            redis_client=None,
        )
    finally:
        # A losing request may have raised before the service opened/closed its transaction.
        if session.in_transaction():
            await session.rollback()


async def _cleanup(maker, user_ids: list, vault_ids: list) -> None:
    """Delete audit rows first: their user FKs are ON DELETE RESTRICT."""
    if not user_ids and not vault_ids:
        return
    async with maker() as session:
        if user_ids:
            await session.execute(
                delete(AccountMerge).where(
                    or_(
                        col(AccountMerge.source_user_id).in_(user_ids),
                        col(AccountMerge.target_user_id).in_(user_ids),
                        col(AccountMerge.actor_user_id).in_(user_ids),
                    )
                )
            )
            await session.execute(delete(Notification).where(col(Notification.user_id).in_(user_ids)))
            await session.execute(
                delete(ChatMessage).where(
                    or_(
                        col(ChatMessage.from_user_id).in_(user_ids),
                        col(ChatMessage.to_user_id).in_(user_ids),
                    )
                )
            )
            await session.execute(delete(LLMInteraction).where(col(LLMInteraction.user_id).in_(user_ids)))
            await session.execute(delete(OAuthAccount).where(col(OAuthAccount.user_id).in_(user_ids)))
        if vault_ids:
            await session.execute(delete(Notification).where(col(Notification.vault_id).in_(vault_ids)))
            await session.execute(delete(ChatMessage).where(col(ChatMessage.vault_id).in_(vault_ids)))
            await session.execute(delete(Vault).where(col(Vault.id).in_(vault_ids)))
        if user_ids:
            await session.execute(delete(Vault).where(col(Vault.user_id).in_(user_ids)))
            await session.execute(delete(UserProfile).where(col(UserProfile.user_id).in_(user_ids)))
            await session.execute(delete(User).where(col(User.id).in_(user_ids)))
        await session.commit()


async def _audit_count(session: AsyncSession, source_ids: list) -> int:
    result = await session.execute(
        select(func.count()).select_from(AccountMerge).where(col(AccountMerge.source_user_id).in_(source_ids))
    )
    return int(result.scalar_one())


async def _same_source_different_targets() -> None:
    async with _sessions() as (maker, first, second):
        user_ids: list = []
        vault_ids: list = []
        try:
            sources, targets, actor, vaults = await _seed(
                maker, sources=1, targets=2, user_ids=user_ids, vault_ids=vault_ids
            )
            source, target_a, target_b = sources[0], targets[0], targets[1]
            results = await asyncio.wait_for(
                asyncio.gather(
                    _attempt(first, source.id, target_a.id, actor.id),
                    _attempt(second, source.id, target_b.id, actor.id),
                    return_exceptions=True,
                ),
                timeout=20,
            )
            applied = [result for result in results if not isinstance(result, BaseException) and result.applied]
            conflicts = [result for result in results if isinstance(result, ResourceConflictException)]
            assert len(applied) == 1, results
            assert len(conflicts) == 1, results
            assert len(applied) + len(conflicts) == len(results), results
            winner_target_id = applied[0].target_id
            losing_target_id = target_b.id if winner_target_id == target_a.id else target_a.id

            async with maker() as session:
                assert await _audit_count(session, [source.id]) == 1
                audit = (
                    await session.execute(select(AccountMerge).where(AccountMerge.source_user_id == source.id))
                ).scalar_one()
                assert audit.target_user_id == winner_target_id

                fresh_source = await crud.user.get(session, source.id, include_deleted=True)
                assert fresh_source.is_deleted is True
                assert fresh_source.is_active is False
                assert await crud.vault.count_by_user(session, source.id) == 0

                moved_vault = (await session.execute(select(Vault).where(col(Vault.id).in_(vault_ids)))).scalar_one()
                assert moved_vault.user_id == winner_target_id
                assert await crud.vault.count_by_user(session, winner_target_id) == 1
                assert await crud.vault.count_by_user(session, losing_target_id) == 0
        finally:
            await _cleanup(maker, user_ids, vault_ids)


async def _same_source_same_target() -> None:
    async with _sessions() as (maker, first, second):
        user_ids: list = []
        vault_ids: list = []
        try:
            sources, targets, actor, vaults = await _seed(
                maker, sources=1, targets=1, user_ids=user_ids, vault_ids=vault_ids
            )
            source, target = sources[0], targets[0]
            results = await asyncio.wait_for(
                asyncio.gather(
                    _attempt(first, source.id, target.id, actor.id),
                    _attempt(second, source.id, target.id, actor.id),
                    return_exceptions=True,
                ),
                timeout=20,
            )
            assert [result for result in results if isinstance(result, BaseException)] == [], results
            applied = [result for result in results if result.applied]
            idempotent = [result for result in results if result.already_merged and not result.applied]
            assert len(applied) == 1, results
            assert len(idempotent) == 1, results

            async with maker() as session:
                assert await _audit_count(session, [source.id]) == 1
                fresh_source = await crud.user.get(session, source.id, include_deleted=True)
                assert fresh_source.is_deleted is True
                assert fresh_source.is_active is False

                moved_vault = (await session.execute(select(Vault).where(col(Vault.id).in_(vault_ids)))).scalar_one()
                assert moved_vault.user_id == target.id
                assert await crud.vault.count_by_user(session, source.id) == 0
                assert await crud.vault.count_by_user(session, target.id) == 1
        finally:
            await _cleanup(maker, user_ids, vault_ids)


async def _opposite_directions() -> None:
    async with _sessions() as (maker, first, second):
        user_ids: list = []
        vault_ids: list = []
        try:
            sources, _, actor, vaults = await _seed(maker, sources=2, targets=0, user_ids=user_ids, vault_ids=vault_ids)
            first_user, second_user = sources
            results = await asyncio.wait_for(
                asyncio.gather(
                    _attempt(first, first_user.id, second_user.id, actor.id),
                    _attempt(second, second_user.id, first_user.id, actor.id),
                    return_exceptions=True,
                ),
                timeout=20,
            )
            applied = [result for result in results if not isinstance(result, BaseException) and result.applied]
            errors = [result for result in results if isinstance(result, BaseException)]
            assert len(applied) == 1, results
            assert len(errors) == 1, results
            assert isinstance(errors[0], DomainError), results

            async with maker() as session:
                assert await _audit_count(session, [first_user.id, second_user.id]) == 1

                fresh_ids = [first_user.id, second_user.id]
                fresh_users = [await crud.user.get(session, user_id, include_deleted=True) for user_id in fresh_ids]
                tombstoned = [user for user in fresh_users if user.is_deleted and not user.is_active]
                survivors = [user for user in fresh_users if not user.is_deleted and user.is_active]
                assert len(tombstoned) == 1, fresh_users
                assert len(survivors) == 1, fresh_users

                surviving_user = survivors[0]
                surviving_vaults = (
                    (await session.execute(select(Vault).where(col(Vault.id).in_(vault_ids)))).scalars().all()
                )
                assert {vault.user_id for vault in surviving_vaults} == {surviving_user.id}
                assert await crud.vault.count_by_user(session, tombstoned[0].id) == 0
                assert await crud.vault.count_by_user(session, surviving_user.id) == len(vault_ids)
        finally:
            await _cleanup(maker, user_ids, vault_ids)


def test_same_source_different_targets_concurrently() -> None:
    asyncio.run(_same_source_different_targets())


def test_same_source_same_target_concurrently() -> None:
    asyncio.run(_same_source_same_target())


def test_opposite_merge_directions_do_not_deadlock() -> None:
    asyncio.run(_opposite_directions())
