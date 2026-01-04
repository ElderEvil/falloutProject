"""Tests for relationship API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.dweller import DwellerCreateCommonOverride

pytestmark = pytest.mark.asyncio(scope="module")


@pytest.mark.asyncio
async def test_get_vault_relationships_empty(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test getting relationships for vault with no relationships."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 899},
        user_id=user.id,
    )

    response = await async_client.get(
        f"/relationships/vault/{vault.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_create_relationship(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test creating a relationship between two dwellers."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 898},
        user_id=user.id,
    )

    # Create two dwellers
    dweller1 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )
    dweller2 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )

    response = await async_client.post(
        "/relationships/",
        headers=superuser_token_headers,
        json={
            "dweller_1_id": str(dweller1.id),
            "dweller_2_id": str(dweller2.id),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dweller_1_id"] == str(dweller1.id)
    assert data["dweller_2_id"] == str(dweller2.id)
    assert data["relationship_type"] == "acquaintance"
    assert data["affinity"] >= 0


@pytest.mark.asyncio
async def test_get_relationship(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test getting a specific relationship."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 897},
        user_id=user.id,
    )

    # Create dwellers and relationship
    dweller1 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )
    dweller2 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )

    create_response = await async_client.post(
        "/relationships/",
        headers=superuser_token_headers,
        json={
            "dweller_1_id": str(dweller1.id),
            "dweller_2_id": str(dweller2.id),
        },
    )
    relationship_id = create_response.json()["id"]

    response = await async_client.get(
        f"/relationships/{relationship_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == relationship_id


@pytest.mark.asyncio
async def test_initiate_romance(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test initiating romance from acquaintance relationship."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 896},
        user_id=user.id,
    )

    # Create dwellers and relationship
    dweller1 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )
    dweller2 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )

    create_response = await async_client.post(
        "/relationships/",
        headers=superuser_token_headers,
        json={
            "dweller_1_id": str(dweller1.id),
            "dweller_2_id": str(dweller2.id),
        },
    )
    relationship_id = create_response.json()["id"]

    # Manually set affinity to 70+ to allow romance
    from uuid import UUID

    from sqlmodel import select

    from app.models.relationship import Relationship

    result = await async_session.execute(select(Relationship).where(Relationship.id == UUID(relationship_id)))
    relationship = result.scalar_one()
    relationship.affinity = 75
    await async_session.commit()

    response = await async_client.put(
        f"/relationships/{relationship_id}/romance",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["relationship_type"] == "romantic"


@pytest.mark.asyncio
async def test_make_partners(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test making dwellers partners from romantic relationship."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 895},
        user_id=user.id,
    )

    # Create dwellers
    dweller1 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )
    dweller2 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )

    # Create and upgrade relationship to romantic
    from app.services.relationship_service import relationship_service

    relationship = await relationship_service.get_or_create_relationship(async_session, dweller1.id, dweller2.id)
    relationship.affinity = 85
    relationship.relationship_type = "romantic"
    await async_session.commit()

    response = await async_client.put(
        f"/relationships/{relationship.id}/partner",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["relationship_type"] == "partner"

    # Verify dwellers now have partner_id set
    await async_session.refresh(dweller1)
    await async_session.refresh(dweller2)
    assert dweller1.partner_id == dweller2.id
    assert dweller2.partner_id == dweller1.id


@pytest.mark.asyncio
async def test_break_up_relationship(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test breaking up a relationship."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 894},
        user_id=user.id,
    )

    # Create dwellers and romantic relationship
    dweller1 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )
    dweller2 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )

    from app.services.relationship_service import relationship_service

    relationship = await relationship_service.get_or_create_relationship(async_session, dweller1.id, dweller2.id)
    relationship.relationship_type = "romantic"
    await async_session.commit()

    response = await async_client.delete(
        f"/relationships/{relationship.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert "ended" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_calculate_compatibility(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
):
    """Test calculating compatibility score between two dwellers."""
    user = await crud.user.get_by_email(async_session, email=settings.FIRST_SUPERUSER_EMAIL)
    vault = await crud.vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 893},
        user_id=user.id,
    )

    # Create two dwellers with similar stats
    dweller1 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="male"),
    )
    dweller2 = await crud.dweller.create_random(
        async_session,
        vault.id,
        obj_in=DwellerCreateCommonOverride(gender="female"),
    )

    response = await async_client.get(
        f"/relationships/compatibility/{dweller1.id}/{dweller2.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "special_score" in data
    assert "happiness_score" in data
    assert "level_score" in data
    assert "proximity_score" in data
    assert 0.0 <= data["score"] <= 1.0
