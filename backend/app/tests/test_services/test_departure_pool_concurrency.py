"""Live-PostgreSQL concurrency check for pool claims.

Skips without a reachable PostgreSQL database: SQLite serializes every write, so it
cannot prove row locking. Two vaults claim the same departure at once and exactly one
must win, charging caps once.
"""

import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from pydantic import UUID4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import crud
from app.core.config import settings
from app.core.enums import (
    SPECIAL_STATS,
    AgeGroupEnum,
    AvailabilityEnum,
    ContentProvenanceEnum,
    GenderEnum,
    LifecycleEnum,
    RarityEnum,
)
from app.models.dweller import Dweller
from app.models.user import User
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.departure_pool_service import departure_pool_service
from app.utils.exceptions import ResourceConflictException

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncEngine:
    """Connect to the live PostgreSQL database, skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping pool claim concurrency check")
    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def two_buyers(live_pg_engine: AsyncEngine) -> tuple[UUID4, UUID4, UUID4]:
    """Two funded vaults and a pool-eligible departure from a third; removed on teardown."""
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    tag = uuid.uuid4().hex[:12]
    now = datetime.now(UTC).replace(tzinfo=None)
    async with maker() as session:
        wallets: dict[str, Vault] = {}
        for label in ("a", "b", "src"):
            user = User(username=f"pool_{label}_{tag}", email=f"pool_{label}_{tag}@vault.test", hashed_password="x")
            session.add(user)
            await session.flush()
            vault = Vault(number=random.randint(1, 999), user_id=user.id, bottle_caps=100_000, population_max=50)
            session.add(vault)
            await session.flush()
            wallets[label] = vault

        dweller = await crud.dweller.create(
            db_session=session,
            obj_in=DwellerCreate(
                vault_id=wallets["src"].id,
                first_name="Pool",
                last_name="Nomad",
                gender=GenderEnum.FEMALE,
                rarity=RarityEnum.COMMON,
                age_group=AgeGroupEnum.ADULT,
                birth_date=now - timedelta(days=365 * 30),
                level=6,
                experience=100,
                max_health=110,
                health=110,
                radiation=0,
                happiness=60,
                **dict.fromkeys(SPECIAL_STATS, 4),
            ),
        )
        dweller.lifecycle = LifecycleEnum.WASTELAND
        dweller.availability = AvailabilityEnum.DEPARTURE
        dweller.vault_id = None
        dweller.previous_vault_id = wallets["src"].id
        dweller.content_provenance = ContentProvenanceEnum.GENERATED
        dweller.departed_at = now - timedelta(days=8)
        dweller.departure_eligible_at = now - timedelta(days=1)
        session.add(dweller)
        await session.commit()

        yield dweller.id, wallets["a"].id, wallets["b"].id

    async with maker() as session:
        await session.execute(text("DELETE FROM dweller WHERE id = :id"), {"id": str(dweller.id)})
        for vault in wallets.values():
            await session.execute(text("DELETE FROM vault WHERE id = :id"), {"id": str(vault.id)})
        await session.execute(text('DELETE FROM "user" WHERE username LIKE :p'), {"p": f"pool_%_{tag}"})
        await session.commit()


@pytest.mark.asyncio
async def test_two_vaults_cannot_claim_the_same_departure(
    live_pg_engine: AsyncEngine, two_buyers: tuple[UUID4, UUID4, UUID4]
) -> None:
    dweller_id, buyer_a, buyer_b = two_buyers
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)

    async def _claim(vault_id: UUID4) -> str:
        async with maker() as session:
            vault = await session.get(Vault, vault_id)
            try:
                await departure_pool_service.claim(session, vault, dweller_id)
            except ResourceConflictException:
                await session.rollback()
                return "conflict"
            else:
                return "claimed"

    outcomes = await asyncio.gather(_claim(buyer_a), _claim(buyer_b))

    assert sorted(outcomes) == ["claimed", "conflict"]

    async with maker() as session:
        winner = await session.get(Dweller, dweller_id)
        assert winner.vault_id in {buyer_a, buyer_b}
        assert winner.availability is AvailabilityEnum.VAULT
