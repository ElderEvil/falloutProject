"""Live-PostgreSQL concurrency checks for medical supply mutations.

Skips without a reachable PostgreSQL database: SQLite serializes every
write, so it cannot prove row locking. Each test writes its own user,
vault, and dweller rows and removes them afterwards.
"""

import asyncio
import random
import uuid
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.enums import GenderEnum, RarityEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.storage import Storage
from app.models.user import User
from app.models.vault import Vault
from app.services import medical_service as med
from app.tests.factory.dwellers import create_random_common_dweller
from app.utils.exceptions import ContentNoChangeException, ResourceConflictException
from app.utils.radiation import radiation_removal_amount

pytest_plugins = ["app.tests.test_alembic._support"]

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def radiated_dweller(live_pg_engine: AsyncEngine) -> tuple[UUID, int]:
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


async def _race(engine: AsyncEngine, fn, first_id: UUID, second_id: UUID | None = None) -> list:
    """Run two concurrent supply uses on separate sessions."""
    maker = _sessions(engine)
    async with maker() as first, maker() as second:
        return await asyncio.gather(fn(first, first_id), fn(second, second_id or first_id), return_exceptions=True)


async def test_concurrent_spend_is_rejected(live_pg_engine: AsyncEngine, radiated_dweller: tuple[UUID, int]) -> None:
    """A use racing an uncommitted spend of the last supply must be rejected, not double-spend.
    Without row locking the racing read validates against the pre-image and
    heals anyway (the UPDATE then merely blocks behind the open transaction).
    """
    dweller_id: UUID = radiated_dweller[0]
    maker = _sessions(live_pg_engine)
    async with maker() as holder, maker() as actor:
        async with holder.begin():
            held = await holder.get(Dweller, dweller_id)
            assert held is not None
            held.stimpack = 0
            await holder.flush()
            task = asyncio.create_task(med.use_stimpack(actor, dweller_id))
            await asyncio.sleep(0.5)
            assert not task.done(), "racing use validated against a stale pre-image"
        with pytest.raises(ResourceConflictException):
            await asyncio.wait_for(task, timeout=10)


async def test_concurrent_use_stimpack_spends_once(
    live_pg_engine: AsyncEngine, radiated_dweller: tuple[UUID, int]
) -> None:
    dweller_id: UUID = radiated_dweller[0]
    ceiling: int = radiated_dweller[1]
    results = await _race(live_pg_engine, med.use_stimpack, dweller_id)
    successes = [r for r in results if isinstance(r, Dweller)]
    failures = [r for r in results if isinstance(r, (ContentNoChangeException, ResourceConflictException))]
    assert len(successes) == 1, f"expected exactly one heal, got {results!r}"
    assert len(failures) == 1
    heal_amount = max(1, int(100 * game_config.health.stimpack_heal_percent))
    assert successes[0].health == min(10 + heal_amount, ceiling)
    assert successes[0].stimpack == 0


async def test_concurrent_use_radaway_spends_once(
    live_pg_engine: AsyncEngine, radiated_dweller: tuple[UUID, int]
) -> None:
    dweller_id: UUID = radiated_dweller[0]
    results = await _race(live_pg_engine, med.use_radaway, dweller_id)
    successes = [r for r in results if isinstance(r, Dweller)]
    failures = [r for r in results if isinstance(r, (ContentNoChangeException, ResourceConflictException))]
    assert len(successes) == 1, f"expected exactly one treatment, got {results!r}"
    assert len(failures) == 1
    removal = radiation_removal_amount(30, successes[0].max_health)
    assert successes[0].radiation == 30 - removal
    assert successes[0].radaway == 0


@pytest_asyncio.fixture
async def vault_stimpack_stock(live_pg_engine: AsyncEngine, radiated_dweller: tuple[UUID, int]):
    """Two injured dwellers sharing the last vault stimpack."""
    maker = _sessions(live_pg_engine)
    async with maker() as session:
        first = await session.get(Dweller, radiated_dweller[0])
        assert first is not None
        first.stimpack = 0
        second = Dweller(**(create_random_common_dweller() | {"vault_id": first.vault_id, "health": 10, "stimpack": 0}))
        stock = Storage(vault_id=first.vault_id, stimpack=1)
        session.add_all([first, second, stock])
        await session.commit()
        ids = (first.id, second.id, stock.id)
    yield ids
    async with maker() as session:
        await session.execute(delete(Storage).where(Storage.id == ids[2]))
        await session.execute(delete(Dweller).where(Dweller.id == ids[1]))
        await session.commit()


async def test_two_dwellers_cannot_spend_the_same_vault_stimpack(live_pg_engine: AsyncEngine, vault_stimpack_stock):
    first_id, second_id, stock_id = vault_stimpack_stock
    results = await _race(live_pg_engine, med.use_stimpack, first_id, second_id)
    assert sum(isinstance(result, Dweller) for result in results) == 1, results
    assert sum(isinstance(result, ResourceConflictException) for result in results) == 1, results
    maker = _sessions(live_pg_engine)
    async with maker() as session:
        stock = await session.get(Storage, stock_id)
        assert stock is not None
        assert stock.stimpack == 0


async def test_vault_stimpack_use_waits_for_pending_stock_spend(live_pg_engine: AsyncEngine, vault_stimpack_stock):
    """A pending stock deduction must be seen even when the actor has cached the old row."""
    first_id, _, stock_id = vault_stimpack_stock
    maker = _sessions(live_pg_engine)
    async with maker() as holder, maker() as actor:
        cached = await actor.get(Storage, stock_id)
        assert cached is not None
        assert cached.stimpack == 1
        async with holder.begin():
            stock = await holder.get(Storage, stock_id)
            assert stock is not None
            stock.stimpack = 0
            await holder.flush()
            task = asyncio.create_task(med.use_stimpack(actor, first_id))
            await asyncio.sleep(0.5)
            assert not task.done(), "healing did not wait for the stock mutation"
        with pytest.raises(ResourceConflictException):
            await asyncio.wait_for(task, timeout=10)
