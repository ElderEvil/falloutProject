import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.crud import user as user_crud
from app.crud import vault as vault_crud
from app.crud.collectible import collectible_crud
from app.crud.dweller import dweller as dweller_crud
from app.models.collectible import VaultCollectible
from app.models.dweller import Dweller
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreate
from app.services.collectible_service import collectible_service
from app.tests.factory.vaults import random_vault_number

pytest_plugins = ["app.tests.test_alembic._support"]


async def vault_with_dweller(
    db: AsyncSession,
    *,
    prefix: str = "bobble",
    surname: str = "Finder",
    password: str = "bobblepw123",  # ruff: ignore[hardcoded-password-default]
) -> tuple:
    number = random_vault_number()
    user = await user_crud.create(
        db_session=db,
        obj_in=UserCreate(username=f"{prefix}{number}", email=f"{prefix}{number}@example.com", password=password),
    )
    vault = await vault_crud.create_with_user_id(
        db_session=db, obj_in=VaultCreate(number=number, name=f"Vault {number}"), user_id=user.id
    )
    dweller = await dweller_crud.create(
        db_session=db,
        obj_in=DwellerCreate(
            vault_id=vault.id,
            first_name="Race",
            last_name=f"{surname}{number}",
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
async def test_two_simultaneous_awards_claim_once(live_pg_engine: AsyncEngine) -> None:
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as db:
        _, vault, dweller = await vault_with_dweller(db)
    vault_id, dweller_id = vault.id, dweller.id

    async def _award() -> bool:
        async with maker() as session:
            finder = await dweller_crud.get(session, dweller_id)
            assert finder is not None
            claimed = await collectible_service.award(
                session, vault_id=vault_id, dweller=finder, collectible_key="strength"
            )
            await session.commit()
            return claimed

    first, second = await asyncio.gather(_award(), _award())
    # Exactly one of the two claims the bobblehead; the loser is told so, not crashed into.
    assert sum(1 for claimed in (first, second) if claimed) == 1
    async with maker() as db:
        claim = await collectible_crud.get_by_vault_and_key(db, vault_id, "strength")
        assert claim is not None
        assert claim.finder_dweller_id == dweller_id
        count = await db.execute(select(func.count(VaultCollectible.id)).where(VaultCollectible.vault_id == vault_id))
        assert count.scalar_one() == 1
        reloaded = await dweller_crud.get(db, dweller_id)
        assert reloaded is not None
        # One bobblehead, one +1: a lost race must not grant a second bonus.
        assert reloaded.collectible_bonus == {"strength": 1}
        await db.delete(claim)
        dwellers = await db.execute(select(Dweller).where(Dweller.vault_id == vault_id))
        for found in dwellers.scalars().all():
            await db.delete(found)
        await db.commit()
