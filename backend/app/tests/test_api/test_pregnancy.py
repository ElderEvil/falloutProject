"""Tests for pregnancy API endpoints."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.models.dweller import Dweller
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate, DwellerCreateCommonOverride

pytestmark = pytest.mark.asyncio(loop_scope="module")


async def _adult(async_session: AsyncSession, vault_id: UUID, gender: GenderEnum) -> Dweller:
    return await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            first_name="Test",
            last_name="Dweller",
            gender=gender,
            rarity=RarityEnum.COMMON,
            is_adult=True,
            age_group=AgeGroupEnum.ADULT,
            birth_date=datetime(2000, 1, 1),
            max_health=100,
            health=100,
            vault_id=str(vault_id),
        ),
    )


@pytest.mark.asyncio
async def test_get_vault_pregnancies_with_active(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test getting active pregnancies."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 798},
        user_id=user.id,
    )

    # Create couple
    mother = await _adult(async_session, vault.id, GenderEnum.FEMALE)
    father = await _adult(async_session, vault.id, GenderEnum.MALE)

    # Create pregnancy
    from app.services.breeding_service import breeding_service

    pregnancy = await breeding_service.create_pregnancy(
        async_session,
        mother.id,
        father.id,
    )

    response = await async_client.get(
        f"/pregnancies/vault/{vault.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["mother_id"] == str(mother.id)
    assert data[0]["father_id"] == str(father.id)
    assert data[0]["status"] == "pregnant"
    assert "progress_percentage" in data[0]
    assert "time_remaining_seconds" in data[0]


@pytest.mark.asyncio
async def test_deliver_baby_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test successful baby delivery."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 795},
        user_id=user.id,
    )

    # Create pregnancy and set it to be due
    mother = await _adult(async_session, vault.id, GenderEnum.FEMALE)
    father = await _adult(async_session, vault.id, GenderEnum.MALE)

    from app.services.breeding_service import breeding_service

    pregnancy = await breeding_service.create_pregnancy(
        async_session,
        mother.id,
        father.id,
    )

    # Manually set pregnancy to be due (in the past)
    pregnancy.due_at = datetime.now(UTC) - timedelta(minutes=1)
    await async_session.commit()

    response = await async_client.post(
        f"/pregnancies/{pregnancy.id}/deliver",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "child_id" in data
    assert "message" in data

    # Verify pregnancy status updated
    pregnancy_check = await async_client.get(
        f"/pregnancies/{pregnancy.id}",
        headers=superuser_token_headers,
    )
    assert pregnancy_check.json()["status"] == "delivered"


# =============================================================================
# Debug Endpoint Tests (Superuser-only)
# =============================================================================


@pytest.mark.asyncio
async def test_force_conception_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test force-conception creates pregnancy for superuser."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 701},
        user_id=user.id,
    )

    mother = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            first_name="ForceConception",
            last_name="Mother",
            gender=GenderEnum.FEMALE,
            rarity=RarityEnum.COMMON,
            is_adult=True,
            age_group=AgeGroupEnum.ADULT,
            birth_date=datetime(2000, 1, 1),
            max_health=100,
            health=100,
            vault_id=str(vault.id),
        ),
    )
    father = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            first_name="ForceConception",
            last_name="Father",
            gender=GenderEnum.MALE,
            rarity=RarityEnum.COMMON,
            is_adult=True,
            age_group=AgeGroupEnum.ADULT,
            birth_date=datetime(2000, 1, 1),
            max_health=100,
            health=100,
            vault_id=str(vault.id),
        ),
    )

    response = await async_client.post(
        "/pregnancies/debug/force-conception",
        headers=superuser_token_headers,
        params={"mother_id": str(mother.id), "father_id": str(father.id)},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mother_id"] == str(mother.id)
    assert data["father_id"] == str(father.id)
    assert data["status"] == "pregnant"


@pytest.mark.asyncio
async def test_accelerate_pregnancy_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test accelerate-pregnancy sets due_at to past for superuser."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 704},
        user_id=user.id,
    )

    mother = await _adult(async_session, vault.id, GenderEnum.FEMALE)
    father = await _adult(async_session, vault.id, GenderEnum.MALE)

    from app.services.breeding_service import breeding_service

    pregnancy = await breeding_service.create_pregnancy(async_session, mother.id, father.id)

    assert not pregnancy.is_due

    response = await async_client.post(
        f"/pregnancies/{pregnancy.id}/debug/accelerate",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_due"] is True
    assert data["progress_percentage"] == 100.0
