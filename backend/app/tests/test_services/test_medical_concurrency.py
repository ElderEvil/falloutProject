"""Live-PostgreSQL concurrency checks for medical supply mutations.

Skips without a reachable PostgreSQL database: SQLite serializes every
write, so it cannot prove row locking. Each test writes its own user,
vault, and dweller rows and removes them afterwards.
"""

import asyncio
import random
import uuid

import pytest
import pytest_asyncio
from pydantic import UUID4
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.enums import GenderEnum, RarityEnum
from app.models.dweller import Dweller
from app.models.user import User
from app.models.vault import Vault
from app.services import medical_service
from app.utils.exceptions import ContentNoChangeException, ResourceConflictException

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncEngine:
    """Connect to the live PostgreSQL database, skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping medical concurrency check")

    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text

            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def radiated_dweller(live_pg_engine: AsyncEngine) -> tuple[UUID4, int]:
    """A vault dweller one stimpack below the radiation ceiling, removed on teardown."""
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    tag = uuid.uuid4().hex[:12]
    async with maker() as session:
        user = User(username=f"locktest_{tag}", email=f"locktest_{tag}@vault.test", hashed_password="x")
        session.add(user)
        await session.flush()
        vault = Vault(number=random.randint(700, 999), user_id=user.id)
        session.add(vault)
        await session.flush()
        dweller = Dweller(
            first_name="Lock",
            last_name="Test",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            vault_id=vault.id,
            max_health=100,
            health=10,
            radiation=30,
            stimpack=1,
            radaway=1,
        )
        session.add(dweller)
        await session.commit()
        ids = (dweller.id, vault.id, user.id)
    yield ids[0], 70
    async with maker() as session:
        await session.execute(delete(Dweller).where(Dweller.id == ids[0]))
        await session.execute(delete(Vault).where(Vault.id == ids[1]))
        await session.execute(delete(User).where(User.id == ids[2]))
        await session.commit()


def _sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_concurrent_spend_is_rejected(live_pg_engine: AsyncEngine, radiated_dweller: tuple[UUID4, int]) -> None:
    """A use racing an uncommitted spend of the last supply must be rejected, not double-spend.

    Without row locking the racing read validates against the pre-image and
    heals anyway (the UPDATE then merely blocks behind the open transaction).
    """
    dweller_id: UUID4 = radiated_dweller[0]
    maker = _sessions(live_pg_engine)
    async with maker() as holder, maker() as actor:
        async with holder.begin():
            held = await holder.get(Dweller, dweller_id)
            assert held is not None
            held.stimpack = 0
            await holder.flush()
            task = asyncio.create_task(medical_service.use_stimpack(actor, dweller_id))
            await asyncio.sleep(0.5)
            assert not task.done(), "racing use validated against a stale pre-image"
        with pytest.raises(ResourceConflictException):
            await asyncio.wait_for(task, timeout=10)


@pytest.mark.asyncio
async def test_concurrent_use_stimpack_spends_once(
    live_pg_engine: AsyncEngine, radiated_dweller: tuple[UUID4, int]
) -> None:
    """Two simultaneous uses with one stimpack: exactly one heals, the other is rejected."""
    from app.core.game_config import game_config

    dweller_id: UUID4 = radiated_dweller[0]
    ceiling: int = radiated_dweller[1]
    maker = _sessions(live_pg_engine)
    async with maker() as first, maker() as second:
        results = await asyncio.gather(
            medical_service.use_stimpack(first, dweller_id),
            medical_service.use_stimpack(second, dweller_id),
            return_exceptions=True,
        )
    successes = [r for r in results if isinstance(r, Dweller)]
    failures = [r for r in results if isinstance(r, (ContentNoChangeException, ResourceConflictException))]
    assert len(successes) == 1, f"expected exactly one heal, got {results!r}"
    assert len(failures) == 1
    heal_amount = max(1, int(100 * game_config.health.stimpack_heal_percent))
    assert successes[0].health == min(10 + heal_amount, ceiling)
    assert successes[0].stimpack == 0
