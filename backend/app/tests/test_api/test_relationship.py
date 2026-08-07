"""Tests for relationship API endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.schemas.dweller import DwellerCreateCommonOverride
from app.utils.exceptions import AccessDeniedException

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
async def test_get_relationship_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
):
    """Test getting a non-existent relationship returns 404."""
    from uuid import uuid4

    non_existent_id = uuid4()

    response = await async_client.get(
        f"/relationships/{non_existent_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


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


# ---------------------------------------------------------------------------
# Mock-based tests for uncovered endpoint paths
# ---------------------------------------------------------------------------


def _make_mock_relationship(**overrides: object) -> MagicMock:
    """Create a mock relationship object with all attributes needed for serialization."""
    now = datetime.now(UTC)
    rid = overrides.pop("id", uuid4())
    attrs: dict[str, object] = {
        "id": rid,
        "dweller_1_id": overrides.pop("dweller_1_id", uuid4()),
        "dweller_2_id": overrides.pop("dweller_2_id", uuid4()),
        "relationship_type": overrides.pop("relationship_type", "acquaintance"),
        "affinity": overrides.pop("affinity", 50),
        "created_at": overrides.pop("created_at", now),
        "updated_at": overrides.pop("updated_at", now),
        **overrides,
    }
    mock = MagicMock()
    for key, value in attrs.items():
        setattr(mock, key, value)
    return mock


# --- GET /relationships/vault/{vault_id} -----------------------------------


@pytest.mark.asyncio
async def test_get_vault_relationships_access_denied(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /relationships/vault/{id} returns 403 when user doesn't own vault."""
    with patch(
        "app.api.v1.endpoints.relationship.get_user_vault_or_403",
        AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
    ):
        response = await async_client.get(
            f"/relationships/vault/{uuid4()}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 403


# --- GET /relationships/{relationship_id} ----------------------------------


@pytest.mark.asyncio
async def test_get_relationship_access_denied(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /relationships/{id} returns 403 when dweller access check fails."""
    mock_rel = _make_mock_relationship()

    with (
        patch(
            "app.api.v1.endpoints.relationship.relationship_crud.get",
            AsyncMock(return_value=mock_rel),
        ),
        patch(
            "app.api.v1.endpoints.relationship.verify_dweller_access",
            AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
        ),
    ):
        response = await async_client.get(
            f"/relationships/{mock_rel.id}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 403


# --- POST /relationships/ --------------------------------------------------


@pytest.mark.asyncio
async def test_create_relationship_dweller_access_denied(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /relationships/ returns 403 when user cannot access dweller 1."""
    d1_id = uuid4()
    d2_id = uuid4()

    with (
        patch(
            "app.api.v1.endpoints.relationship.verify_dweller_access",
            AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
        ),
    ):
        response = await async_client.post(
            "/relationships/",
            headers=superuser_token_headers,
            json={"dweller_1_id": str(d1_id), "dweller_2_id": str(d2_id)},
        )
    assert response.status_code == 403


# --- PUT /relationships/{id}/romance ---------------------------------------


@pytest.mark.asyncio
async def test_initiate_romance_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """PUT /relationships/{id}/romance returns 404 when relationship not found."""
    fake_id = uuid4()

    with patch(
        "app.api.v1.endpoints.relationship.relationship_crud.get",
        AsyncMock(return_value=None),
    ):
        response = await async_client.put(
            f"/relationships/{fake_id}/romance",
            headers=superuser_token_headers,
        )
    assert response.status_code == 404
    assert "Relationship not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_initiate_romance_access_denied(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """PUT /relationships/{id}/romance returns 403 when dweller access fails."""
    mock_rel = _make_mock_relationship()

    with (
        patch(
            "app.api.v1.endpoints.relationship.relationship_crud.get",
            AsyncMock(return_value=mock_rel),
        ),
        patch(
            "app.api.v1.endpoints.relationship.verify_dweller_access",
            AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
        ),
    ):
        response = await async_client.put(
            f"/relationships/{mock_rel.id}/romance",
            headers=superuser_token_headers,
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_initiate_romance_value_error(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """PUT /relationships/{id}/romance returns 400 when ValueError from service."""
    mock_rel = _make_mock_relationship()

    with (
        patch(
            "app.api.v1.endpoints.relationship.relationship_crud.get",
            AsyncMock(return_value=mock_rel),
        ),
        patch(
            "app.api.v1.endpoints.relationship.verify_dweller_access",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.relationship.relationship_service.initiate_romance",
            AsyncMock(side_effect=ValueError("Affinity not high enough")),
        ),
    ):
        response = await async_client.put(
            f"/relationships/{mock_rel.id}/romance",
            headers=superuser_token_headers,
        )
    assert response.status_code == 400
    assert "Affinity not high enough" in response.json()["detail"]


# --- PUT /relationships/{id}/partner ---------------------------------------


@pytest.mark.asyncio
async def test_make_partners_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """PUT /relationships/{id}/partner returns 404 when relationship not found."""
    fake_id = uuid4()

    with patch(
        "app.api.v1.endpoints.relationship.relationship_crud.get",
        AsyncMock(return_value=None),
    ):
        response = await async_client.put(
            f"/relationships/{fake_id}/partner",
            headers=superuser_token_headers,
        )
    assert response.status_code == 404
    assert "Relationship not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_make_partners_access_denied(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """PUT /relationships/{id}/partner returns 403 when dweller access fails."""
    mock_rel = _make_mock_relationship()

    with (
        patch(
            "app.api.v1.endpoints.relationship.relationship_crud.get",
            AsyncMock(return_value=mock_rel),
        ),
        patch(
            "app.api.v1.endpoints.relationship.verify_dweller_access",
            AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
        ),
    ):
        response = await async_client.put(
            f"/relationships/{mock_rel.id}/partner",
            headers=superuser_token_headers,
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_make_partners_value_error(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """PUT /relationships/{id}/partner returns 400 when ValueError from service."""
    mock_rel = _make_mock_relationship()

    with (
        patch(
            "app.api.v1.endpoints.relationship.relationship_crud.get",
            AsyncMock(return_value=mock_rel),
        ),
        patch(
            "app.api.v1.endpoints.relationship.verify_dweller_access",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.relationship.relationship_service.make_partners",
            AsyncMock(side_effect=ValueError("Must be romantic first")),
        ),
    ):
        response = await async_client.put(
            f"/relationships/{mock_rel.id}/partner",
            headers=superuser_token_headers,
        )
    assert response.status_code == 400
    assert "Must be romantic first" in response.json()["detail"]


# --- DELETE /relationships/{id} --------------------------------------------


@pytest.mark.asyncio
async def test_break_up_not_found(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """DELETE /relationships/{id} returns 404 when relationship not found."""
    fake_id = uuid4()

    with patch(
        "app.api.v1.endpoints.relationship.relationship_crud.get",
        AsyncMock(return_value=None),
    ):
        response = await async_client.delete(
            f"/relationships/{fake_id}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 404
    assert "Relationship not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_break_up_access_denied(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """DELETE /relationships/{id} returns 403 when dweller access fails."""
    mock_rel = _make_mock_relationship()

    with (
        patch(
            "app.api.v1.endpoints.relationship.relationship_crud.get",
            AsyncMock(return_value=mock_rel),
        ),
        patch(
            "app.api.v1.endpoints.relationship.verify_dweller_access",
            AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
        ),
    ):
        response = await async_client.delete(
            f"/relationships/{mock_rel.id}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_break_up_value_error(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """DELETE /relationships/{id} returns 400 when ValueError from service."""
    mock_rel = _make_mock_relationship()

    with (
        patch(
            "app.api.v1.endpoints.relationship.relationship_crud.get",
            AsyncMock(return_value=mock_rel),
        ),
        patch(
            "app.api.v1.endpoints.relationship.verify_dweller_access",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.relationship.relationship_service.break_up",
            AsyncMock(side_effect=ValueError("Cannot break up an acquaintance relationship")),
        ),
    ):
        response = await async_client.delete(
            f"/relationships/{mock_rel.id}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 400
    assert "Cannot break up" in response.json()["detail"]


# --- POST /relationships/vault/{vault_id}/quick-pair -----------------------


@pytest.mark.asyncio
async def test_quick_pair_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /relationships/vault/{id}/quick-pair returns 200 on successful pairing."""
    vault_id = uuid4()
    mock_rel = _make_mock_relationship(relationship_type="partner", affinity=90)

    with (
        patch(
            "app.api.v1.endpoints.relationship.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.relationship.relationship_service.quick_pair_dwellers",
            AsyncMock(return_value=mock_rel),
        ),
    ):
        response = await async_client.post(
            f"/relationships/vault/{vault_id}/quick-pair",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["relationship_type"] == "partner"
    assert data["affinity"] == 90
    assert data["id"] == str(mock_rel.id)


@pytest.mark.asyncio
async def test_quick_pair_access_denied(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /relationships/vault/{id}/quick-pair returns 403 when user doesn't own vault."""
    vault_id = uuid4()

    with patch(
        "app.api.v1.endpoints.relationship.get_user_vault_or_403",
        AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
    ):
        response = await async_client.post(
            f"/relationships/vault/{vault_id}/quick-pair",
            headers=superuser_token_headers,
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_quick_pair_value_error(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /relationships/vault/{id}/quick-pair returns 400 when ValueError from service."""
    vault_id = uuid4()

    with (
        patch(
            "app.api.v1.endpoints.relationship.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.api.v1.endpoints.relationship.relationship_service.quick_pair_dwellers",
            AsyncMock(side_effect=ValueError("Not enough compatible dwellers")),
        ),
    ):
        response = await async_client.post(
            f"/relationships/vault/{vault_id}/quick-pair",
            headers=superuser_token_headers,
        )
    assert response.status_code == 400
    assert "Not enough compatible dwellers" in response.json()["detail"]


# --- GET /relationships/compatibility/{dweller_1_id}/{dweller_2_id} --------


@pytest.mark.asyncio
async def test_compatibility_access_denied_dweller_1(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """GET /relationships/compatibility returns 403 when cannot access dweller 1."""
    d1_id = uuid4()
    d2_id = uuid4()

    with (
        patch(
            "app.api.v1.endpoints.relationship.verify_dweller_access",
            AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
        ),
    ):
        response = await async_client.get(
            f"/relationships/compatibility/{d1_id}/{d2_id}",
            headers=superuser_token_headers,
        )
    assert response.status_code == 403


# --- POST /relationships/vault/{vault_id}/process --------------------------


@pytest.mark.asyncio
async def test_process_vault_breeding_success(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /relationships/vault/{id}/process returns 200 with breeding stats."""
    vault_id = uuid4()
    mock_stats = {
        "conceptions": 1,
        "births": 0,
        "pairs_processed": 3,
        "relationships_processed": 5,
    }

    with (
        patch(
            "app.api.v1.endpoints.relationship.get_user_vault_or_403",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.game_loop.game_loop_service._process_breeding",
            AsyncMock(return_value=mock_stats),
        ),
    ):
        response = await async_client.post(
            f"/relationships/vault/{vault_id}/process",
            headers=superuser_token_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Breeding and relationships processed successfully"
    assert data["stats"] == mock_stats


@pytest.mark.asyncio
async def test_process_vault_breeding_access_denied(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """POST /relationships/vault/{id}/process returns 403 when user doesn't own vault."""
    vault_id = uuid4()

    with patch(
        "app.api.v1.endpoints.relationship.get_user_vault_or_403",
        AsyncMock(side_effect=AccessDeniedException("The user doesn't have enough privileges")),
    ):
        response = await async_client.post(
            f"/relationships/vault/{vault_id}/process",
            headers=superuser_token_headers,
        )
    assert response.status_code == 403
