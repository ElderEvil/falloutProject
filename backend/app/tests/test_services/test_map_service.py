"""Tests for MapService — registration and map assembly."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ExpeditionRunStatus, LocationTypeEnum, PlaceKindEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.notification import Notification, NotificationType
from app.models.vault import Vault
from app.models.world_location import DwellerLocation, VaultLocationState, WorldLocation
from app.schemas.common import RarityEnum
from app.services.map_service import map_service
from app.utils.places import WORLD_SCALE, normalize_place_name

# ---------------------------------------------------------------------------
# register_bio_places
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_bio_places_rarity_scaled(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """VISITED cap follows rarity: COMMON→0, LEGENDARY→2 for 6 provided names each."""
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
    assert len(visited_rows) == 2


@pytest.mark.asyncio
async def test_register_bio_places_caps_curated_templates_at_rarity(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Curated places obey the same rarity cap: a legendary registers 2, not all 4."""
    dweller.rarity = RarityEnum.LEGENDARY
    await map_service.register_bio_places(
        async_session,
        dweller,
        origin_place="Rivet City",
        visited_places=["National Archives", "Megaton", "Canterbury Commons", "Tenpenny Tower"],
    )

    rows = (await async_session.execute(select(VaultLocationState))).scalars().all()
    visited_rows = [r for r in rows if r.type == LocationTypeEnum.VISITED]
    assert len(visited_rows) == 2


@pytest.mark.asyncio
async def test_common_bio_registers_origin_only(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """A common dweller keeps its origin but registers no traveled history."""
    dweller.rarity = RarityEnum.COMMON
    await map_service.register_bio_places(
        async_session,
        dweller,
        origin_place="Megaton",
        visited_places=["Rivet City", "Tenpenny Tower", "Canterbury Commons"],
    )

    rows = (await async_session.execute(select(VaultLocationState))).scalars().all()
    origin_rows = [r for r in rows if r.type == LocationTypeEnum.ORIGIN]
    visited_rows = [r for r in rows if r.type == LocationTypeEnum.VISITED]
    assert len(origin_rows) == 1
    assert len(visited_rows) == 0


@pytest.mark.asyncio
async def test_template_dweller_creation_registers_capped_places(async_session: AsyncSession, vault: Vault) -> None:
    """Abraham Washington's 4 curated visits register capped to the legendary limit of 2."""
    from app.services.dweller_service import dweller_service

    dweller = await dweller_service.create_dweller_from_template(async_session, vault.id, "abraham-washington")

    rows = (await async_session.execute(select(VaultLocationState))).scalars().all()
    visited_rows = [r for r in rows if r.type == LocationTypeEnum.VISITED]
    assert dweller.bio.startswith("Curator of the Capitol Preservation Society")
    assert len(visited_rows) == 2


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


@pytest.mark.asyncio
async def test_ensure_home_marker_upgrades_bio_registered_place_row(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A bio mention of 'Vault NNN' must not strand the home marker off-grid."""
    from app.crud.world_location import world_location as wl_crud

    await map_service.register_bio_places(
        async_session, dweller, origin_place=f"Vault {vault.number:03}", visited_places=[]
    )
    placed = await wl_crud.get_registry_by_normalized(async_session, normalize_place_name(f"Vault {vault.number:03}"))
    assert placed is not None
    assert placed.kind != PlaceKindEnum.VAULT

    home = await map_service.ensure_home_marker(async_session, vault)

    assert home.id == placed.id
    assert home.kind == PlaceKindEnum.VAULT
    assert home.vault_number == vault.number
    assert (home.coord_x, home.coord_y) == (50.0, 50.0)
    states = (
        (await async_session.execute(select(VaultLocationState).where(VaultLocationState.vault_id == vault.id)))
        .scalars()
        .all()
    )
    assert any(s.type == LocationTypeEnum.HOME_VAULT and s.location_id == home.id for s in states)


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
    dweller.rarity = RarityEnum.LEGENDARY
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


@pytest.mark.asyncio
async def test_vault_map_hides_other_vault_dwellers(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, dweller_data: dict
) -> None:
    """Two vaults sharing a place name see only their own dwellers."""
    from faker import Faker

    from app import crud
    from app.schemas.dweller import DwellerCreate
    from app.schemas.user import UserCreate
    from app.schemas.vault import VaultCreateWithUserID

    fake = Faker()
    user = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password()),
    )
    vault2 = await crud.vault.create(
        db_session=async_session,
        obj_in=VaultCreateWithUserID(
            number=999,
            bottle_caps=1000,
            happiness=50,
            power=10,
            food=10,
            water=10,
            population_max=50,
            user_id=user.id,
        ),
    )
    dweller2 = await crud.dweller.create(
        db_session=async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault2.id)
    )

    await map_service.register_bio_places(async_session, dweller, origin_place="Megaton", visited_places=[])
    await map_service.register_bio_places(async_session, dweller2, origin_place="Megaton", visited_places=[])

    map_a = await map_service.get_vault_map(async_session, vault)
    megaton_a = next(loc for loc in map_a.locations if loc.normalized_name == "megaton")
    assert {ref.dweller_id for ref in megaton_a.dwellers} == {dweller.id}

    map_b = await map_service.get_vault_map(async_session, vault2)
    megaton_b = next(loc for loc in map_b.locations if loc.normalized_name == "megaton")
    assert {ref.dweller_id for ref in megaton_b.dwellers} == {dweller2.id}


@pytest.mark.asyncio
async def test_get_or_create_location_conflict_keeps_outer_transaction(async_session: AsyncSession) -> None:
    """A flush conflict returns the existing row without killing outer work."""
    from app.crud.world_location import world_location

    existing = await world_location.get_or_create_location(async_session, "Race Town")
    await async_session.commit()

    outer = await world_location.get_or_create_location(async_session, "Outer Town", commit=False)
    with patch.object(world_location, "get_registry_by_normalized", side_effect=[None, existing]):
        recovered = await world_location.get_or_create_location(async_session, "Race Town", commit=False)
    assert recovered.id == existing.id
    await async_session.commit()
    persisted = await world_location.get_registry_by_normalized(async_session, "outer town")
    assert persisted is not None
    assert persisted.id == outer.id


# ---------------------------------------------------------------------------
# clear_state — per-point clear state on the map wire (issue 772, phase 1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_vault_map_clear_state_never_cleared(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A clearable, never-cleared point exposes clear_state with zeroed counters."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Red Rocket", visited_places=[])

    map_data = await map_service.get_vault_map(async_session, vault)
    red_rocket = next(loc for loc in map_data.locations if loc.normalized_name == "red rocket")

    assert red_rocket.clear_state is not None
    assert red_rocket.clear_state.clearable is True
    assert red_rocket.clear_state.cleared is False
    assert red_rocket.clear_state.clear_count == 0
    assert red_rocket.clear_state.tier == 0
    assert red_rocket.clear_state.time_remaining_seconds == 0
    assert red_rocket.clear_state.loot_table == "low"


@pytest.mark.asyncio
async def test_get_vault_map_clear_state_cleared_pending_reclear(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A cleared point with a future reclear window reports cleared + tier capped."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Red Rocket", visited_places=[])

    state = (
        await async_session.execute(
            select(VaultLocationState)
            .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
            .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == "Red Rocket")
        )
    ).scalar_one()
    state.reclear_available_at = datetime.utcnow() + timedelta(hours=1)
    state.clear_count = 5
    await async_session.commit()

    map_data = await map_service.get_vault_map(async_session, vault)
    red_rocket = next(loc for loc in map_data.locations if loc.normalized_name == "red rocket")

    assert red_rocket.clear_state is not None
    assert red_rocket.clear_state.cleared is True
    assert red_rocket.clear_state.clear_count == 5
    assert red_rocket.clear_state.tier == game_config.exploration.dispatch.escalation_cap
    assert red_rocket.clear_state.time_remaining_seconds > 0


@pytest.mark.asyncio
async def test_get_vault_map_clear_state_none_for_non_clearable_group(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Non-clearable groups (settlement) carry no clear_state."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Megaton", visited_places=[])

    map_data = await map_service.get_vault_map(async_session, vault)
    megaton = next(loc for loc in map_data.locations if loc.normalized_name == "megaton")

    assert megaton.group_key == "settlement"
    assert megaton.clear_state is None


@pytest.mark.asyncio
async def test_get_vault_map_clear_state_for_ungrouped_place(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """An ungrouped emergent PLACE falls back to the default clearable archetype."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Race Town", visited_places=[])

    map_data = await map_service.get_vault_map(async_session, vault)
    race_town = next(loc for loc in map_data.locations if loc.normalized_name == "race town")

    assert race_town.group_key is None
    assert race_town.clear_state is not None
    assert race_town.clear_state.clearable is True
    assert race_town.clear_state.loot_table == "low"


@pytest.mark.asyncio
async def test_get_vault_map_clear_state_none_when_emergent_sites_disabled(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the flag off, an ungrouped PLACE carries no clear_state."""
    monkeypatch.setattr(game_config.features, "emergent_sites", False)
    await map_service.register_bio_places(async_session, dweller, origin_place="Race Town", visited_places=[])

    map_data = await map_service.get_vault_map(async_session, vault)
    race_town = next(loc for loc in map_data.locations if loc.normalized_name == "race town")

    assert race_town.clear_state is None


@pytest.mark.asyncio
async def test_get_location_detail_includes_clear_state(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """get_location_detail exposes clear_state for clearable points too."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Red Rocket", visited_places=[])

    state = (
        await async_session.execute(
            select(VaultLocationState)
            .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
            .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == "Red Rocket")
        )
    ).scalar_one()

    detail = await map_service.get_location_detail(async_session, vault, state.location_id)

    assert detail.clear_state is not None
    assert detail.clear_state.clearable is True
    assert detail.clear_state.cleared is False
    assert detail.clear_state.clear_count == 0
    assert detail.clear_state.tier == 0
    assert detail.clear_state.loot_table == "low"


@pytest.mark.asyncio
async def test_location_detail_prefers_canonical_description(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A canonical registry description wins over the per-vault description."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Red Rocket", visited_places=[])
    location = (
        await async_session.execute(select(WorldLocation).where(WorldLocation.name == "Red Rocket"))
    ).scalar_one()
    location.description = "Canonical lore"
    state = (
        await async_session.execute(
            select(VaultLocationState).where(
                VaultLocationState.vault_id == vault.id,
                VaultLocationState.location_id == location.id,
            )
        )
    ).scalar_one()
    state.description = "Per-vault lore"
    async_session.add(location)
    async_session.add(state)
    await async_session.commit()

    detail = await map_service.get_location_detail(async_session, vault, location.id)

    assert detail.description == "Canonical lore"


@pytest.mark.asyncio
async def test_location_detail_falls_back_to_group_lore(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A place with no description shows its archetype's shared lore."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Red Rocket", visited_places=[])
    location = (
        await async_session.execute(select(WorldLocation).where(WorldLocation.name == "Red Rocket"))
    ).scalar_one()

    detail = await map_service.get_location_detail(async_session, vault, location.id)

    assert detail.description is not None
    assert "roadside fuel stop" in detail.description


# ---------------------------------------------------------------------------
# sweep_reclears — reclear reset sweep (issue 772, phase 4a)
# ---------------------------------------------------------------------------


async def _red_rocket_state(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> VaultLocationState:
    """Register Red Rocket and return its vault state."""
    await map_service.register_bio_places(async_session, dweller, origin_place="Red Rocket", visited_places=[])
    return (
        await async_session.execute(
            select(VaultLocationState)
            .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
            .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == "Red Rocket")
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_sweep_reclears_nulls_elapsed_and_notifies_once(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """An elapsed reclear is nulled and emits exactly one LOCATION_READY; a second sweep is a no-op."""
    state = await _red_rocket_state(async_session, vault, dweller)
    state.reclear_available_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    assert await map_service.sweep_reclears(async_session) == 1

    await async_session.refresh(state)
    assert state.reclear_available_at is None
    notifications = (
        (
            await async_session.execute(
                select(Notification).where(Notification.notification_type == NotificationType.LOCATION_READY)
            )
        )
        .scalars()
        .all()
    )
    assert len(notifications) == 1
    assert notifications[0].user_id == vault.user_id
    assert notifications[0].vault_id == vault.id
    assert "Red Rocket" in notifications[0].title
    assert notifications[0].meta_data == {
        "location_id": str(state.location_id),
        "location_name": "Red Rocket",
    }

    assert await map_service.sweep_reclears(async_session) == 0
    notifications = (
        (
            await async_session.execute(
                select(Notification).where(Notification.notification_type == NotificationType.LOCATION_READY)
            )
        )
        .scalars()
        .all()
    )
    assert len(notifications) == 1


@pytest.mark.asyncio
async def test_sweep_reclears_skips_not_yet_elapsed(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A reclear window still in the future is untouched: neither nulled nor notified."""
    state = await _red_rocket_state(async_session, vault, dweller)
    state.reclear_available_at = datetime.utcnow() + timedelta(hours=1)
    await async_session.commit()

    assert await map_service.sweep_reclears(async_session) == 0

    await async_session.refresh(state)
    assert state.reclear_available_at is not None
    notifications = (await async_session.execute(select(Notification))).scalars().all()
    assert notifications == []


@pytest.mark.asyncio
async def test_sweep_reclears_skips_missing_vault_owner(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A vault whose owner row is missing is skipped without aborting the sweep."""
    state = await _red_rocket_state(async_session, vault, dweller)
    state.reclear_available_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    with patch("app.services.map_service.vault_crud.get_or_none", new=AsyncMock(return_value=None)):
        assert await map_service.sweep_reclears(async_session) == 1

    await async_session.refresh(state)
    assert state.reclear_available_at is None
    notifications = (await async_session.execute(select(Notification))).scalars().all()
    assert notifications == []


# ---------------------------------------------------------------------------
# expedition_sites — interactive site markers on the map wire
# ---------------------------------------------------------------------------


async def _legacy_journey(async_session: AsyncSession, vault: Vault) -> None:
    """An in-progress legacy (non-spatial) journey, so the catalog fallback applies."""
    from app import crud
    from app.schemas.dweller import DwellerCreate
    from app.services.exploration_service import exploration_service
    from app.tests.factory.dwellers import create_fake_adult_dweller

    dweller = await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=str(vault.id))
    )
    await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)


@pytest.mark.asyncio
async def test_get_vault_map_expedition_sites_ready(async_session: AsyncSession, vault: Vault) -> None:
    """No runs yet: every site is ready with zeroed cooldown and scaled coords."""
    from app.services.exploration import data_loader

    await _legacy_journey(async_session, vault)
    map_data = await map_service.get_vault_map(async_session, vault)
    by_id = {site.id: site for site in map_data.expedition_sites}
    assert set(by_id) == {"red_rocket", "super_duper_mart"}
    for site in data_loader.load_expedition_sites():
        marker = by_id[site.id]
        assert marker.block_reason is None
        assert marker.cleared is False
        assert marker.cooldown_remaining_seconds == 0
        assert marker.coord_x == round(site.coord_x * WORLD_SCALE, 1)
        assert marker.coord_y == round(site.coord_y * WORLD_SCALE, 1)
        assert marker.min_dweller_level == site.min_dweller_level
        assert marker.room_total == len(site.rooms)


@pytest.mark.asyncio
async def test_get_vault_map_expedition_sites_open(async_session: AsyncSession, vault: Vault) -> None:
    """An open run for a vault+site marks that site as blocked by 'open'."""
    from app.models.exploration import ExpeditionRun, ExpeditionRunStatus

    await _legacy_journey(async_session, vault)
    async_session.add(
        ExpeditionRun(
            exploration_id=uuid4(),
            vault_id=vault.id,
            site_id="red_rocket",
            status=ExpeditionRunStatus.IN_ROOM,
        )
    )
    await async_session.commit()

    map_data = await map_service.get_vault_map(async_session, vault)
    by_id = {site.id: site for site in map_data.expedition_sites}
    assert by_id["red_rocket"].block_reason == "open"
    assert by_id["red_rocket"].cleared is False
    assert by_id["red_rocket"].cooldown_remaining_seconds == 0
    assert by_id["super_duper_mart"].block_reason is None


@pytest.mark.asyncio
async def test_get_vault_map_expedition_sites_cooldown(async_session: AsyncSession, vault: Vault) -> None:
    """A recent terminal run puts the site in cooldown with remaining seconds."""
    from app.models.exploration import ExpeditionRun, ExpeditionRunStatus

    await _legacy_journey(async_session, vault)
    async_session.add(
        ExpeditionRun(
            exploration_id=uuid4(),
            vault_id=vault.id,
            site_id="red_rocket",
            status=ExpeditionRunStatus.CLEARED,
            finished_at=datetime.utcnow() - timedelta(days=1),
        )
    )
    await async_session.commit()

    map_data = await map_service.get_vault_map(async_session, vault)
    by_id = {site.id: site for site in map_data.expedition_sites}
    assert by_id["red_rocket"].block_reason == "cooldown"
    assert by_id["red_rocket"].cleared is True
    assert by_id["red_rocket"].cooldown_remaining_seconds > 0
    assert by_id["super_duper_mart"].block_reason is None
    assert by_id["super_duper_mart"].cleared is False


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [ExpeditionRunStatus.RETREATED, ExpeditionRunStatus.DIED])
async def test_get_vault_map_expedition_sites_cooldown_not_cleared(
    async_session: AsyncSession, vault: Vault, status: ExpeditionRunStatus
) -> None:
    """A retreat/death within the anti-farm window blocks re-entry but is NOT 'cleared'."""
    from app.models.exploration import ExpeditionRun

    await _legacy_journey(async_session, vault)
    async_session.add(
        ExpeditionRun(
            exploration_id=uuid4(),
            vault_id=vault.id,
            site_id="red_rocket",
            status=status,
            finished_at=datetime.utcnow() - timedelta(days=1),
        )
    )
    await async_session.commit()

    map_data = await map_service.get_vault_map(async_session, vault)
    by_id = {site.id: site for site in map_data.expedition_sites}
    assert by_id["red_rocket"].block_reason == "cooldown"
    assert by_id["red_rocket"].cleared is False
    assert by_id["red_rocket"].cooldown_remaining_seconds > 0
    assert by_id["super_duper_mart"].block_reason is None
    assert by_id["super_duper_mart"].cleared is False


async def _spatial_journey_near_red_rocket(async_session: AsyncSession, vault: Vault, dweller: Dweller):
    """An in-progress spatial run whose trail passes red_rocket (30, 25)."""
    from app.crud.vault_slot import vault_slot
    from app.services.exploration_service import exploration_service
    from app.services.world_snapshot_service import world_snapshot_service

    slot = await vault_slot.get_by_vault(async_session, vault.id)
    if slot is None:
        await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
        await async_session.commit()
    await world_snapshot_service.get_or_generate(async_session)
    dweller.level = 10
    dweller.health = 100
    dweller.max_health = 100
    async_session.add(dweller)
    await async_session.commit()
    exploration = await exploration_service.send_dweller(
        async_session, vault.id, dweller.id, duration=24, heading_degrees=90
    )
    exploration.pos_x, exploration.pos_y = 30.0, 25.0
    exploration.trail = [*exploration.trail, {"x": 30.0, "y": 25.0, "t": datetime.utcnow().isoformat()}]
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    return exploration


@pytest.mark.asyncio
async def test_get_vault_map_spatial_journey_exposes_only_offered_sites(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A spatial journey shows only trail-offered sites; consumption removes one."""
    from app import crud

    exploration = await _spatial_journey_near_red_rocket(async_session, vault, dweller)

    map_data = await map_service.get_vault_map(async_session, vault)
    assert {site.id for site in map_data.expedition_sites} == {"red_rocket"}

    run = await crud.expedition_run.create_run(
        async_session, exploration_id=exploration.id, vault_id=vault.id, site_id="red_rocket"
    )
    run.status = ExpeditionRunStatus.CLEARED
    run.finished_at = datetime.utcnow()
    async_session.add(run)
    await async_session.commit()

    map_data = await map_service.get_vault_map(async_session, vault)
    assert map_data.expedition_sites == []


@pytest.mark.asyncio
async def test_get_vault_map_no_journey_has_no_site_markers(async_session: AsyncSession, vault: Vault) -> None:
    """Without an in-progress journey, the temporary encounter markers are absent."""
    map_data = await map_service.get_vault_map(async_session, vault)

    assert map_data.expedition_sites == []


@pytest.mark.asyncio
async def test_get_vault_map_unions_offers_across_journeys(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Every in-progress spatial journey contributes its own discovered encounters."""
    from app import crud
    from app.schemas.dweller import DwellerCreate
    from app.services.exploration_service import exploration_service
    from app.services.world_snapshot_service import world_snapshot_service
    from app.tests.factory.dwellers import create_fake_adult_dweller

    await _spatial_journey_near_red_rocket(async_session, vault, dweller)

    other = await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=str(vault.id))
    )
    other.level = 10
    other.health = 100
    other.max_health = 100
    async_session.add(other)
    await async_session.commit()
    await world_snapshot_service.get_or_generate(async_session)
    second = await exploration_service.send_dweller(async_session, vault.id, other.id, duration=24, heading_degrees=90)
    second.pos_x, second.pos_y = 72.0, 68.0
    second.trail = [*second.trail, {"x": 72.0, "y": 68.0, "t": datetime.utcnow().isoformat()}]
    async_session.add(second)
    await async_session.commit()

    map_data = await map_service.get_vault_map(async_session, vault)
    by_id = {site.id: site for site in map_data.expedition_sites}

    assert {"red_rocket", "super_duper_mart"} <= set(by_id)
    assert by_id["red_rocket"].exploration_id is not None
    assert by_id["red_rocket"].exploration_id != by_id["super_duper_mart"].exploration_id
