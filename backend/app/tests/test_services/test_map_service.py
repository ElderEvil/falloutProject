"""Tests for MapService — registration and map assembly."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.dweller import Dweller
from app.models.notification import Notification
from app.models.vault import Vault
from app.models.wasteland_location import DwellerLocation, LocationTypeEnum, WastelandLocation
from app.schemas.common import RarityEnum
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
    # Cap scales with rarity; pin to LEGENDARY (max 5) so the 5-row assertion is deterministic.
    dweller.rarity = RarityEnum.LEGENDARY
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

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    origin_rows = [r for r in rows if r.type == LocationTypeEnum.ORIGIN]
    visited_rows = [r for r in rows if r.type == LocationTypeEnum.VISITED]
    assert len(origin_rows) == 1
    assert len(visited_rows) == 7


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
async def test_register_discovery_sets_exploration_id(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """register_discovery upserts a DISCOVERY row with exploration_id."""
    from uuid import uuid4

    exploration_id = uuid4()
    await map_service.register_discovery(async_session, vault.id, exploration_id, dweller.id, "Abandoned Bunker")

    result = await async_session.execute(select(WastelandLocation).where(WastelandLocation.vault_id == vault.id))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].type == LocationTypeEnum.DISCOVERY
    assert rows[0].exploration_id == exploration_id
    assert rows[0].name == "Abandoned Bunker"


@pytest.mark.asyncio
async def test_register_discovery_links_and_unlocks_dweller(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """register_discovery links the discovering dweller and unlocks the place."""
    from uuid import uuid4

    location = await map_service.register_discovery(async_session, vault.id, uuid4(), dweller.id, "Abandoned Bunker")
    assert location is not None

    payload = await map_service.get_vault_map(async_session, vault)
    discovery_locs = [loc for loc in payload.locations if loc.type == LocationTypeEnum.DISCOVERY]
    assert len(discovery_locs) == 1
    assert discovery_locs[0].id == location.id
    assert discovery_locs[0].is_unlocked is True


@pytest.mark.asyncio
async def test_register_discovery_forced_db_error_logged_not_raised(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, caplog
) -> None:
    """A forced DB error inside register_discovery is logged, not raised."""
    from uuid import uuid4

    # Monkeypatch get_or_create to raise an SQLAlchemyError
    with patch(
        "app.crud.wasteland_location.wasteland_location.get_or_create",
        side_effect=SQLAlchemyError("forced"),
    ):
        # Must NOT raise
        await map_service.register_discovery(async_session, vault.id, uuid4(), dweller.id, "Crash Site")

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
    """get_vault_map returns the globally consistent computed signal roster."""
    response = await map_service.get_vault_map(async_session, vault)

    assert response.vault_markers is not None
    assert 3 <= len(response.vault_markers) <= 7

    for marker in response.vault_markers:
        assert marker.type == "vault"
        assert "Unexplored vault signal" in marker.description

    # Locations list should contain at least the home marker
    assert len(response.locations) >= 1
    home_locs = [loc for loc in response.locations if loc.type == LocationTypeEnum.HOME_VAULT]
    assert len(home_locs) == 1


@pytest.mark.asyncio
async def test_register_discovery_rolls_back_with_callers_transaction(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Discovery registration must not commit before its event can be persisted."""
    location = await map_service.register_discovery(async_session, vault.id, uuid4(), dweller.id, "Rollback Depot")
    assert location is not None

    await async_session.rollback()

    rows = (
        (
            await async_session.execute(
                select(WastelandLocation).where(
                    WastelandLocation.normalized_name == normalize_place_name("Rollback Depot")
                )
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


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


@pytest.mark.asyncio
async def test_register_bio_places_retries_a_transient_failure(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """One transient write error still creates all three fixture links."""
    dweller.rarity = RarityEnum.LEGENDARY
    from app.crud.wasteland_location import wasteland_location

    original_get_or_create = wasteland_location.get_or_create
    attempts = 0

    async def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise SQLAlchemyError("transient")
        return await original_get_or_create(*args, **kwargs)

    with patch.object(wasteland_location, "get_or_create", side_effect=fail_once):
        await map_service.register_bio_places(
            async_session,
            dweller,
            origin_place="Rusty Creek",
            visited_places=["Necropolis", "Brotherhood Outpost"],
        )

    links = (await async_session.execute(select(DwellerLocation))).scalars().all()
    assert len(links) == 3


@pytest.mark.asyncio
async def test_register_bio_places_persists_failure_notification(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """An exhausted retry leaves one durable, actionable notification."""
    dweller_id = dweller.id
    with patch(
        "app.crud.wasteland_location.wasteland_location.get_or_create",
        side_effect=SQLAlchemyError("persistent"),
    ):
        await map_service.register_bio_places(
            async_session,
            dweller,
            origin_place="Rusty Creek",
            visited_places=["Necropolis", "Brotherhood Outpost"],
        )

    notifications = (await async_session.execute(select(Notification))).scalars().all()
    assert len(notifications) == 1
    assert notifications[0].notification_type.value == "map_registration_failed"
    assert notifications[0].from_dweller_id == dweller_id


# ---------------------------------------------------------------------------
# Regression — DwellerReadFull has vault_id (production path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_bio_places_with_dweller_read_full(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """register_bio_places works with a real DwellerReadFull schema object.

    The production caller (dweller_ai._register_map_places_best_effort) passes a
    DwellerReadFull, which historically lacked ``vault_id`` — causing the
    best-effort body to silently swallow AttributeError.  This test proves the
    schema now carries vault_id and the full registration pipeline works end-to-end.
    """
    from app import crud
    from app.models.wasteland_location import DwellerLocation, DwellerLocationRelationEnum
    from app.schemas.dweller import DwellerReadFull

    # Build a real DwellerReadFull from the ORM dweller — must use get_full_info
    # (or eager-load) because weapon/outfit are lazy relationships and
    # model_validate with from_attributes=True on a bare Dweller trips
    # MissingGreenlet in async context.
    dweller_read = await crud.dweller.get_full_info(async_session, dweller.id)

    # The schema MUST carry vault_id — this assertion alone fails before the fix
    assert dweller_read.vault_id == vault.id

    # Register bio places through the full pipeline
    await map_service.register_bio_places(
        async_session,
        dweller_read,
        origin_place="Megaton",
        visited_places=["Rivet City", "Goodneighbor"],
    )

    # Assert WastelandLocation rows were created
    locations = (await async_session.execute(select(WastelandLocation))).scalars().all()
    origin_rows = [r for r in locations if r.type == LocationTypeEnum.ORIGIN]
    visited_rows = [r for r in locations if r.type == LocationTypeEnum.VISITED]

    assert len(origin_rows) == 1, "Expected 1 ORIGIN location"
    assert origin_rows[0].name == "Megaton"
    assert len(visited_rows) == 2, "Expected 2 VISITED locations"
    visited_names = {r.name for r in visited_rows}
    assert "Rivet City" in visited_names
    assert "Goodneighbor" in visited_names

    # Assert DwellerLocation junction rows link the dweller
    links = (await async_session.execute(select(DwellerLocation))).scalars().all()
    origin_links = [lnk for lnk in links if lnk.relation == DwellerLocationRelationEnum.ORIGIN]
    visited_links = [lnk for lnk in links if lnk.relation == DwellerLocationRelationEnum.VISITED]

    assert len(origin_links) == 1, "Expected 1 ORIGIN DwellerLocation link"
    assert origin_links[0].dweller_id == dweller.id

    assert len(visited_links) == 2, "Expected 2 VISITED DwellerLocation links"
    for lnk in visited_links:
        assert lnk.dweller_id == dweller.id


# ---------------------------------------------------------------------------
# World-coordinate scaling (0-100 DB grid → 0-160 render world)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vault_map_scales_home_marker_to_world(async_session: AsyncSession, vault: Vault) -> None:
    """get_vault_map returns coords scaled by WORLD_SCALE: home (50,50) → (80,80)."""
    response = await map_service.get_vault_map(async_session, vault)

    home = next(loc for loc in response.locations if loc.type == LocationTypeEnum.HOME_VAULT)
    assert home.coord_x == 80.0
    assert home.coord_y == 80.0


@pytest.mark.asyncio
async def test_get_vault_map_scales_all_coords_into_world(async_session: AsyncSession, vault: Vault) -> None:
    """Every returned location and vault marker coord lands in the 0-160 world."""
    response = await map_service.get_vault_map(async_session, vault)

    for loc in response.locations:
        assert 0.0 <= loc.coord_x <= 160.0, loc.name
        assert 0.0 <= loc.coord_y <= 160.0, loc.name
    for marker in response.vault_markers:
        assert 0.0 <= marker.coord_x <= 160.0, marker.name
        assert 0.0 <= marker.coord_y <= 160.0, marker.name


# ---------------------------------------------------------------------------
# is_unlocked — includes unlock state in responses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vault_map_includes_is_unlocked_on_locations(async_session: AsyncSession, vault: Vault) -> None:
    """Every location in get_vault_map carries an is_unlocked field."""
    response = await map_service.get_vault_map(async_session, vault)

    for loc in response.locations:
        assert hasattr(loc, "is_unlocked")
        # By default nothing is unlocked
        assert loc.is_unlocked is False


@pytest.mark.asyncio
async def test_get_vault_map_includes_is_unlocked_on_dweller_refs(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """DwellerRef objects in the map response carry is_unlocked."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Megaton", visited_places=["Rivet City"])

    response = await map_service.get_vault_map(async_session, vault)

    megaton = next((loc for loc in response.locations if loc.name == "Megaton"), None)
    assert megaton is not None
    assert len(megaton.dwellers) == 1
    assert megaton.dwellers[0].is_unlocked is False


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
async def test_get_vault_map_unlocked_only_keeps_unlocked(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """unlocked_only=True keeps non-VAULT locations whose DwellerLocation is unlocked."""
    from app.crud.wasteland_location import wasteland_location as wl_crud
    from app.models.wasteland_location import DwellerLocation, LocationTypeEnum, WastelandLocation

    await map_service.register_bio_places(async_session, dweller, origin_place="Megaton", visited_places=["Rivet City"])
    await wl_crud.unlock_places_for_dweller(async_session, dweller_id=dweller.id)

    filtered = await map_service.get_vault_map(async_session, vault, unlocked_only=True)

    megaton = next((loc for loc in filtered.locations if loc.name == "Megaton"), None)
    assert megaton is not None, "Unlocked Megaton should appear when unlocked_only=True"
    assert megaton.is_unlocked is True

    rivet_city = next((loc for loc in filtered.locations if loc.name == "Rivet City"), None)
    assert rivet_city is not None, "Rivet City linked to same dweller should also appear (unlock affects ALL places)"


@pytest.mark.asyncio
async def test_get_location_detail_includes_is_unlocked(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_location_detail returns is_unlocked on location and dweller refs."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Megaton", visited_places=[])

    from app.models.wasteland_location import WastelandLocation

    loc_row = (
        await async_session.execute(
            select(WastelandLocation).where(
                WastelandLocation.vault_id == vault.id,
                WastelandLocation.name == "Megaton",
            )
        )
    ).scalar_one()

    detail = await map_service.get_location_detail(async_session, vault, loc_row.id)

    assert hasattr(detail, "is_unlocked")
    assert detail.is_unlocked is False
    assert len(detail.dwellers) == 1
    assert detail.dwellers[0].is_unlocked is False
