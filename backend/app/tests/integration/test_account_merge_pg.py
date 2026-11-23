"""PostgreSQL concurrency coverage for the account merge service.

Each test owns one event loop via ``asyncio.run`` so the asyncpg pool is never
shared; schema comes from Alembic, never ``create_all``.
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
    except Exception as exc:  # pragma: no cover - malformed config is not an optional DB
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
    number = random_vault_number()
    while number in used:
        number = random_vault_number()
    used.add(number)
    return number


async def _make_user(session: AsyncSession, tag: str, suffix: str) -> User:
    return await crud.user.create(
        session,
        UserCreate(username=f"mergepg{tag}{suffix}", email=f"mergepg{tag}{suffix}@example.com", password="Secret123!"),
    )


async def _seed(maker, *, sources: int, targets: int, user_ids: list, vault_ids: list):
    """Create a superuser actor, source/target users, and one vault per source."""
    suffix = uuid4().hex[:10]
    async with maker() as session:
        actor = await _make_user(session, "act", suffix)
        user_ids.append(actor.id)
        actor.is_superuser = True
        await session.commit()
        source_users = [await _make_user(session, f"src{i}", suffix) for i in range(sources)]
        target_users = [await _make_user(session, f"tgt{i}", suffix) for i in range(targets)]
        user_ids.extend(user.id for user in source_users + target_users)
        used: set[int] = set()
        vaults = [Vault(user_id=user.id, number=_vault_number(used)) for user in source_users]
        session.add_all(vaults)
        await session.commit()
        vault_ids.extend(vault.id for vault in vaults)
    return source_users, target_users, actor, vaults


async def _race(*calls):
    """Run concurrent merge attempts, collecting exceptions as results."""
    return await asyncio.wait_for(asyncio.gather(*calls, return_exceptions=True), timeout=20)


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
    statements = [
        delete(AccountMerge).where(
            or_(
                col(AccountMerge.source_user_id).in_(user_ids),
                col(AccountMerge.target_user_id).in_(user_ids),
                col(AccountMerge.actor_user_id).in_(user_ids),
            )
        ),
        delete(Notification).where(
            or_(col(Notification.user_id).in_(user_ids), col(Notification.vault_id).in_(vault_ids))
        ),
        delete(ChatMessage).where(
            or_(
                col(ChatMessage.from_user_id).in_(user_ids),
                col(ChatMessage.to_user_id).in_(user_ids),
                col(ChatMessage.vault_id).in_(vault_ids),
            )
        ),
        delete(LLMInteraction).where(col(LLMInteraction.user_id).in_(user_ids)),
        delete(OAuthAccount).where(col(OAuthAccount.user_id).in_(user_ids)),
        delete(Vault).where(or_(col(Vault.id).in_(vault_ids), col(Vault.user_id).in_(user_ids))),
        delete(UserProfile).where(col(UserProfile.user_id).in_(user_ids)),
        delete(User).where(col(User.id).in_(user_ids)),
    ]
    async with maker() as session:
        for statement in statements:
            await session.execute(statement)
        await session.commit()


async def _audit_count(session: AsyncSession, source_ids: list) -> int:
    result = await session.execute(
        select(func.count()).select_from(AccountMerge).where(col(AccountMerge.source_user_id).in_(source_ids))
    )
    return int(result.scalar_one())


async def _vaults(session: AsyncSession, vault_ids: list) -> list[Vault]:
    return (await session.execute(select(Vault).where(col(Vault.id).in_(vault_ids)))).scalars().all()


async def _verify_landed(maker, source_id, winner_id, vault_ids, losing_id=None) -> None:
    """A single merge won: one audit row, source tombstoned, vaults moved."""
    async with maker() as session:
        assert await _audit_count(session, [source_id]) == 1
        audit = (
            await session.execute(select(AccountMerge).where(AccountMerge.source_user_id == source_id))
        ).scalar_one()
        assert audit.target_user_id == winner_id
        fresh_source = await crud.user.get(session, source_id, include_deleted=True)
        assert fresh_source.is_deleted is True
        assert fresh_source.is_active is False
        assert await crud.vault.count_by_user(session, source_id) == 0
        moved_vault = (await _vaults(session, vault_ids))[0]
        assert moved_vault.user_id == winner_id
        assert await crud.vault.count_by_user(session, winner_id) == 1
        if losing_id is not None:
            assert await crud.vault.count_by_user(session, losing_id) == 0


@asynccontextmanager
async def _merge_context():
    """Own the engine, both racing sessions, and the ids cleanup needs."""
    async with _sessions() as (maker, first, second):
        user_ids: list = []
        vault_ids: list = []
        try:
            yield maker, first, second, user_ids, vault_ids
        finally:
            await _cleanup(maker, user_ids, vault_ids)


async def _same_source_different_targets() -> None:
    async with _merge_context() as (maker, first, second, user_ids, vault_ids):
        sources, targets, actor, _ = await _seed(maker, sources=1, targets=2, user_ids=user_ids, vault_ids=vault_ids)
        source, target_a, target_b = sources[0], targets[0], targets[1]
        results = await _race(
            _attempt(first, source.id, target_a.id, actor.id),
            _attempt(second, source.id, target_b.id, actor.id),
        )
        applied = [result for result in results if not isinstance(result, BaseException) and result.applied]
        conflicts = [result for result in results if isinstance(result, ResourceConflictException)]
        assert len(applied) == 1, results
        assert len(conflicts) == 1, results
        assert len(applied) + len(conflicts) == len(results), results
        winner_target_id = applied[0].target_id
        losing_target_id = target_b.id if winner_target_id == target_a.id else target_a.id
        await _verify_landed(maker, source.id, winner_target_id, vault_ids, losing_target_id)


async def _same_source_same_target() -> None:
    async with _merge_context() as (maker, first, second, user_ids, vault_ids):
        sources, targets, actor, _ = await _seed(maker, sources=1, targets=1, user_ids=user_ids, vault_ids=vault_ids)
        source, target = sources[0], targets[0]
        results = await _race(
            _attempt(first, source.id, target.id, actor.id),
            _attempt(second, source.id, target.id, actor.id),
        )
        assert [result for result in results if isinstance(result, BaseException)] == [], results
        applied = [result for result in results if result.applied]
        idempotent = [result for result in results if result.already_merged and not result.applied]
        assert len(applied) == 1, results
        assert len(idempotent) == 1, results
        await _verify_landed(maker, source.id, target.id, vault_ids)


async def _opposite_directions() -> None:
    async with _merge_context() as (maker, first, second, user_ids, vault_ids):
        sources, _, actor, _ = await _seed(maker, sources=2, targets=0, user_ids=user_ids, vault_ids=vault_ids)
        first_user, second_user = sources
        results = await _race(
            _attempt(first, first_user.id, second_user.id, actor.id),
            _attempt(second, second_user.id, first_user.id, actor.id),
        )
        applied = [result for result in results if not isinstance(result, BaseException) and result.applied]
        errors = [result for result in results if isinstance(result, BaseException)]
        assert len(applied) == 1, results
        assert len(errors) == 1, results
        assert isinstance(errors[0], DomainError), results
        async with maker() as session:
            assert await _audit_count(session, [first_user.id, second_user.id]) == 1
            fresh_users = [
                await crud.user.get(session, user_id, include_deleted=True)
                for user_id in (first_user.id, second_user.id)
            ]
            tombstoned = [user for user in fresh_users if user.is_deleted and not user.is_active]
            survivors = [user for user in fresh_users if not user.is_deleted and user.is_active]
            assert len(tombstoned) == 1, fresh_users
            assert len(survivors) == 1, fresh_users
            surviving_user = survivors[0]
            surviving_vaults = await _vaults(session, vault_ids)
            assert {vault.user_id for vault in surviving_vaults} == {surviving_user.id}
            assert await crud.vault.count_by_user(session, tombstoned[0].id) == 0
            assert await crud.vault.count_by_user(session, surviving_user.id) == len(vault_ids)


def test_same_source_different_targets_concurrently() -> None:
    asyncio.run(_same_source_different_targets())


def test_same_source_same_target_concurrently() -> None:
    asyncio.run(_same_source_same_target())


def test_opposite_merge_directions_do_not_deadlock() -> None:
    asyncio.run(_opposite_directions())
