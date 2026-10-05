"""One-time journey encounters (slice 3b): consumption, travel-clock pause, deferred arrival."""

import math
from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.exploration import ExpeditionRunStatus, ExplorationStatus
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.exploration import data_loader
from app.services.exploration import expedition as expedition_module
from app.services.exploration_service import exploration_service
from app.services.game_tick.dwellers_tick import process_explorations
from app.services.world_snapshot_service import world_snapshot_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.utils.exceptions import ResourceConflictException, ValidationException

SITE_ID = "red_rocket"


async def _spatial_run(async_session: AsyncSession, vault: Vault, dweller: Dweller, *, heading: float = 90):
    from app.crud.vault_slot import vault_slot

    slot = await vault_slot.get_by_vault(async_session, vault.id)
    if slot is None:
        slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
        await async_session.commit()
    await world_snapshot_service.get_or_generate(async_session)
    dweller.level = 10
    dweller.health = 100
    dweller.max_health = 100
    async_session.add(dweller)
    await async_session.commit()
    return await exploration_service.send_dweller(
        async_session, vault.id, dweller.id, duration=24, heading_degrees=heading
    )


async def _spatial_run_at_site(async_session: AsyncSession, vault: Vault, dweller: Dweller, site_id: str = SITE_ID):
    """A spatial run staged with its trail passing the site (travel covered by movement tests)."""
    exploration = await _spatial_run(async_session, vault, dweller)
    site = next(site for site in data_loader.load_expedition_sites() if site.id == site_id)
    near = (site.coord_x - 2.0, site.coord_y)
    exploration.pos_x, exploration.pos_y = near
    exploration.trail = [*exploration.trail, {"x": near[0], "y": near[1], "t": datetime.utcnow().isoformat()}]
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    return exploration


@pytest.mark.asyncio
async def test_retreat_allows_reentry_and_resumes_progress(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Retreat does not consume: re-entry resumes the saved room cursor, and the site stays offered."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    assert run is not None
    run.room_cursor = 1
    async_session.add(run)
    await async_session.commit()

    await expedition_module.expedition_service.retreat_run(async_session, exploration.id)

    available = await expedition_module.expedition_service.list_available_sites(async_session, exploration.id)
    assert SITE_ID in [site.id for site in available]

    view = await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    assert view.room_index == 1


@pytest.mark.asyncio
async def test_cleared_site_rejects_reentry_in_same_journey(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Only completion consumes the encounter: a CLEARED run refuses re-entry as spent."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    run = await crud.expedition_run.create_run(
        async_session,
        exploration_id=exploration.id,
        vault_id=vault.id,
        site_id=SITE_ID,
    )
    run.status = ExpeditionRunStatus.CLEARED
    run.finished_at = datetime.utcnow()
    async_session.add(run)
    await async_session.commit()

    with pytest.raises(ResourceConflictException, match="spent for this journey"):
        await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)

    available = await expedition_module.expedition_service.list_available_sites(async_session, exploration.id)
    assert SITE_ID not in [site.id for site in available]


@pytest.mark.asyncio
async def test_open_encounter_freezes_position_but_burns_clock(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """While inside, advance() holds position and consumes the interval."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    before = (exploration.pos_x, exploration.pos_y)
    trail_len = len(exploration.trail)
    now = exploration.start_time + timedelta(hours=2)

    advanced = await exploration_service.advance(async_session, exploration.id, now=now)

    assert (advanced.pos_x, advanced.pos_y) == before
    assert advanced.position_as_of == now
    assert len(advanced.trail) == trail_len


@pytest.mark.asyncio
async def test_tick_defers_finalize_while_encounter_open(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A returning run with an expired timer stays unfinalized while the dweller is inside."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    exploration.status = ExplorationStatus.RETURNING
    exploration.return_started_at = datetime.utcnow() - timedelta(hours=2)
    exploration.return_completes_at = datetime.utcnow() - timedelta(minutes=1)
    async_session.add(exploration)
    await async_session.commit()

    stats = await process_explorations(async_session, vault.id)

    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.RETURNING
    assert stats.get("completed", 0) == 0


@pytest.mark.asyncio
async def _extend_trail_near_site(async_session, exploration, site_id: str = SITE_ID):
    """Append a near-site breadcrumb without moving (travel covered by movement tests)."""
    site = next(site for site in data_loader.load_expedition_sites() if site.id == site_id)
    near = (site.coord_x - 2.0, site.coord_y)
    exploration.trail = [*exploration.trail, {"x": near[0], "y": near[1], "t": datetime.utcnow().isoformat()}]
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    return exploration


@pytest.mark.asyncio
async def test_pause_resume_discounts_paused_interval(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Settled boundaries: a 2h pause with no inside tick never converts to movement."""
    exploration = await _spatial_run(async_session, vault, dweller)
    speed = 1 / game_config.exploration.dispatch.travel_hours_per_unit
    t0 = exploration.start_time
    await exploration_service.advance(async_session, exploration.id, now=t0 + timedelta(hours=1))
    await async_session.refresh(exploration)
    pos_after_1h = (exploration.pos_x, exploration.pos_y)

    await exploration_service.pause_for_encounter(async_session, exploration, now=t0 + timedelta(hours=1))
    await async_session.commit()
    # A 2h pause with no tick inside: advance only burns the clock.
    await exploration_service.advance(async_session, exploration.id, now=t0 + timedelta(hours=3))
    await async_session.refresh(exploration)
    exploration_service.resume_from_encounter(exploration, now=t0 + timedelta(hours=3))
    await async_session.commit()
    await exploration_service.advance(async_session, exploration.id, now=t0 + timedelta(hours=4))

    await async_session.refresh(exploration)
    heading = math.radians(exploration.heading_degrees)
    expected = (
        pos_after_1h[0] + math.sin(heading) * speed * 1,
        pos_after_1h[1] - math.cos(heading) * speed * 1,
    )
    assert exploration.pos_x == pytest.approx(expected[0], abs=0.05)
    assert exploration.pos_y == pytest.approx(expected[1], abs=0.05)
    assert exploration.paused_at is None


@pytest.mark.asyncio
async def test_enter_retreat_without_tick_does_not_move(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Enter + immediate retreat with no inside tick leaves the position untouched."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    await async_session.refresh(exploration)
    entered = (exploration.pos_x, exploration.pos_y)
    assert exploration.paused_at is not None

    await expedition_module.expedition_service.retreat_run(async_session, exploration.id)

    await async_session.refresh(exploration)
    assert exploration.paused_at is None
    assert (exploration.pos_x, exploration.pos_y) == entered


@pytest.mark.asyncio
async def test_return_clock_shifts_on_encounter_exit(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Return timing extends by the paused interval at the exit boundary."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    exploration.status = ExplorationStatus.RETURNING
    completes_at = datetime.utcnow() + timedelta(hours=1)
    exploration.return_started_at = datetime.utcnow() - timedelta(hours=1)
    exploration.return_completes_at = completes_at
    async_session.add(exploration)
    await async_session.commit()

    exploration_service.resume_from_encounter(exploration, now=exploration.position_as_of + timedelta(hours=1))
    await async_session.commit()

    await async_session.refresh(exploration)
    assert exploration.return_completes_at == completes_at + timedelta(hours=1)


@pytest.mark.asyncio
async def test_return_leg_entry_pauses_the_return(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """An in-progress return leg may enter a site, which pauses the return clock."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    exploration.status = ExplorationStatus.RETURNING
    exploration.return_started_at = datetime.utcnow() - timedelta(hours=1)
    exploration.return_completes_at = datetime.utcnow() + timedelta(hours=1)
    async_session.add(exploration)
    await async_session.commit()

    view = await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)

    await async_session.refresh(exploration)
    assert view.site_id == SITE_ID
    assert exploration.paused_at is not None
    assert SITE_ID in [
        site.id
        for site in await expedition_module.expedition_service.list_available_sites(async_session, exploration.id)
    ]


@pytest.mark.asyncio
async def test_spatial_offers_only_sites_near_the_trail(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A spatial run is offered the site its trail passes, never a distant one."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller, SITE_ID)

    available = await expedition_module.expedition_service.list_available_sites(async_session, exploration.id)
    offered = [site.id for site in available]

    assert SITE_ID in offered
    with pytest.raises(ValidationException):
        await expedition_module.expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")

    await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    await expedition_module.expedition_service.retreat_run(async_session, exploration.id)
    available = await expedition_module.expedition_service.list_available_sites(async_session, exploration.id)
    # A retreat stays resumable for the journey, so the trail-offered site is still listed.
    assert SITE_ID in [site.id for site in available]


@pytest.mark.asyncio
async def test_spatial_reentry_ignores_vault_cooldown(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A finished journey does not lock the site vault-wide for the next journey."""
    first = await _spatial_run_at_site(async_session, vault, dweller)
    await expedition_module.expedition_service.enter_run(async_session, first.id, SITE_ID)
    await expedition_module.expedition_service.retreat_run(async_session, first.id)

    dweller_data = {**create_fake_adult_dweller(), "level": 10, "health": 100, "max_health": 100}
    other = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=str(vault.id)))
    second = await _spatial_run_at_site(async_session, vault, other)

    available = await expedition_module.expedition_service.list_available_sites(async_session, second.id)
    assert SITE_ID in [site.id for site in available]
    await expedition_module.expedition_service.enter_run(async_session, second.id, SITE_ID)


@pytest.mark.asyncio
async def test_tick_does_not_expire_a_paused_journey(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """An active journey inside an encounter is never force-returned by timer expiry."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    # Past its planned duration, as a long site visit would leave it.
    exploration.start_time = datetime.utcnow() - timedelta(hours=25)
    async_session.add(exploration)
    await async_session.commit()

    await process_explorations(async_session, vault.id)

    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.ACTIVE
    assert exploration.paused_at is not None
