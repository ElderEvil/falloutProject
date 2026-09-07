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
from app.services.map_service import map_service
from app.tests.utils.utils import get_gender_based_name

# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------


# ------------------------------------------------------------------
# happy path
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# OpenAPI schema assertion
# ------------------------------------------------------------------
