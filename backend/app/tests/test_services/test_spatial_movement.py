"""Spatial movement (slice 1): slot-authoritative origin + persisted directional movement."""

import math
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.vault_slot import vault_slot
from app.models.dweller import Dweller
from app.models.exploration import ExplorationStatus
from app.models.vault import Vault
from app.models.vault_slot import VaultSlot
from app.models.world_location import WorldLocation
from app.schemas.exploration_event import DiscoveryEventSchema
from app.services.exploration.event_generator import event_generator
from app.services.exploration_service import exploration_service
from app.services.world_snapshot_service import world_snapshot_service
from app.utils.exceptions import ValidationException
from app.utils.vault_slots import slot_coords

SPEED = 1 / game_config.exploration.dispatch.travel_hours_per_unit


async def _claim_slot(async_session: AsyncSession, vault: Vault, slot_index: int | None = None) -> int:
    """Claim a slot for the vault; a specific index is inserted directly."""
    if slot_index is None:
        slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
        await async_session.commit()
        return slot.slot_index
    async_session.add(VaultSlot(slot_index=slot_index, vault_id=vault.id))
    await async_session.commit()
    return slot_index


async def _ensure_snapshot(async_session: AsyncSession):
    return await world_snapshot_service.get_or_generate(async_session)


async def _spatial_depart(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, *, heading: float = 0, duration: int = 4
):
    return await exploration_service.send_dweller(
        async_session, vault.id, dweller.id, duration=duration, heading_degrees=heading
    )


# ---------------------------------------------------------------------------
# step 1: slot-authoritative origin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vault_origin_matches_slot_coords(async_session: AsyncSession, vault: Vault) -> None:
    """A vault with a slot departs from its slot placement."""
    slot_index = await _claim_slot(async_session, vault)

    origin = await exploration_service._vault_origin(async_session, vault.id)

    assert origin == slot_coords(slot_index)


@pytest.mark.asyncio
async def test_vault_origin_is_none_without_slot(async_session: AsyncSession, vault: Vault) -> None:
    """A vault without a slot has no origin: no production fallback to the map centre."""
    origin = await exploration_service._vault_origin(async_session, vault.id)

    assert origin is None


@pytest.mark.asyncio
async def test_spatial_depart_requires_a_slot(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """A slotless vault cannot start a spatial run (grandfathered, not map-centre)."""
    with pytest.raises(ValidationException, match="no map placement"):
        await exploration_service.depart(async_session, vault.id, [dweller.id], duration=4, heading_degrees=90)


@pytest.mark.asyncio
async def test_home_marker_agrees_with_the_slot(async_session: AsyncSession, vault: Vault) -> None:
    """The home marker sits at the same slot coordinates as the departure origin."""
    from app.services.map_service import map_service

    slot_index = await _claim_slot(async_session, vault)
    home = await map_service.ensure_home_marker(async_session, vault)

    assert (home.coord_x, home.coord_y) == slot_coords(slot_index)
    assert await exploration_service._vault_origin(async_session, vault.id) == (home.coord_x, home.coord_y)


# ---------------------------------------------------------------------------
# step 2: directional movement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heading_depart_persists_movement_fields(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A heading departure records world version, origin, heading, position, trail, position_as_of."""
    slot_index = await _claim_slot(async_session, vault)
    snapshot = await _ensure_snapshot(async_session)
    origin = slot_coords(slot_index)

    exploration = await _spatial_depart(async_session, vault, dweller, heading=90)

    assert exploration.heading_degrees == 90
    assert exploration.world_version == snapshot.generator_version
    assert (exploration.origin_x, exploration.origin_y) == origin
    assert (exploration.pos_x, exploration.pos_y) == origin
    assert exploration.position_as_of is not None
    assert exploration.trail == [{"x": origin[0], "y": origin[1], "t": exploration.start_time.isoformat()}]


@pytest.mark.asyncio
async def test_position_advances_along_heading_by_elapsed_time(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """Position advances along the heading by elapsed time (pinned clock, no sleep)."""
    slot_index = await _claim_slot(async_session, vault)
    await _ensure_snapshot(async_session)
    origin = slot_coords(slot_index)

    exploration = await _spatial_depart(async_session, vault, dweller, heading=0, duration=4)
    now = exploration.start_time + timedelta(hours=1)

    advanced = await exploration_service.advance(async_session, exploration.id, now=now)

    assert advanced.status == ExplorationStatus.ACTIVE
    assert advanced.pos_x == pytest.approx(origin[0], abs=1e-6)
    assert advanced.pos_y == pytest.approx(origin[1] - SPEED * 1, abs=1e-6)
    assert advanced.position_as_of == now
    assert len(advanced.trail) == 2


@pytest.mark.asyncio
async def test_blocked_heading_returns_early(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """A heading that hits water stops forward movement and starts the return."""
    slot_index = await _claim_slot(async_session, vault, slot_index=4)
    await _ensure_snapshot(async_session)
    origin = slot_coords(slot_index)

    exploration = await _spatial_depart(async_session, vault, dweller, heading=0, duration=4)
    now = exploration.start_time + timedelta(hours=2)

    advanced = await exploration_service.advance(async_session, exploration.id, now=now)

    assert advanced.status == ExplorationStatus.RETURNING
    assert advanced.return_started_at is not None
    assert advanced.return_completes_at is not None
    # The dweller stopped before the water, not at the analytic 2h point.
    assert advanced.pos_y > origin[1] - SPEED * 2


@pytest.mark.asyncio
async def test_double_processing_is_noop(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """Reprocessing an already-processed interval changes nothing."""
    slot_index = await _claim_slot(async_session, vault)
    await _ensure_snapshot(async_session)

    exploration = await _spatial_depart(async_session, vault, dweller, heading=0, duration=4)
    now = exploration.start_time + timedelta(hours=1)

    first = await exploration_service.advance(async_session, exploration.id, now=now)
    second = await exploration_service.advance(async_session, exploration.id, now=now)

    assert second.pos_x == first.pos_x
    assert second.pos_y == first.pos_y
    assert second.position_as_of == first.position_as_of
    assert len(second.trail) == len(first.trail)


@pytest.mark.asyncio
async def test_legacy_null_heading_run_untouched(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """A legacy run (heading NULL) keeps today's behavior: advance() is a no-op."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    assert exploration.heading_degrees is None
    assert exploration.pos_x is None

    advanced = await exploration_service.advance(
        async_session, exploration.id, now=datetime.utcnow() + timedelta(hours=1)
    )

    assert advanced.status == ExplorationStatus.ACTIVE
    assert advanced.pos_x is None
    assert advanced.position_as_of is None


@pytest.mark.asyncio
async def test_spatial_run_writes_no_registry_rows_from_names(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A spatial discovery records the journal but creates no WorldLocation row."""
    await _claim_slot(async_session, vault)
    await _ensure_snapshot(async_session)
    exploration = await _spatial_depart(async_session, vault, dweller, heading=0, duration=4)
    exploration.start_time = datetime.utcnow() - timedelta(minutes=10)
    await async_session.commit()

    mock_event = DiscoveryEventSchema(
        location_name="Crater of Mystery",
        description="Your dweller has discovered Crater of Mystery in the wasteland.",
    )
    with patch.object(event_generator, "generate_event", return_value=mock_event):
        result = await exploration_service.process_event(async_session, exploration)

    assert result.events[-1]["type"] == "discovery"
    assert result.events[-1]["location_name"] == "Crater of Mystery"
    rows = (
        (await async_session.execute(select(WorldLocation).where(WorldLocation.name == "Crater of Mystery")))
        .scalars()
        .all()
    )
    assert rows == []


@pytest.mark.asyncio
async def test_tick_advances_spatial_run(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    """The game tick drives a spatial run's position through advance()."""
    from app.services.game_tick.dwellers_tick import process_explorations

    slot_index = await _claim_slot(async_session, vault)
    await _ensure_snapshot(async_session)
    origin = slot_coords(slot_index)

    exploration = await _spatial_depart(async_session, vault, dweller, heading=0, duration=4)
    exploration.start_time = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    stats = await process_explorations(async_session, vault.id)

    await async_session.refresh(exploration)
    assert exploration.status == ExplorationStatus.ACTIVE
    assert exploration.pos_y == pytest.approx(origin[1] - SPEED * 1, abs=0.5)
    assert stats["active_count"] == 1


@pytest.mark.asyncio
async def test_spatial_run_returns_home_and_finalizes(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A full spatial journey retraces the trail home and finalizes on arrival."""
    slot_index = await _claim_slot(async_session, vault)
    await _ensure_snapshot(async_session)
    origin = slot_coords(slot_index)

    exploration = await _spatial_depart(async_session, vault, dweller, heading=0, duration=4)
    forward_end = exploration.start_time + timedelta(hours=2)

    mid = await exploration_service.advance(async_session, exploration.id, now=forward_end + timedelta(seconds=1))
    assert mid.status == ExplorationStatus.RETURNING
    assert mid.pos_y == pytest.approx(origin[1] - SPEED * 2, abs=1e-6)

    arrived = await exploration_service.advance(async_session, exploration.id, now=forward_end + timedelta(hours=2))
    assert arrived.status == ExplorationStatus.RETURNING
    assert arrived.pos_x == pytest.approx(origin[0], abs=1e-6)
    assert arrived.pos_y == pytest.approx(origin[1], abs=1e-6)
    assert arrived.return_completes_at == pytest.approx(forward_end + timedelta(hours=2), abs=timedelta(seconds=1))
