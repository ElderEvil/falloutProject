"""Tests for MapService — registration and map assembly."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.wasteland_location import LocationTypeEnum, WastelandLocation
from app.services.map_service import map_service
from app.utils.places import normalize_place_name, seeded_vault_specs

# ---------------------------------------------------------------------------
# register_bio_places
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_bio_places_creates_origin_and_visited(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """origin "Megaton" + 6 visited names → 1 ORIGIN + exactly 5 VISITED rows."""
    visited_names = [
        "Rivet City",
        "Tenpenny Tower",
        "Paradise Falls",
        "Canterbury Commons",
        "Big Town",
        "Little Lamplight",  # 6th — should be dropped (cap=5)
    ]
    await map_service.register_bio_places(
        async_session,
        dweller,
        origin_place="Megaton",
        visited_places=visited_names,
    )

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    origin_rows = [r for r in rows if r.type == LocationTypeEnum.ORIGIN]
    visited_rows = [r for r in rows if r.type == LocationTypeEnum.VISITED]

    assert len(origin_rows) == 1
    assert len(visited_rows) == 5

    assert origin_rows[0].normalized_name == normalize_place_name("Megaton")


@pytest.mark.asyncio
async def test_register_bio_places_second_call_reuses(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Second call with differently-cased origin reuses the same row (1 total)."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Megaton", visited_places=[])
    await map_service.register_bio_places(async_session, dweller, origin_place=" MEGATON ", visited_places=[])

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    origin_rows = [r for r in rows if r.type == LocationTypeEnum.ORIGIN]
    assert len(origin_rows) == 1


@pytest.mark.asyncio
async def test_register_bio_places_skips_wasteland(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """origin_place="Wasteland" normalises into GENERIC_ORIGIN_SKIP → creates nothing."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Wasteland", visited_places=[])

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_register_bio_places_skips_visited_wasteland(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Visited names in the skip-list are dropped."""
    await map_service.register_bio_places(
        async_session, dweller, origin_place="Megaton", visited_places=["the wasteland", "unknown"]
    )

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    # Only the origin should exist
    assert len(rows) == 1
    assert rows[0].type == LocationTypeEnum.ORIGIN


# ---------------------------------------------------------------------------
# register_discovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_discovery_sets_exploration_id(async_session: AsyncSession, vault: Vault) -> None:
    """register_discovery upserts a DISCOVERY row with exploration_id."""
    from uuid import uuid4

    exploration_id = uuid4()
    await map_service.register_discovery(async_session, vault.id, exploration_id, "Abandoned Bunker")

    result = await async_session.execute(select(WastelandLocation).where(WastelandLocation.vault_id == vault.id))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].type == LocationTypeEnum.DISCOVERY
    assert rows[0].exploration_id == exploration_id
    assert rows[0].name == "Abandoned Bunker"


@pytest.mark.asyncio
async def test_register_discovery_forced_db_error_logged_not_raised(
    async_session: AsyncSession, vault: Vault, caplog
) -> None:
    """A forced DB error inside register_discovery is logged, not raised."""
    from uuid import uuid4

    # Monkeypatch get_or_create to raise an SQLAlchemyError
    with patch(
        "app.crud.wasteland_location.wasteland_location.get_or_create",
        side_effect=SQLAlchemyError("forced"),
    ):
        # Must NOT raise
        await map_service.register_discovery(async_session, vault.id, uuid4(), "Crash Site")

    # The exception should have been logged
    assert any("register_discovery failed" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# ensure_home_marker  /  link_home_origin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_home_marker_idempotent(async_session: AsyncSession, vault: Vault) -> None:
    """Calling ensure_home_marker twice yields exactly one HOME_VAULT row."""
    await map_service.ensure_home_marker(async_session, vault)
    await map_service.ensure_home_marker(async_session, vault)

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    home_rows = [r for r in rows if r.type == LocationTypeEnum.HOME_VAULT]
    assert len(home_rows) == 1
    assert home_rows[0].coord_x == 50.0
    assert home_rows[0].coord_y == 50.0
    assert home_rows[0].name == f"Vault {vault.number:03}"


@pytest.mark.asyncio
async def test_link_home_origin_best_effort(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """link_home_origin creates the home marker and links dweller."""
    await map_service.link_home_origin(async_session, dweller, vault)

    home = await async_session.execute(
        select(WastelandLocation).where(
            WastelandLocation.vault_id == vault.id,
            WastelandLocation.type == LocationTypeEnum.HOME_VAULT,
        )
    )
    home_loc = home.scalar_one_or_none()
    assert home_loc is not None


# ---------------------------------------------------------------------------
# get_vault_map
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vault_map_seeds_home_marker_once(async_session: AsyncSession, vault: Vault) -> None:
    """Repeated get_vault_map calls seed the home marker exactly once."""
    await map_service.get_vault_map(async_session, vault)
    await map_service.get_vault_map(async_session, vault)

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    home_rows = [r for r in rows if r.type == LocationTypeEnum.HOME_VAULT]
    assert len(home_rows) == 1


@pytest.mark.asyncio
async def test_get_vault_map_returns_vault_markers(async_session: AsyncSession, vault: Vault) -> None:
    """get_vault_map returns computed VaultMarkerRead items (3-7, excluding home)."""
    response = await map_service.get_vault_map(async_session, vault)

    assert response.vault_markers is not None
    assert 3 <= len(response.vault_markers) <= 7

    # None of the computed markers should match the home vault
    home_name = f"Vault {vault.number:03}"
    for marker in response.vault_markers:
        assert marker.name != home_name
        assert marker.type == "vault"
        assert "Unexplored vault signal" in marker.description

    # Locations list should contain at least the home marker
    assert len(response.locations) >= 1
    home_locs = [loc for loc in response.locations if loc.type == LocationTypeEnum.HOME_VAULT]
    assert len(home_locs) == 1


@pytest.mark.asyncio
async def test_get_vault_map_includes_dweller_refs(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """get_vault_map includes dweller references on location rows."""
    # Register bio places first so dweller is linked to locations
    await map_service.register_bio_places(
        async_session,
        dweller,
        origin_place="Megaton",
        visited_places=["Rivet City"],
    )

    response = await map_service.get_vault_map(async_session, vault)

    # Find the Megaton location and check it has the dweller ref
    megaton = next((loc for loc in response.locations if loc.name == "Megaton"), None)
    assert megaton is not None
    assert len(megaton.dwellers) == 1
    assert megaton.dwellers[0].dweller_id == dweller.id
    assert megaton.dwellers[0].relation == "origin"


@pytest.mark.asyncio
async def test_register_bio_places_forced_db_error_logged_not_raised(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, caplog
) -> None:
    """A forced DB error inside register_bio_places is logged, not raised."""
    with patch(
        "app.crud.wasteland_location.wasteland_location.get_or_create",
        side_effect=SQLAlchemyError("forced"),
    ):
        # Must NOT raise
        await map_service.register_bio_places(
            async_session, dweller, origin_place="Megaton", visited_places=["Rivet City"]
        )

    assert any("register_bio_places failed" in record.message for record in caplog.records)
