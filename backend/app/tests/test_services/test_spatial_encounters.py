"""One-time journey encounters (slice 3b): consumption, travel-clock pause, deferred arrival."""

import math
from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ExpeditionRunStatus, ExplorationStatus
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services import catalog_service as data_loader
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
    dweller.radiation = 0
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
    run.flags = {}  # Simulate a room-based run saved before single-scene encounters.
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
    started_at = exploration.start_time

    exploration_service.resume_from_encounter(exploration, now=exploration.position_as_of + timedelta(hours=1))
    await async_session.commit()

    await async_session.refresh(exploration)
    assert exploration.return_completes_at == completes_at + timedelta(hours=1)
    assert exploration.start_time == started_at + timedelta(hours=1)


@pytest.mark.asyncio
async def test_return_leg_entry_pauses_the_return(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """An in-progress return leg may enter a site, which pauses the return clock."""
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    exploration.status = ExplorationStatus.RETURNING
    exploration.return_started_at = datetime.utcnow() - timedelta(hours=1)
    exploration.return_started_at = datetime.utcnow()
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


@pytest.mark.asyncio
async def test_site_discovery_is_durable_and_not_repeated_on_return(async_session, vault, dweller):
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    await expedition_module.expedition_service.discover_sites(async_session, exploration.id)
    await async_session.refresh(exploration)
    discoveries = [event for event in exploration.events if event.get("event") == "site_found"]
    assert SITE_ID in {event["site_id"] for event in discoveries}
    assert exploration.paused_at is None
    from app.crud.notification import notification as notification_crud

    notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
    reports = [n for n in notifications if (n.meta_data or {}).get("event") == "site_found"]
    assert len(reports) == len(discoveries)
    assert {n.meta_data["site_id"] for n in reports} == {event["site_id"] for event in discoveries}
    exploration.status = ExplorationStatus.RETURNING
    exploration.return_started_at = datetime.utcnow()
    exploration.return_completes_at = datetime.utcnow() + timedelta(hours=1)
    async_session.add(exploration)
    await async_session.commit()

    await expedition_module.expedition_service.discover_sites(async_session, exploration.id)
    await async_session.refresh(exploration)
    assert [event for event in exploration.events if event.get("event") == "site_found"] == discoveries
    assert SITE_ID in {
        s.id for s in await expedition_module.expedition_service.list_available_sites(async_session, exploration.id)
    }
    view = await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    assert view.site_id == SITE_ID


@pytest.mark.asyncio
async def test_expired_return_rejects_new_site_before_tick_finalizes(async_session, vault, dweller):
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    exploration.status = ExplorationStatus.RETURNING
    exploration.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()
    with pytest.raises(ValidationException, match="arrived home"):
        await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    assert await expedition_module.expedition_service.list_available_sites(async_session, exploration.id) == []
    assert await crud.expedition_run.get_open_for_exploration(async_session, exploration.id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_insert", [1, 2])
async def test_discovery_notification_failure_rolls_back_report_and_emits_nothing(
    async_session, vault, dweller, monkeypatch, failed_insert
):
    from unittest.mock import AsyncMock

    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    from app.crud.notification import notification as notification_crud
    from app.services.notification_service import manager, sse_manager

    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    exploration_id, user_id = exploration.id, vault.user_id
    original_events = list(exploration.events)
    publish = AsyncMock()
    websocket = AsyncMock()
    monkeypatch.setattr(sse_manager, "publish", publish)
    monkeypatch.setattr(manager, "send_personal_message", websocket)
    connection = (await async_session.connection()).sync_connection

    inserted = 0

    def fail_notification(conn, cursor, statement, parameters, context, executemany):
        nonlocal inserted
        if statement.lstrip().upper().startswith("INSERT INTO NOTIFICATION"):
            inserted += 1
        if statement.lstrip().upper().startswith("INSERT INTO NOTIFICATION") and inserted == failed_insert:
            raise OperationalError(statement, parameters, RuntimeError("notification insert failed"))

    event.listen(connection, "before_cursor_execute", fail_notification)
    try:
        with pytest.raises(OperationalError):
            await expedition_module.expedition_service.discover_sites(async_session, exploration_id)
    finally:
        event.remove(connection, "before_cursor_execute", fail_notification)
        await async_session.rollback()
    reloaded = await crud.exploration.get(async_session, exploration_id)
    assert reloaded.events == original_events
    notifications = await notification_crud.get_user_notifications(async_session, user_id)
    assert not [n for n in notifications if (n.meta_data or {}).get("event") == "site_found"]
    assert not async_session.info.get("deferred_notification_deliveries")
    publish.assert_not_awaited()
    websocket.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("rejection", ["dead", "expired", "legacy", "off_trail"])
async def test_ineligible_discoveries_leave_no_reports(async_session, vault, dweller, rejection):
    from app.crud.notification import notification as notification_crud

    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    if rejection == "dead":
        dweller.is_dead = True
    elif rejection == "expired":
        exploration.status = ExplorationStatus.RETURNING
        exploration.return_completes_at = datetime.utcnow() - timedelta(seconds=1)
    elif rejection == "legacy":
        exploration.heading_degrees = None
    else:
        exploration.trail = [{"x": 100000, "y": 100000, "t": datetime.utcnow().isoformat()}]
    async_session.add(dweller)
    async_session.add(exploration)
    await async_session.commit()
    original_events = list(exploration.events)
    await expedition_module.expedition_service.discover_sites(async_session, exploration.id)
    await async_session.refresh(exploration)
    assert exploration.events == original_events
    notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
    assert not [n for n in notifications if (n.meta_data or {}).get("event") == "site_found"]


@pytest.mark.asyncio
async def test_tick_discovers_sites_on_return_leg(async_session, vault, dweller):
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    exploration.status = ExplorationStatus.RETURNING
    exploration.return_started_at = datetime.utcnow()
    exploration.return_completes_at = datetime.utcnow() + timedelta(hours=1)
    async_session.add(exploration)
    await async_session.commit()
    await process_explorations(async_session, vault.id)
    await async_session.refresh(exploration)
    discoveries = [event for event in exploration.events if event.get("event") == "site_found"]
    assert SITE_ID in {event["site_id"] for event in discoveries}
    assert exploration.status == ExplorationStatus.RETURNING
    assert exploration.paused_at is None


@pytest.mark.asyncio
async def test_discovery_respects_site_level_gate(async_session, vault, dweller):
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    dweller.level = 1
    async_session.add(dweller)
    await async_session.commit()
    await expedition_module.expedition_service.discover_sites(async_session, exploration.id)
    await async_session.refresh(exploration)
    assert SITE_ID not in {event.get("site_id") for event in exploration.events}
    with pytest.raises(ValidationException, match="needs dweller level"):
        await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)


@pytest.mark.asyncio
async def test_open_site_reconnect_survives_original_return_deadline(async_session, vault, dweller):
    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    exploration.status = ExplorationStatus.RETURNING
    exploration.return_started_at = datetime.utcnow()
    exploration.return_completes_at = datetime.utcnow() + timedelta(hours=1)
    async_session.add(exploration)
    await async_session.commit()
    view = await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    exploration.return_completes_at = datetime.utcnow() - timedelta(minutes=10)
    async_session.add(exploration)
    await async_session.commit()
    reconnected = await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    assert reconnected.site_id == view.site_id
    assert reconnected.room_index == view.room_index
    assert exploration.paused_at is not None


@pytest.mark.asyncio
async def test_discovery_accepts_production_raw_sqlalchemy_session(async_session, vault, dweller):
    from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession

    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    async with RawAsyncSession(
        bind=await async_session.connection(),
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as tick_session:
        await expedition_module.expedition_service.discover_sites(tick_session, exploration.id)
    await async_session.refresh(exploration)
    assert SITE_ID in {event.get("site_id") for event in exploration.events if event.get("event") == "site_found"}


@pytest.mark.asyncio
async def test_new_spatial_site_is_one_interior_encounter(async_session, vault, dweller):
    import random

    from app.schemas.expedition import ExpeditionResolveRequest

    exploration = await _spatial_run_at_site(async_session, vault, dweller, "super_duper_mart")
    for stat in ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"):
        setattr(exploration, f"dweller_{stat}", 10)
    async_session.add(exploration)
    await async_session.commit()
    view = await expedition_module.expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    assert view.room_total == 1
    assert view.room_name == "Supermarket Interior"
    assert view.scene_id == "supermarket_interior"
    assert view.node.kind == "combat"
    assert "parking" not in view.node.prompt.lower()
    random.seed(570)
    resolved = view
    for _ in range(100):
        resolved = await expedition_module.expedition_service.resolve_node(
            async_session, exploration.id, ExpeditionResolveRequest()
        )
        if resolved.status != "in_room":
            break
    assert resolved.status == "cleared"
    assert resolved.room_index == 0
    assert resolved.scene_id == view.scene_id
    assert resolved.finale_paid
    assert resolved.outcome.caps_gained > 0
    await async_session.refresh(exploration)
    assert exploration.paused_at is None
    assert exploration.enemies_encountered == len(view.node.enemy_names)
    assert "super_duper_mart" not in {
        site.id
        for site in await expedition_module.expedition_service.list_available_sites(async_session, exploration.id)
    }
    with pytest.raises(ValidationException, match="No open expedition run"):
        await expedition_module.expedition_service.resolve_node(
            async_session, exploration.id, ExpeditionResolveRequest()
        )


@pytest.mark.asyncio
async def test_preexisting_spatial_run_keeps_its_saved_rooms(async_session, vault, dweller):
    exploration = await _spatial_run_at_site(async_session, vault, dweller, "super_duper_mart")
    run = await crud.expedition_run.create_run(
        async_session, exploration_id=exploration.id, vault_id=vault.id, site_id="super_duper_mart"
    )
    run.room_cursor = 2
    async_session.add(run)
    await async_session.commit()
    view = await expedition_module.expedition_service.current_view(async_session, exploration.id)
    assert view.room_index == 2
    assert view.room_total == 4
    assert view.room_name == "Storage Room"


@pytest.mark.asyncio
async def test_scene_briefing_uses_persisted_enemy_roster(async_session, vault, dweller):
    exploration = await _spatial_run_at_site(async_session, vault, dweller, "super_duper_mart")
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    combat = run.flags["combat"]
    enemy = combat["opponents"][0]
    run.flags = {**run.flags, "combat": {**combat, "opponents": [dict(enemy), dict(enemy)]}}
    async_session.add(run)
    await async_session.commit()

    view = await expedition_module.expedition_service.current_view(async_session, exploration.id)
    assert view.node.enemy_names == [enemy["name"], enemy["name"]]
    assert len(view.combat_state.fighters) == 3
    assert view.combat_state.round == 0


@pytest.mark.asyncio
async def test_single_scene_defeat_is_nonlethal_consumed_and_resumes_travel(async_session, vault, dweller):
    from app.schemas.expedition import ExpeditionResolveRequest

    exploration = await _spatial_run_at_site(async_session, vault, dweller, "super_duper_mart")
    dweller.health = 1
    async_session.add(dweller)
    async_session.add(exploration)
    await async_session.commit()
    initial = await expedition_module.expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    defeated = initial
    for _ in range(100):
        defeated = await expedition_module.expedition_service.resolve_node(
            async_session, exploration.id, ExpeditionResolveRequest()
        )
        if defeated.status != "in_room":
            break
    assert defeated.defeated
    assert defeated.status == "defeated"
    assert defeated.room_index == 0
    assert not defeated.finale_paid
    assert defeated.outcome.caps_gained == 0
    assert exploration.paused_at is None
    assert dweller.health == 1
    assert not dweller.is_dead
    assert defeated.outcome.loot_gained == []
    reconnect = await expedition_module.expedition_service.current_view(async_session, exploration.id)
    assert reconnect is None
    assert "super_duper_mart" not in {
        site.id
        for site in await expedition_module.expedition_service.list_available_sites(async_session, exploration.id)
    }
    with pytest.raises(ResourceConflictException, match="spent"):
        await expedition_module.expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")


@pytest.mark.asyncio
async def test_single_scene_resolution_late_failure_rolls_back_fight_and_haul(
    async_session, vault, dweller, monkeypatch
):
    import random
    from unittest.mock import AsyncMock

    from sqlalchemy import event
    from sqlalchemy.exc import SQLAlchemyError

    from app.schemas.expedition import ExpeditionResolveRequest
    from app.services.notification_service import manager, sse_manager

    exploration = await _spatial_run_at_site(async_session, vault, dweller, "super_duper_mart")
    for stat in ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"):
        setattr(exploration, f"dweller_{stat}", 10)
    async_session.add(exploration)
    await async_session.commit()
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    run.flags = {
        **run.flags,
        "combat": {
            **run.flags["combat"],
            "next_attack_team": "B",
            "opponents": [{**enemy, "power": 100} for enemy in run.flags["combat"]["opponents"]],
        },
    }
    async_session.add(run)
    await async_session.commit()
    exploration_id, dweller_id, run_id = exploration.id, dweller.id, run.id
    before = (
        exploration.total_caps_found,
        list(exploration.loot_collected),
        list(exploration.events),
        exploration.paused_at,
    )
    health_before = dweller.health
    publish, websocket = AsyncMock(), AsyncMock()
    monkeypatch.setattr(sse_manager, "publish", publish)
    monkeypatch.setattr(manager, "send_personal_message", websocket)
    connection = (await async_session.connection()).sync_connection
    damaged = []

    def fail_run_update(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE dweller"):
            damaged.append(True)
        if statement.startswith("UPDATE expeditionrun"):
            raise SQLAlchemyError("late run write failed")

    event.listen(connection, "before_cursor_execute", fail_run_update)
    random.seed(570)
    try:
        with pytest.raises(SQLAlchemyError, match="late run write"):
            await expedition_module.expedition_service.resolve_node(
                async_session, exploration_id, ExpeditionResolveRequest()
            )
    finally:
        event.remove(connection, "before_cursor_execute", fail_run_update)
        await async_session.rollback()
    assert damaged
    saved = await crud.exploration.get(async_session, exploration_id)
    assert (saved.total_caps_found, saved.loot_collected, saved.events, saved.paused_at) == before
    assert (await crud.dweller.get(async_session, dweller_id)).health == health_before
    saved_run = await crud.expedition_run.get(async_session, run_id)
    assert saved_run.status == ExpeditionRunStatus.IN_ROOM
    assert saved_run.finished_at is None
    assert saved.enemies_encountered == 0
    publish.assert_not_awaited()
    websocket.assert_not_awaited()


@pytest.mark.asyncio
async def test_single_scene_invalid_choice_leaves_run_untouched(async_session, vault, dweller):
    from app.schemas.expedition import ExpeditionResolveRequest

    exploration = await _spatial_run_at_site(async_session, vault, dweller)
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, SITE_ID)
    health_before, caps_before, events_before = dweller.health, exploration.total_caps_found, list(exploration.events)
    exploration_id, dweller_id = exploration.id, dweller.id
    with pytest.raises(ValidationException, match="do not accept a stat-check choice"):
        await expedition_module.expedition_service.resolve_node(
            async_session, exploration_id, ExpeditionResolveRequest(choice_id="invalid")
        )
    await async_session.rollback()
    saved = await crud.exploration.get(async_session, exploration_id)
    assert saved.total_caps_found == caps_before
    assert saved.events == events_before
    assert saved.paused_at is not None
    assert (await crud.dweller.get(async_session, dweller_id)).health == health_before
    assert (await crud.expedition_run.get_open_for_exploration(async_session, exploration_id)).room_cursor == 0


@pytest.mark.asyncio
async def test_scene_combat_reconnect_skill_and_stale_round_rejection(async_session, vault, dweller):
    from copy import deepcopy

    from app.schemas.expedition import ExpeditionResolveRequest

    exploration = await _spatial_run_at_site(async_session, vault, dweller, "super_duper_mart")
    entered = await expedition_module.expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    assert entered.combat_state.round == 0
    assert entered.combat_state.fighters[0].active_skill.charge == 0
    with pytest.raises(ValidationException, match="not ready"):
        await expedition_module.expedition_service.resolve_node(
            async_session, exploration.id, ExpeditionResolveRequest(use_skill=True)
        )
    first = await expedition_module.expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(expected_round=0)
    )
    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    saved_state = deepcopy(run.flags["combat"])
    with pytest.raises(ResourceConflictException, match="advanced"):
        await expedition_module.expedition_service.resolve_node(
            async_session, exploration.id, ExpeditionResolveRequest(expected_round=0)
        )
    reconnected = await expedition_module.expedition_service.current_view(async_session, exploration.id)
    assert reconnected.combat_state == first.combat_state
    assert run.flags["combat"] == saved_state
    # A full meter is persisted server state, never supplied by the client.
    run.flags = {**run.flags, "combat": {**saved_state, "charge": 100, "next_attack_team": "A"}}
    async_session.add(run)
    await async_session.commit()
    skilled = await expedition_module.expedition_service.resolve_node(
        async_session, exploration.id, ExpeditionResolveRequest(use_skill=True)
    )
    assert any(event.action and event.action.skill for event in skilled.combat_state.events)
    assert skilled.combat_state.fighters[0].active_skill.charge < 100


@pytest.mark.asyncio
async def test_scene_reward_notification_failure_rolls_back_final_turn(async_session, vault, dweller, monkeypatch):
    from copy import deepcopy
    from unittest.mock import AsyncMock

    from sqlalchemy import event
    from sqlalchemy.exc import SQLAlchemyError

    from app.schemas.expedition import ExpeditionResolveRequest
    from app.services.notification_service import manager, notification_service, sse_manager

    exploration = await _spatial_run_at_site(async_session, vault, dweller, "super_duper_mart")
    await expedition_module.expedition_service.enter_run(async_session, exploration.id, "super_duper_mart")
    run = await crud.expedition_run.get_open_for_exploration(async_session, exploration.id)
    run.flags = {
        **run.flags,
        "combat": {
            **run.flags["combat"],
            "opponents": [{**enemy, "hp": 1} for enemy in run.flags["combat"]["opponents"]],
            "carry": {run.flags["combat"]["opponents"][0]["key"] + "#0": 0.99},
        },
    }
    async_session.add(run)
    await async_session.commit()
    exploration_id, run_id, user_id = exploration.id, run.id, vault.user_id
    before = deepcopy(
        (exploration.total_caps_found, exploration.loot_collected, exploration.events, exploration.paused_at, run.flags)
    )
    publish, websocket = AsyncMock(), AsyncMock()
    monkeypatch.setattr(sse_manager, "publish", publish)
    monkeypatch.setattr(manager, "send_personal_message", websocket)
    connection = (await async_session.connection()).sync_connection
    written = []

    def fail_notification(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE exploration"):
            written.append(True)
        if statement.startswith("INSERT INTO notification"):
            raise SQLAlchemyError("final notification failed")

    event.listen(connection, "before_cursor_execute", fail_notification)
    try:
        with pytest.raises(SQLAlchemyError, match="final notification"):
            await expedition_module.expedition_service.resolve_node(
                async_session, exploration_id, ExpeditionResolveRequest()
            )
    finally:
        event.remove(connection, "before_cursor_execute", fail_notification)
        await async_session.rollback()
        notification_service.discard_deferred_notifications(async_session)
    saved = await crud.exploration.get(async_session, exploration_id)
    saved_run = await crud.expedition_run.get(async_session, run_id)
    assert written
    assert (saved.total_caps_found, saved.loot_collected, saved.events, saved.paused_at, saved_run.flags) == before
    assert saved_run.status == ExpeditionRunStatus.IN_ROOM
    assert saved_run.finished_at is None
    from app.crud.notification import notification as notification_crud

    assert not [
        n
        for n in await notification_crud.get_user_notifications(async_session, user_id)
        if (n.meta_data or {}).get("event") == "site_cleared"
    ]
    publish.assert_not_awaited()
    websocket.assert_not_awaited()


@pytest.mark.parametrize("first_health", [40, 0])
async def test_duplicate_scene_enemies_have_stable_numbered_labels(
    async_session: AsyncSession, dweller: Dweller, first_health: int
) -> None:
    from app.services.exploration.site_combat_service import combat_view, resolve_turn

    dweller = await crud.dweller.get(async_session, dweller.id)
    dweller.health = dweller.max_health = 100
    dweller.radiation = 0
    opponent = {"key": "raider", "name": "Raider", "hp": 40, "max_hp": 40, "power": 100}
    state = {
        "round": 0,
        "next_attack_team": "B",
        "opponents": [
            {**opponent, "hp": first_health},
            {**opponent, "key": "feral-ghoul", "name": "Feral Ghoul"},
            dict(opponent),
        ],
        "charge": 0,
        "carry": {},
        "events": [],
    }
    fighters = combat_view(state, dweller).fighters[1:]
    assert [fighter.name for fighter in fighters] == ["Raider 1", "Feral Ghoul", "Raider 2"]
    assert [fighter.id for fighter in fighters] == ["raider#0", "feral-ghoul#1", "raider#2"]

    resolved, *_ = resolve_turn(state, dweller, use_skill=False)
    assert any("Raider 2 hits" in event["message"] for event in resolved["events"])
    assert any("Raider 1 hits" in event["message"] for event in resolved["events"]) == (first_health > 0)
    assert [fighter.name for fighter in combat_view(resolved, dweller).fighters[1:]] == [
        "Raider 1",
        "Feral Ghoul",
        "Raider 2",
    ]
    assert [enemy["name"] for enemy in resolved["opponents"]] == ["Raider", "Feral Ghoul", "Raider"]
