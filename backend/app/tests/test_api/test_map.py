"""Tests for map API endpoints."""

import random
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.wasteland_location import (
    DwellerLocationRelationEnum,
    LocationTypeEnum,
    WastelandLocation,
)
from app.schemas.common import GenderEnum, RarityEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.map_service import map_service
from app.tests.utils.user import authentication_token_from_email
from app.tests.utils.utils import get_gender_based_name, random_lower_string

# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------


async def _create_second_user_and_vault(
    async_session: AsyncSession,
) -> tuple[str, Vault]:
    """Create a second user + vault. Returns (email, vault)."""
    username = random_lower_string()[:24]
    email = f"{username}@example.com"
    user_in = UserCreate(username=username, email=email, password=random_lower_string())
    user = await crud.user.create(db_session=async_session, obj_in=user_in)

    vault_in = VaultCreateWithUserID(
        number=666,
        bottle_caps=500,
        happiness=50,
        power=50,
        food=50,
        water=50,
        user_id=user.id,
    )
    vault = await crud.vault.create(db_session=async_session, obj_in=vault_in)
    return email, vault


# ------------------------------------------------------------------
# happy path
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vault_map_happy(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    vault: Vault,
) -> None:
    """GET /map/vault/{vault_id} returns VaultMapResponse with home marker + vault_markers."""
    response = await async_client.get(
        f"/map/vault/{vault.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Response shape
    assert "locations" in data
    assert "vault_markers" in data

    # At least one location (HOME_VAULT marker seeded lazily)
    assert len(data["locations"]) >= 1
    home_types = [loc["type"] for loc in data["locations"] if loc["type"] == LocationTypeEnum.HOME_VAULT]
    assert len(home_types) >= 1

    # 3-7 computed vault markers
    assert 3 <= len(data["vault_markers"]) <= 7
    for m in data["vault_markers"]:
        assert m["type"] == "vault"
        assert "name" in m
        assert "coord_x" in m
        assert "coord_y" in m
        assert "description" in m


@pytest.mark.asyncio
async def test_get_vault_map_includes_bio_places(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault: Vault,
    dweller: Dweller,
) -> None:
    """After registering bio places, GET /map returns the location with dwellers populated."""
    await map_service.register_bio_places(
        async_session,
        dweller,
        origin_place="Megaton",
        visited_places=["Rivet City", "Tenpenny Tower"],
    )

    # Second dweller also from Megaton (use create_random for full defaults)
    dw2 = await crud.dweller.create_random(db_session=async_session, vault_id=vault.id)
    await map_service.register_bio_places(
        async_session,
        dw2,
        origin_place="Megaton",
        visited_places=["Tenpenny Tower"],
    )

    response = await async_client.get(
        f"/map/vault/{vault.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Must have at least one location with dwellers
    locations_with_dwellers = [loc for loc in data["locations"] if loc["dwellers"]]
    assert len(locations_with_dwellers) >= 1

    # Verify a dweller ref shape
    first_dwellers = locations_with_dwellers[0]["dwellers"]
    assert len(first_dwellers) >= 1
    ref = first_dwellers[0]
    assert "dweller_id" in ref
    assert "first_name" in ref
    assert "relation" in ref


@pytest.mark.asyncio
async def test_get_location_detail_with_dwellers(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault: Vault,
    dweller: Dweller,
) -> None:
    """GET /map/vault/{vault_id}/locations/{location_id} returns linked dweller refs."""
    await map_service.register_bio_places(
        async_session,
        dweller,
        origin_place="Rivet City",
        visited_places=[],
    )

    # Fetch the persisted location
    from app.crud.wasteland_location import wasteland_location as wl_crud

    normalized = "rivet city"
    loc = await wl_crud.get_by_normalized(async_session, vault.id, normalized)
    assert loc is not None

    response = await async_client.get(
        f"/map/vault/{vault.id}/locations/{loc.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(loc.id)
    assert data["type"] == LocationTypeEnum.ORIGIN
    assert len(data["dwellers"]) >= 1

    # Dweller ref shape
    ref = data["dwellers"][0]
    assert ref["dweller_id"] == str(dweller.id)
    assert ref["first_name"] == dweller.first_name
    assert ref["relation"] == DwellerLocationRelationEnum.ORIGIN


# ------------------------------------------------------------------
# failures
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vault_map_another_users_vault_returns_403(
    async_client: AsyncClient,
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """A non-superuser normal user cannot access another user's vault."""
    # Create a second user and get THEIR auth headers
    second_email, _ = await _create_second_user_and_vault(async_session)
    second_user_headers = await authentication_token_from_email(
        client=async_client,
        email=second_email,
        db_session=async_session,
    )

    response = await async_client.get(
        f"/map/vault/{vault.id}",
        headers=second_user_headers,
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_get_location_detail_random_id_returns_404(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
    vault: Vault,
) -> None:
    """GET location detail with a random non-existent uuid → 404."""
    random_id = uuid4()
    response = await async_client.get(
        f"/map/vault/{vault.id}/locations/{random_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_location_detail_foreign_vault_location_returns_404(
    async_client: AsyncClient,
    async_session: AsyncSession,
    superuser_token_headers: dict[str, str],
    vault: Vault,
    dweller: Dweller,
) -> None:
    """A location owned by a different vault → 404, not 403 or 200."""
    # Create location under THIS vault
    from app.crud.wasteland_location import wasteland_location as wl_crud

    loc = await wl_crud.get_or_create(
        async_session,
        vault_id=vault.id,
        name="Underworld",
        type=LocationTypeEnum.VISITED,
    )

    # Create second user+vault
    _, second_vault = await _create_second_user_and_vault(async_session)

    # Request this vault's location BUT address it under the SECOND vault's id
    response = await async_client.get(
        f"/map/vault/{second_vault.id}/locations/{loc.id}",
        headers=superuser_token_headers,
    )
    # The location belongs to vault, not second_vault → should be 404
    assert response.status_code == 404


# ------------------------------------------------------------------
# OpenAPI schema assertion
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openapi_schema_includes_map_schemas(
    async_client: AsyncClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """FastAPI OpenAPI JSON must include the map response schemas."""
    response = await async_client.get(
        "/openapi.json",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    schema = response.json()

    schemas = schema.get("components", {}).get("schemas", {})
    # WastelandLocationRead is a base model — Pydantic v2 inlines its fields
    # into WastelandLocationWithDwellers rather than exposing it as a separate
    # component.  Assert the schemas actually returned by the map endpoints.
    for required_schema in ("VaultMapResponse", "WastelandLocationWithDwellers", "VaultMarkerRead", "DwellerRef"):
        assert required_schema in schemas, f"{required_schema} missing from OpenAPI schemas"
