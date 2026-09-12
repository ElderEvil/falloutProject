"""Tests for MapService — registration and map assembly."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import LocationTypeEnum
from app.models.dweller import Dweller
from app.models.notification import Notification
from app.models.vault import Vault
from app.models.world_location import DwellerLocation, VaultLocationState, WorldLocation
from app.schemas.common import RarityEnum
from app.services.map_service import map_service
from app.utils.places import normalize_place_name

# ---------------------------------------------------------------------------
# register_bio_places
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_bio_places_rarity_scaled(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """VISITED cap follows rarity: COMMON→2, LEGENDARY→5 for 6 provided names each."""
    common_names = [
        "Megaton",
        "Rivet City",
        "Tenpenny Tower",
        "Paradise Falls",
        "Canterbury Commons",
        "Big Town",
    ]
    legendary_names = [
        "Little Lamplight",
        "Goodneighbor",
        "Diamond City",
        "The Slog",
        "Bunker Hill",
        "Republic of Dave",
    ]
    # get_or_create dedupes on (vault_id, normalized_name), so the two calls
    # must use disjoint name sets for the totals below to hold.
    dweller.rarity = RarityEnum.COMMON
    await map_service.register_bio_places(async_session, dweller, origin_place="Arefu", visited_places=common_names)
    dweller.rarity = RarityEnum.LEGENDARY
    await map_service.register_bio_places(async_session, dweller, origin_place="Arefu", visited_places=legendary_names)

    rows = (await async_session.execute(select(VaultLocationState))).scalars().all()
    origin_rows = [r for r in rows if r.type == LocationTypeEnum.ORIGIN]
    visited_rows = [r for r in rows if r.type == LocationTypeEnum.VISITED]
    assert len(origin_rows) == 1
    assert len(visited_rows) == 7


@pytest.mark.asyncio
async def test_register_bio_places_skips_visited_wasteland(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Visited names in the skip-list are dropped."""
    await map_service.register_bio_places(
        async_session, dweller, origin_place="Megaton", visited_places=["the wasteland", "unknown"]
    )

    rows = (await async_session.execute(select(VaultLocationState))).scalars().all()
    # Only the origin should exist
    assert len(rows) == 1
    assert rows[0].type == LocationTypeEnum.ORIGIN


# ---------------------------------------------------------------------------
# register_discovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_discovery_forced_db_error_logged_not_raised(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, caplog
) -> None:
    """A forced DB error inside register_discovery is logged, not raised."""

    # Monkeypatch get_or_create to raise an SQLAlchemyError
    with patch(
        "app.crud.world_location.world_location.get_or_create_location",
        side_effect=SQLAlchemyError("forced"),
    ):
        # Must NOT raise
        await map_service.register_discovery(async_session, vault.id, uuid4(), dweller.id, "Crash Site")

    # The exception should have been logged
    assert any("register_discovery failed" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# ensure_home_marker  /  link_home_origin
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# get_vault_map
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_bio_places_retries_a_transient_failure(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """One transient write error still creates all three fixture links."""
    dweller.rarity = RarityEnum.LEGENDARY
    from app.crud.world_location import world_location

    original_get_or_create = world_location.get_or_create_location
    attempts = 0

    async def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise SQLAlchemyError("transient")
        return await original_get_or_create(*args, **kwargs)

    with patch.object(world_location, "get_or_create_location", side_effect=fail_once):
        await map_service.register_bio_places(
            async_session,
            dweller,
            origin_place="Rusty Creek",
            visited_places=["Necropolis", "Brotherhood Outpost"],
        )

    links = (await async_session.execute(select(DwellerLocation))).scalars().all()
    assert len(links) == 3


@pytest.mark.asyncio
async def test_register_bio_places_handles_final_commit_failure(async_session: AsyncSession, dweller: Dweller) -> None:
    """A failed final commit remains a best-effort map-registration failure."""
    with patch.object(async_session, "commit", new=AsyncMock(side_effect=SQLAlchemyError("offline"))):
        assert await map_service.register_bio_places(async_session, dweller, "Arefu", []) is False


# ---------------------------------------------------------------------------
# Regression — DwellerReadFull has vault_id (production path)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# World-coordinate scaling (0-100 DB grid → 0-160 render world)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# is_unlocked — includes unlock state in responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vault_map_unlocked_only_hides_locked(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """unlocked_only=True excludes non-VAULT locations that are locked."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Megaton", visited_places=["Rivet City"])

    full = await map_service.get_vault_map(async_session, vault)
    filtered = await map_service.get_vault_map(async_session, vault, unlocked_only=True)

    # Full response has 1 HOME_VAULT + 2 bio locations = at least 3
    assert len(full.locations) >= 3

    # Filtered response should only have HOME_VAULT (1) since nothing is unlocked yet
    non_home = [loc for loc in filtered.locations if loc.type != LocationTypeEnum.HOME_VAULT]
    assert len(non_home) == 0, "No non-VAULT locations should appear when unlocked_only=True and nothing is unlocked"
    assert any(loc.type == LocationTypeEnum.HOME_VAULT for loc in filtered.locations)


@pytest.mark.asyncio
async def test_get_location_detail_includes_is_unlocked(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_location_detail returns is_unlocked on location and dweller refs."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Megaton", visited_places=[])

    from app.models.world_location import VaultLocationState

    loc_row = (
        await async_session.execute(
            select(VaultLocationState)
            .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
            .where(
                VaultLocationState.vault_id == vault.id,
                WorldLocation.name == "Megaton",
            )
        )
    ).scalar_one()

    detail = await map_service.get_location_detail(async_session, vault, loc_row.location_id)

    assert hasattr(detail, "is_unlocked")
    assert detail.is_unlocked is False
    assert len(detail.dwellers) == 1
    assert detail.dwellers[0].is_unlocked is False
