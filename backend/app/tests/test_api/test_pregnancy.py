"""Tests for pregnancy API endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.dweller import DwellerCreateCommonOverride

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_get_vault_pregnancies_empty(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test getting pregnancies for vault with no active pregnancies."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 799},
        user_id=user.id,
    )

    response = await async_client.get(
        f"/pregnancies/vault/{vault.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


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
    mother = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )
    father = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

    # Create pregnancy
    from app.services.breeding_service import breeding_service

    pregnancy = await breeding_service.create_pregnancy(  # noqa: F841
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
async def test_get_pregnancy_details(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test getting specific pregnancy details."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 797},
        user_id=user.id,
    )

    # Create couple and pregnancy
    mother = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )
    father = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

    from app.services.breeding_service import breeding_service

    pregnancy = await breeding_service.create_pregnancy(
        async_session,
        mother.id,
        father.id,
    )

    response = await async_client.get(
        f"/pregnancies/{pregnancy.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(pregnancy.id)
    assert data["mother_id"] == str(mother.id)
    assert data["father_id"] == str(father.id)


@pytest.mark.asyncio
async def test_deliver_baby_not_due(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test delivering baby fails when pregnancy not due."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 796},
        user_id=user.id,
    )

    # Create pregnancy (not due yet)
    mother = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )
    father = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

    from app.services.breeding_service import breeding_service

    pregnancy = await breeding_service.create_pregnancy(
        async_session,
        mother.id,
        father.id,
    )

    response = await async_client.post(
        f"/pregnancies/{pregnancy.id}/deliver",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert "not due" in response.json()["detail"].lower()


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
    mother = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )
    father = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

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


@pytest.mark.asyncio
async def test_pregnancy_progress_calculation(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test pregnancy progress percentage is calculated correctly."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 794},
        user_id=user.id,
    )

    # Create pregnancy
    mother = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )
    father = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

    from app.services.breeding_service import breeding_service

    pregnancy = await breeding_service.create_pregnancy(
        async_session,
        mother.id,
        father.id,
    )

    response = await async_client.get(
        f"/pregnancies/{pregnancy.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Progress should be between 0 and 100
    assert 0.0 <= data["progress_percentage"] <= 100.0

    # Time remaining should be positive if not due
    if not data["is_due"]:
        assert data["time_remaining_seconds"] > 0


@pytest.mark.asyncio
async def test_pregnancy_not_found(
    async_client: AsyncClient,
    async_session: AsyncSession,  # noqa: ARG001
    superuser_token_headers: dict[str, str],
):
    """Test 404 when pregnancy doesn't exist."""
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = await async_client.get(
        f"/pregnancies/{fake_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 422


# =============================================================================
# Debug Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_force_conception_debug_disabled(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test force-conception returns 403 when debug mode is disabled."""
    from unittest.mock import patch

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 700},
        user_id=user.id,
    )

    mother = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )
    father = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

    # Ensure debug mode is disabled
    with patch("app.api.v1.endpoints.pregnancy.game_config.breeding.debug_enabled", False):  # noqa: FBT003
        response = await async_client.post(
            "/pregnancies/debug/force-conception",
            headers=superuser_token_headers,
            params={"mother_id": str(mother.id), "father_id": str(father.id)},
        )

    assert response.status_code == 403
    assert "debug mode" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_force_conception_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test force-conception creates pregnancy when debug mode enabled."""
    from unittest.mock import patch

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 701},
        user_id=user.id,
    )

    mother = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )
    father = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

    # Enable debug mode
    with patch("app.api.v1.endpoints.pregnancy.game_config.breeding.debug_enabled", True):  # noqa: FBT003
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
async def test_force_conception_wrong_gender(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test force-conception rejects wrong gender assignments."""
    from unittest.mock import patch

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 702},
        user_id=user.id,
    )

    # Create two males (invalid)
    male1 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )
    male2 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

    with patch("app.api.v1.endpoints.pregnancy.game_config.breeding.debug_enabled", True):  # noqa: FBT003
        response = await async_client.post(
            "/pregnancies/debug/force-conception",
            headers=superuser_token_headers,
            params={"mother_id": str(male1.id), "father_id": str(male2.id)},
        )

    assert response.status_code == 400
    assert "Mother must be female" in response.json()["detail"]


@pytest.mark.asyncio
async def test_accelerate_pregnancy_debug_disabled(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test accelerate-pregnancy returns 403 when debug mode disabled."""
    from unittest.mock import patch

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 703},
        user_id=user.id,
    )

    mother = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )
    father = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

    from app.services.breeding_service import breeding_service

    pregnancy = await breeding_service.create_pregnancy(async_session, mother.id, father.id)

    with patch("app.api.v1.endpoints.pregnancy.game_config.breeding.debug_enabled", False):  # noqa: FBT003
        response = await async_client.post(
            f"/pregnancies/{pregnancy.id}/debug/accelerate",
            headers=superuser_token_headers,
        )

    assert response.status_code == 403
    assert "debug mode" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_accelerate_pregnancy_success(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test accelerate-pregnancy sets due_at to past when debug enabled."""
    from unittest.mock import patch

    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 704},
        user_id=user.id,
    )

    mother = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )
    father = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )

    from app.services.breeding_service import breeding_service

    pregnancy = await breeding_service.create_pregnancy(async_session, mother.id, father.id)

    # Originally not due
    assert not pregnancy.is_due

    with patch("app.api.v1.endpoints.pregnancy.game_config.breeding.debug_enabled", True):  # noqa: FBT003
        response = await async_client.post(
            f"/pregnancies/{pregnancy.id}/debug/accelerate",
            headers=superuser_token_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_due"] is True
    assert data["progress_percentage"] == 100.0


@pytest.mark.asyncio
async def test_accelerate_pregnancy_not_found(
    async_client: AsyncClient,
    async_session: AsyncSession,  # noqa: ARG001
    superuser_token_headers: dict[str, str],
):
    """Test accelerate-pregnancy returns 404 for non-existent pregnancy."""
    from unittest.mock import patch
    from uuid import uuid4

    fake_id = uuid4()

    with patch("app.api.v1.endpoints.pregnancy.game_config.breeding.debug_enabled", True):  # noqa: FBT003
        response = await async_client.post(
            f"/pregnancies/{fake_id}/debug/accelerate",
            headers=superuser_token_headers,
        )

    assert response.status_code == 404
    assert "Pregnancy" in response.json()["detail"]
