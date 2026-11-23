from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from faker import Faker
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ExpeditionRunStatus, LocationTypeEnum, NotificationType, PlaceKindEnum, RarityEnum
from app.core.game_config import game_config
from app.crud.vault_slot import vault_slot
from app.crud.world_location import world_location
from app.crud.world_location import world_location as wl_crud
from app.models.dweller import Dweller
from app.models.exploration import ExpeditionRun
from app.models.notification import Notification
from app.models.vault import Vault
from app.models.world_location import DwellerLocation, VaultLocationState, WorldLocation
from app.schemas.dweller import DwellerCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services import catalog_service as data_loader
from app.services.dweller_service import dweller_service
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service
from app.services.world_snapshot_service import world_snapshot_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.utils.places import WORLD_SCALE, normalize_place_name
from app.utils.time import utcnow

# Ready (not scenario-only) expedition sites and their room totals; both ready-map
# assertions compare the wire payload against this table.
_ONE_ROOM_SITES = [
    "abandoned_campsite",
    "roadside_supply_truck",
    "forgotten_shack",
    "collapsed_subway",
    "rusted_midway",
    "frozen_research_outpost",
    "raider_tollbooth",
    "gloomwater_bog",
    "gloomwater_bog_night",
    "outskirts_interchange",
]
_READY_SITES = {"red_rocket": 3, "super_duper_mart": 4, **dict.fromkeys(_ONE_ROOM_SITES, 1)}


async def _register(session: AsyncSession, dweller: Dweller, origin: str, visited=()) -> None:
    await map_service.register_bio_places(session, dweller, origin_place=origin, visited_places=list(visited))


async def _state_for(session, vault, name):
    return (
        await session.execute(
            select(VaultLocationState)
            .join(WorldLocation, WorldLocation.id == VaultLocationState.location_id)
            .where(VaultLocationState.vault_id == vault.id, WorldLocation.name == name)
        )
    ).scalar_one()


async def _find(session, vault, origin):
    map_data = await map_service.get_vault_map(session, vault)
    return next(loc for loc in map_data.locations if loc.normalized_name == origin.lower())


async def _location(session: AsyncSession, vault: Vault, dweller: Dweller, origin="Red Rocket", visited=()):
    await _register(session, dweller, origin, visited)
    return await _find(session, vault, origin)


async def _notifications(session, notification_type=None):
    stmt = select(Notification)
    if notification_type is not None:
        stmt = stmt.where(Notification.notification_type == notification_type)
    return (await session.execute(stmt)).scalars().all()


async def test_register_bio_places_rarity_scaled(async_session, vault, dweller):
    common_names = ["Megaton", "Rivet City", "Tenpenny Tower", "Paradise Falls", "Canterbury Commons", "Big Town"]
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
    await _register(async_session, dweller, "Arefu", common_names)
    dweller.rarity = RarityEnum.LEGENDARY
    await _register(async_session, dweller, "Arefu", legendary_names)

    rows = (await async_session.execute(select(VaultLocationState))).scalars().all()
    assert len([r for r in rows if r.type == LocationTypeEnum.ORIGIN]) == 1
    assert len([r for r in rows if r.type == LocationTypeEnum.VISITED]) == 2


@pytest.mark.parametrize(
    ("rarity", "origin", "visited", "visited_count"),
    [
        (RarityEnum.LEGENDARY, "Rivet City", ["National Archives", "Megaton", "Canterbury Commons"], 2),
        (RarityEnum.COMMON, "Megaton", ["Rivet City", "Tenpenny Tower", "Canterbury Commons"], 0),
        (RarityEnum.COMMON, "Megaton", ["the wasteland", "unknown"], 0),
    ],
)
async def test_bio_registration_is_capped_by_rarity_and_skips_wasteland(
    async_session, vault, dweller, rarity, origin, visited, visited_count
):
    dweller.rarity = rarity
    await _register(async_session, dweller, origin, visited)

    rows = (await async_session.execute(select(VaultLocationState))).scalars().all()
    assert len([r for r in rows if r.type == LocationTypeEnum.ORIGIN]) == 1
    assert len([r for r in rows if r.type == LocationTypeEnum.VISITED]) == visited_count


async def test_template_dweller_creation_registers_capped_places(async_session, vault):
    dweller = await dweller_service.create_dweller_from_template(async_session, vault.id, "abraham-washington")

    rows = (await async_session.execute(select(VaultLocationState))).scalars().all()
    assert dweller.bio.startswith("Curator of the Capitol Preservation Society")
    assert len([r for r in rows if r.type == LocationTypeEnum.VISITED]) == 2


async def test_register_discovery_forced_db_error_logged_not_raised(async_session, vault, dweller, caplog):
    with patch("app.crud.world_location.world_location.get_or_create_location", side_effect=SQLAlchemyError("forced")):
        # Must NOT raise
        await map_service.register_discovery(async_session, vault.id, uuid4(), dweller.id, "Crash Site")

    assert any("register_discovery failed" in record.message for record in caplog.records)


async def test_register_bio_places_handles_final_commit_failure(async_session, dweller):
    with patch.object(async_session, "commit", new=AsyncMock(side_effect=SQLAlchemyError("offline"))):
        assert await map_service.register_bio_places(async_session, dweller, "Arefu", []) is False


async def test_ensure_home_marker_upgrades_bio_registered_place_row(async_session, vault, dweller):
    # A bio mention of 'Vault NNN' must not strand the home marker off-grid.
    await _register(async_session, dweller, f"Vault {vault.number:03}")
    placed = await wl_crud.get_registry_by_normalized(async_session, normalize_place_name(f"Vault {vault.number:03}"))
    assert placed is not None
    assert placed.kind != PlaceKindEnum.VAULT

    home = await map_service.ensure_home_marker(async_session, vault)

    assert home.id == placed.id
    assert (home.kind, home.vault_number, home.coord_x, home.coord_y) == (PlaceKindEnum.VAULT, vault.number, 50.0, 50.0)
    states = (
        (await async_session.execute(select(VaultLocationState).where(VaultLocationState.vault_id == vault.id)))
        .scalars()
        .all()
    )
    assert any(s.type == LocationTypeEnum.HOME_VAULT and s.location_id == home.id for s in states)


async def test_register_bio_places_retries_a_transient_failure(async_session, vault, dweller):
    dweller.rarity = RarityEnum.LEGENDARY
    original_get_or_create = world_location.get_or_create_location
    attempts = 0

    async def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise SQLAlchemyError("transient")
        return await original_get_or_create(*args, **kwargs)

    with patch.object(world_location, "get_or_create_location", side_effect=fail_once):
        await _register(async_session, dweller, "Rusty Creek", ["Necropolis", "Brotherhood Outpost"])

    assert len((await async_session.execute(select(DwellerLocation))).scalars().all()) == 3


async def test_get_vault_map_unlocked_only_hides_locked_and_detail_flags_unlock(async_session, vault, dweller):
    dweller.rarity = RarityEnum.LEGENDARY
    await _register(async_session, dweller, "Megaton", ["Rivet City"])

    full = await map_service.get_vault_map(async_session, vault)
    filtered = await map_service.get_vault_map(async_session, vault, unlocked_only=True)

    assert len(full.locations) >= 3
    non_home = [loc for loc in filtered.locations if loc.type != LocationTypeEnum.HOME_VAULT]
    assert len(non_home) == 0, "No non-VAULT locations should appear when unlocked_only=True and nothing is unlocked"
    assert any(loc.type == LocationTypeEnum.HOME_VAULT for loc in filtered.locations)

    loc_row = await _state_for(async_session, vault, "Megaton")
    detail = await map_service.get_location_detail(async_session, vault, loc_row.location_id)

    assert hasattr(detail, "is_unlocked")
    assert detail.is_unlocked is False
    assert len(detail.dwellers) == 1
    assert detail.dwellers[0].is_unlocked is False


async def test_vault_map_hides_other_vault_dwellers(async_session, vault, dweller, dweller_data):
    fake = Faker()
    user = await crud.user.create(
        db_session=async_session,
        obj_in=UserCreate(username=fake.user_name(), email=fake.email(), password=fake.password()),
    )
    vault2 = await crud.vault.create(
        db_session=async_session,
        obj_in=VaultCreateWithUserID(
            number=999, bottle_caps=1000, happiness=50, power=10, food=10, water=10, population_max=50, user_id=user.id
        ),
    )
    dweller2 = await crud.dweller.create(
        db_session=async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault2.id)
    )

    await _register(async_session, dweller, "Megaton")
    await _register(async_session, dweller2, "Megaton")

    map_a = await map_service.get_vault_map(async_session, vault)
    assert map_a.expedition_sites == []
    megaton_a = next(loc for loc in map_a.locations if loc.normalized_name == "megaton")
    assert {ref.dweller_id for ref in megaton_a.dwellers} == {dweller.id}

    map_b = await map_service.get_vault_map(async_session, vault2)
    megaton_b = next(loc for loc in map_b.locations if loc.normalized_name == "megaton")
    assert {ref.dweller_id for ref in megaton_b.dwellers} == {dweller2.id}


async def test_get_or_create_location_conflict_keeps_outer_transaction(async_session):
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


async def test_red_rocket_clear_state_and_unlock_gate_actions(async_session, vault, dweller):
    # A clearable, never-cleared point exposes clear_state with zeroed counters.
    red_rocket = await _location(async_session, vault, dweller)
    state = red_rocket.clear_state
    assert state is not None
    assert (state.clearable, state.cleared, state.clear_count, state.tier) == (True, False, 0, 0)
    assert (state.time_remaining_seconds, state.loot_table, state.xp_per_survivor) == (0, "automotive", 20)
    assert state.loot_preview[0].signature is True
    assert state.loot_preview[0].junk_types == ["adhesive"]
    assert any(not entry.signature for entry in state.loot_preview)

    assert red_rocket.is_unlocked is False
    assert red_rocket.action == "none"

    detail_state = (await map_service.get_location_detail(async_session, vault, red_rocket.id)).clear_state
    assert detail_state is not None
    assert (
        detail_state.clearable,
        detail_state.cleared,
        detail_state.clear_count,
        detail_state.tier,
        detail_state.loot_table,
    ) == (True, False, 0, 0, "automotive")

    await async_session.execute(
        update(DwellerLocation).where(DwellerLocation.location_id == red_rocket.id).values(is_unlocked=True)
    )
    await async_session.commit()

    unlocked = await _find(async_session, vault, "Red Rocket")
    assert unlocked.is_unlocked is True
    assert unlocked.action == "clear"


async def test_get_vault_map_clear_state_cleared_pending_reclear(async_session, vault, dweller):
    await _register(async_session, dweller, "Red Rocket")
    row = await _state_for(async_session, vault, "Red Rocket")
    row.reclear_available_at = utcnow() + timedelta(hours=1)
    row.clear_count = 5
    await async_session.commit()

    state = (await _find(async_session, vault, "Red Rocket")).clear_state
    assert state is not None
    assert (state.cleared, state.clear_count) == (True, 5)
    assert state.tier == game_config.exploration.dispatch.escalation_cap
    assert state.time_remaining_seconds > 0
    assert state.xp_per_survivor == int(
        20 * (1 + game_config.exploration.dispatch.reward_per_tier * game_config.exploration.dispatch.escalation_cap)
    )


@pytest.mark.parametrize(
    ("origin", "emergent", "group_key", "clearable", "loot_table"),
    [
        ("Megaton", True, "settlement", None, None),
        ("Race Town", True, "wasteland_site", True, "low"),
        ("Race Town", False, None, None, None),
    ],
)
async def test_get_vault_map_clear_state_follows_the_group(
    async_session, vault, dweller, monkeypatch, origin, emergent, group_key, clearable, loot_table
):
    monkeypatch.setattr(game_config.features, "emergent_sites", emergent)
    location = await _location(async_session, vault, dweller, origin)

    if group_key is not None:
        assert location.group_key == group_key
    if clearable is None:
        assert location.clear_state is None
    else:
        assert location.clear_state.clearable is clearable
        assert location.clear_state.loot_table == loot_table


async def test_location_detail_prefers_canonical_description_then_group_lore(async_session, vault, dweller):
    await _register(async_session, dweller, "Red Rocket")
    location = (
        await async_session.execute(select(WorldLocation).where(WorldLocation.name == "Red Rocket"))
    ).scalar_one()

    detail = await map_service.get_location_detail(async_session, vault, location.id)
    assert detail.description is not None
    assert "roadside fuel stop" in detail.description

    location.description = "Canonical lore"
    state = await _state_for(async_session, vault, "Red Rocket")
    state.description = "Per-vault lore"
    async_session.add_all([location, state])
    await async_session.commit()

    detail = await map_service.get_location_detail(async_session, vault, location.id)
    assert detail.description == "Canonical lore"


async def _elapsed_red_rocket(async_session, vault, dweller):
    await _register(async_session, dweller, "Red Rocket")
    state = await _state_for(async_session, vault, "Red Rocket")
    state.reclear_available_at = utcnow() - timedelta(hours=1)
    await async_session.commit()
    return state


async def test_sweep_reclears_only_elapsed_rows_and_notifies_once(async_session, vault, dweller):
    await _register(async_session, dweller, "Red Rocket")
    state = await _state_for(async_session, vault, "Red Rocket")
    state.reclear_available_at = utcnow() + timedelta(hours=1)
    await async_session.commit()

    assert await map_service.sweep_reclears(async_session) == 0
    await async_session.refresh(state)
    assert state.reclear_available_at is not None
    assert await _notifications(async_session) == []

    state.reclear_available_at = utcnow() - timedelta(hours=1)
    await async_session.commit()

    assert await map_service.sweep_reclears(async_session) == 1

    await async_session.refresh(state)
    assert state.reclear_available_at is None
    notifications = await _notifications(async_session, NotificationType.LOCATION_READY)
    assert len(notifications) == 1
    assert (notifications[0].user_id, notifications[0].vault_id) == (vault.user_id, vault.id)
    assert "Red Rocket" in notifications[0].title
    assert notifications[0].meta_data == {"location_id": str(state.location_id), "location_name": "Red Rocket"}

    assert await map_service.sweep_reclears(async_session) == 0
    assert len(await _notifications(async_session, NotificationType.LOCATION_READY)) == 1

    # A missing vault owner still clears the row, without a fresh notification.
    state.reclear_available_at = utcnow() - timedelta(hours=1)
    await async_session.commit()
    with patch("app.services.map.discovery.vault_crud.get_or_none", new=AsyncMock(return_value=None)):
        assert await map_service.sweep_reclears(async_session) == 1
    await async_session.refresh(state)
    assert state.reclear_available_at is None
    assert len(await _notifications(async_session, NotificationType.LOCATION_READY)) == 1


_EXPECTED_SITE_IDS = {"red_rocket", "super_duper_mart", *_ONE_ROOM_SITES}


async def _legacy_journey(session, vault):
    """An in-progress legacy (non-spatial) journey, so the catalog fallback applies."""
    dweller = await crud.dweller.create(
        session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=str(vault.id))
    )
    await exploration_service.send_dweller(session, vault.id, dweller.id, duration=4)


async def _spatial_journey(session, vault, dweller, pos):
    """An in-progress spatial run whose trail includes `pos`."""
    if await vault_slot.get_by_vault(session, vault.id) is None:
        await vault_slot.claim_next(db_session=session, vault_id=vault.id)
        await session.commit()
    await world_snapshot_service.get_or_generate(session)
    dweller.level, dweller.health, dweller.max_health = 10, 100, 100
    session.add(dweller)
    await session.commit()
    exploration = await exploration_service.send_dweller(session, vault.id, dweller.id, duration=24, heading_degrees=90)
    exploration.pos_x, exploration.pos_y = pos
    exploration.trail = [*exploration.trail, {"x": pos[0], "y": pos[1], "t": utcnow().isoformat()}]
    session.add(exploration)
    await session.commit()
    await session.refresh(exploration)
    return exploration


async def test_expedition_sites_ready_catalog(async_session, vault):
    await _legacy_journey(async_session, vault)
    sites = {site.id: site for site in (await map_service.get_vault_map(async_session, vault)).expedition_sites}

    assert set(sites) == _EXPECTED_SITE_IDS
    for site in data_loader.load_expedition_sites():
        if site.scenario_only:
            continue
        marker = sites[site.id]
        assert (marker.block_reason, marker.cleared, marker.cooldown_remaining_seconds) == (None, False, 0)
        assert (marker.coord_x, marker.coord_y, marker.min_dweller_level) == (
            round(site.coord_x * WORLD_SCALE, 1),
            round(site.coord_y * WORLD_SCALE, 1),
            site.min_dweller_level,
        )
    assert {site_id: marker.room_total for site_id, marker in sites.items()} == {
        "red_rocket": 3,
        "super_duper_mart": 4,
        **dict.fromkeys(_ONE_ROOM_SITES, 1),
    }


@pytest.mark.parametrize(
    ("status", "block", "cleared"),
    [
        (ExpeditionRunStatus.IN_ROOM, "open", False),
        (ExpeditionRunStatus.CLEARED, "cooldown", True),
        (ExpeditionRunStatus.RETREATED, "cooldown", False),
        (ExpeditionRunStatus.DIED, "cooldown", False),
    ],
)
async def test_expedition_sites_block_states(async_session, vault, status, block, cleared):
    await _legacy_journey(async_session, vault)
    finished_at = None if status == ExpeditionRunStatus.IN_ROOM else utcnow() - timedelta(days=1)
    async_session.add(
        ExpeditionRun(
            exploration_id=uuid4(), vault_id=vault.id, site_id="red_rocket", status=status, finished_at=finished_at
        )
    )
    await async_session.commit()

    sites = {site.id: site for site in (await map_service.get_vault_map(async_session, vault)).expedition_sites}
    rocket = sites["red_rocket"]
    assert (rocket.block_reason, rocket.cleared) == (block, cleared)
    assert (rocket.cooldown_remaining_seconds > 0) is (block == "cooldown")
    assert (sites["super_duper_mart"].block_reason, sites["super_duper_mart"].cleared) == (None, False)


async def test_spatial_journey_exposes_only_offered_sites(async_session, vault, dweller):
    exploration = await _spatial_journey(async_session, vault, dweller, (30.0, 25.0))
    sites = (await map_service.get_vault_map(async_session, vault)).expedition_sites
    assert {site.id for site in sites} == {"red_rocket", "roadside_supply_truck"}
    assert {site.id: site.room_total for site in sites} == {"red_rocket": 1, "roadside_supply_truck": 1}

    run = await crud.expedition_run.create_run(
        async_session, exploration_id=exploration.id, vault_id=vault.id, site_id="red_rocket"
    )
    run.status = ExpeditionRunStatus.CLEARED
    run.finished_at = utcnow()
    async_session.add(run)
    await async_session.commit()

    sites = (await map_service.get_vault_map(async_session, vault)).expedition_sites
    assert {site.id for site in sites} == {"roadside_supply_truck"}


async def test_expedition_site_offers_union_across_journeys(async_session, vault, dweller):
    await _spatial_journey(async_session, vault, dweller, (30.0, 25.0))
    other = await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=str(vault.id))
    )
    other.level, other.health, other.max_health = 10, 100, 100
    async_session.add(other)
    await async_session.commit()
    second = await exploration_service.send_dweller(async_session, vault.id, other.id, duration=24, heading_degrees=90)
    second.pos_x, second.pos_y = 72.0, 68.0
    second.trail = [*second.trail, {"x": 72.0, "y": 68.0, "t": utcnow().isoformat()}]
    async_session.add(second)
    await async_session.commit()

    by_id = {site.id: site for site in (await map_service.get_vault_map(async_session, vault)).expedition_sites}
    assert {"red_rocket", "super_duper_mart"} <= set(by_id)
    assert by_id["red_rocket"].exploration_id is not None
    assert by_id["red_rocket"].exploration_id != by_id["super_duper_mart"].exploration_id
