"""Tests for dweller recycling service datetime compatibility with naive UTC timestamps.

These tests validate that the recycling service works correctly with naive UTC
datetimes stored in PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns.
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.services.dweller_recycling_service import dweller_recycling_service


@pytest_asyncio.fixture(name="naive_deleted_dweller")
async def naive_deleted_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a soft-deleted dweller with a naive UTC deleted_at timestamp."""
    dweller_data = {
        "first_name": "Naive",
        "last_name": "Ghost",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "level": 1,
        "experience": 0,
        "max_health": 50,
        "health": 50,
        "radiation": 0,
        "happiness": 50,
        "strength": 5,
        "perception": 5,
        "endurance": 5,
        "charisma": 5,
        "intelligence": 5,
        "agility": 5,
        "luck": 5,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

    # Soft-delete using a naive UTC datetime (no tzinfo)
    # This mirrors how deleted_at is stored in PostgreSQL TIMESTAMP WITHOUT TIME ZONE
    dweller.is_deleted = True
    dweller.deleted_at = datetime.utcnow() - timedelta(days=1)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


@pytest.mark.asyncio
async def test_get_recyclable_dwellers_with_naive_utc_timestamp(
    async_session: AsyncSession,
    vault: Vault,
    naive_deleted_dweller: Dweller,
):
    """A dweller soft-deleted with a naive UTC timestamp must be returned as recyclable.

    Before the fix, `datetime.now(UTC)` produced a timezone-aware datetime that
    asyncpg could not compare against a naive TIMESTAMP WITHOUT TIME ZONE column,
    causing the query to raise a DBAPIError on PostgreSQL. Using `datetime.utcnow()`
    ensures the cutoff_date is naive and compatible.
    """
    recyclable = await dweller_recycling_service.get_recyclable_dwellers(
        db_session=async_session,
        min_age_days=0,
        limit=10,
    )

    assert len(recyclable) == 1
    assert recyclable[0].id == naive_deleted_dweller.id
