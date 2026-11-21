"""PostgreSQL-only: two simultaneous accepts settle once and notify once.

SQLite has no row locks, so this skips unless the configured database is a live
PostgreSQL, matching the other lock-contract tests in this package.
"""

import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.enums import (
    AgeGroupEnum,
    GenderEnum,
    NotificationType,
    PvpDuelStatus,
    RarityEnum,
)
from app.crud import pvp_duel as pvp_duel_crud
from app.crud import user as user_crud
from app.crud import vault as vault_crud
from app.crud.dweller import dweller as dweller_crud
from app.models.dweller import Dweller
from app.models.notification import Notification
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreate
from app.services.pvp_duel_service import pvp_duel_service
from app.tests.factory.vaults import random_vault_number
from app.utils.exceptions import DomainError

COMBAT_TYPES = [NotificationType.COMBAT_VICTORY, NotificationType.COMBAT_DEFEAT]


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncEngine:
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping duel accept race")
    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    await engine.dispose()


async def _vault_with_dweller(db: AsyncSession) -> tuple:
    number = random_vault_number()
    user = await user_crud.create(
        db_session=db,
        obj_in=UserCreate(
            username=f"pvp{number}",
            email=f"pvp{number}@example.com",
            password="duelpw123",
        ),
    )
    vault = await vault_crud.create_with_user_id(
        db_session=db, obj_in=VaultCreate(number=number, name=f"Vault {number}"), user_id=user.id
    )
    dweller = await dweller_crud.create(
        db_session=db,
        obj_in=DwellerCreate(
            vault_id=vault.id,
            first_name="Race",
            last_name=f"Tester{number}",
            gender=GenderEnum.MALE,
            age_group=AgeGroupEnum.ADULT,
            rarity=RarityEnum.COMMON,
            level=5,
            experience=0,
            max_health=100,
            health=100,
            radiation=0,
            happiness=50,
            strength=5,
            perception=5,
            endurance=5,
            charisma=5,
            intelligence=5,
            agility=5,
            luck=5,
        ),
    )
    return user, vault, dweller


@pytest.mark.integration
@pytest.mark.asyncio
async def test_two_simultaneous_accepts_settle_once(live_pg_engine: AsyncEngine) -> None:
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as db:
        challenger_user, challenger_vault, challenger_dweller = await _vault_with_dweller(db)
        _, defender_vault, defender_dweller = await _vault_with_dweller(db)
        posted = await pvp_duel_service.post(db, challenger_vault.id, dweller_ids=[challenger_dweller.id])

    async def _accept() -> object:
        async with maker() as session:
            try:
                return await pvp_duel_service.accept(
                    session, defender_vault.id, posted.duel_id, dweller_ids=[defender_dweller.id]
                )
            except DomainError as exc:
                return exc

    first, second = await asyncio.gather(_accept(), _accept())
    results = [first, second]
    assert sum(not isinstance(result, DomainError) for result in results) == 1

    async with maker() as db:
        duel = await pvp_duel_crud.get_duel(db, posted.duel_id)
        assert duel is not None
        assert PvpDuelStatus(duel.status) == PvpDuelStatus.ACCEPTED
        assert duel.journal
        count = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == challenger_user.id,
                Notification.notification_type.in_(COMBAT_TYPES),
            )
        )
        assert count.scalar_one() == 1

        await db.delete(duel)
        for vault_id in (challenger_vault.id, defender_vault.id):
            dwellers = await db.execute(select(Dweller).where(Dweller.vault_id == vault_id))
            for dweller in dwellers.scalars().all():
                await db.delete(dweller)
        await db.commit()
