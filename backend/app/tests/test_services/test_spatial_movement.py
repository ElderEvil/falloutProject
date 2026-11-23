import math
from datetime import timedelta
from typing import ClassVar
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import ExplorationStatus
from app.core.game_config import game_config
from app.crud.vault_slot import vault_slot
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.models.vault_slot import VaultSlot
from app.services.exploration_service import exploration_service
from app.services.game_tick.dwellers_tick import process_explorations
from app.services.map_service import map_service
from app.services.world_snapshot_service import world_snapshot_service
from app.utils.exceptions import ValidationException
from app.utils.serialize import serialize_naive_utc_datetime
from app.utils.time import utcnow
from app.utils.vault_slots import slot_coords

SPEED = 1 / game_config.exploration.dispatch.travel_hours_per_unit


async def _save(db, *objs):
    for obj in objs:
        db.add(obj)
    await db.commit()


async def _claim_slot(async_session: AsyncSession, vault: Vault, slot_index: int | None = None) -> int:
    if slot_index is None:
        slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
        await async_session.commit()
        return slot.slot_index
    await _save(async_session, VaultSlot(slot_index=slot_index, vault_id=vault.id))
    return slot_index


async def _depart(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, *, heading: float | None = 0, slot_index=None
):
    idx = await _claim_slot(async_session, vault, slot_index)
    await world_snapshot_service.get_or_generate(async_session)
    exploration = await exploration_service.send_dweller(
        async_session, vault.id, dweller.id, duration=4, heading_degrees=heading
    )
    return exploration, slot_coords(idx)


class TestSpatialMovement:
    pytestmark: ClassVar = [pytest.mark.asyncio, pytest.mark.usefixtures("default_world_snapshot")]

    async def test_vault_origin_is_slot_authoritative(self, async_session: AsyncSession, vault: Vault) -> None:
        assert await exploration_service._vault_origin(async_session, vault.id) is None
        slot_index = await _claim_slot(async_session, vault)
        assert await exploration_service._vault_origin(async_session, vault.id) == slot_coords(slot_index)

    async def test_spatial_depart_requires_a_slot(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        with pytest.raises(ValidationException, match="no map placement"):
            await exploration_service.depart(async_session, vault.id, [dweller.id], duration=4, heading_degrees=90)

    async def test_home_marker_agrees_with_the_slot(self, async_session: AsyncSession, vault: Vault) -> None:
        slot_index = await _claim_slot(async_session, vault)
        home = await map_service.ensure_home_marker(async_session, vault)
        assert (home.coord_x, home.coord_y) == slot_coords(slot_index)
        assert await exploration_service._vault_origin(async_session, vault.id) == (home.coord_x, home.coord_y)

    @pytest.mark.parametrize("heading", [90, None])
    async def test_depart_persists_a_spatial_run(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller, heading
    ):
        exploration, origin = await _depart(async_session, vault, dweller, heading=heading)
        if heading is None:
            assert exploration.heading_degrees is not None
            assert 0 <= exploration.heading_degrees < 360
        else:
            assert exploration.heading_degrees == 90
        assert (
            exploration.world_version == (await world_snapshot_service.get_or_generate(async_session)).generator_version
        )
        assert (exploration.origin_x, exploration.origin_y) == origin
        assert (exploration.pos_x, exploration.pos_y) == origin
        assert exploration.position_as_of is not None
        assert exploration.trail == [
            {"x": origin[0], "y": origin[1], "t": serialize_naive_utc_datetime(exploration.start_time)}
        ]

    async def test_position_advances_once_and_double_processing_is_noop(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        exploration, origin = await _depart(async_session, vault, dweller, heading=0)
        now = exploration.start_time + timedelta(hours=1)
        first = await exploration_service.advance(async_session, exploration.id, now=now)
        assert (first.status, first.pos_x, first.pos_y, first.position_as_of) == (
            ExplorationStatus.ACTIVE,
            pytest.approx(origin[0], abs=1e-6),
            pytest.approx(origin[1] - SPEED * 1, abs=1e-6),
            now,
        )
        assert len(first.trail) == 2
        second = await exploration_service.advance(async_session, exploration.id, now=now)
        assert (second.pos_x, second.pos_y, second.position_as_of, len(second.trail)) == (
            first.pos_x,
            first.pos_y,
            first.position_as_of,
            len(first.trail),
        )

    async def test_blocked_heading_returns_early(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ) -> None:
        exploration, origin = await _depart(async_session, vault, dweller, heading=0, slot_index=4)
        advanced = await exploration_service.advance(
            async_session, exploration.id, now=exploration.start_time + timedelta(hours=2)
        )
        assert advanced.status == ExplorationStatus.RETURNING
        assert (advanced.return_started_at is not None, advanced.return_completes_at is not None) == (True, True)
        # The dweller stopped before the water, not at the analytic 2h point.
        assert advanced.pos_y > origin[1] - SPEED * 2

    async def test_choose_heading_is_deterministic_and_prefers_clear_ground(
        self, async_session: AsyncSession, vault: Vault
    ) -> None:
        origin = slot_coords(await _claim_slot(async_session, vault))
        snapshot = await world_snapshot_service.get_or_generate(async_session)
        seed = uuid4()
        first = exploration_service.choose_heading(snapshot, origin, 4, seed=seed)
        assert first == exploration_service.choose_heading(snapshot, origin, 4, seed=seed)
        outbound = SPEED * 4 / 2
        scores = {
            heading: min(exploration_service._clear_distance(snapshot, origin, heading, outbound), outbound)
            for heading in range(0, 360, 15)
        }
        assert scores[first] == pytest.approx(max(scores.values()))

    async def test_suggest_heading_requires_a_slot(self, async_session: AsyncSession, vault: Vault) -> None:
        assert await exploration_service.suggest_heading(async_session, vault.id, duration=4, seed="nonce-1") is None
        await _claim_slot(async_session, vault)
        heading = await exploration_service.suggest_heading(async_session, vault.id, duration=4, seed="nonce-1")
        assert heading is not None
        assert 0 <= heading < 360

    async def test_no_slot_send_stays_legacy(self, async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
        exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
        assert (exploration.heading_degrees, exploration.pos_x) == (None, None)
        advanced = await exploration_service.advance(async_session, exploration.id, now=utcnow() + timedelta(hours=1))
        assert (advanced.status, advanced.pos_x, advanced.position_as_of) == (ExplorationStatus.ACTIVE, None, None)

    async def test_tick_advances_then_the_run_returns_home(
        self, async_session: AsyncSession, vault: Vault, dweller: Dweller
    ):
        exploration, origin = await _depart(async_session, vault, dweller, heading=0)
        exploration.start_time = utcnow() - timedelta(hours=1)
        await async_session.commit()
        stats = await process_explorations(async_session, vault.id)
        await async_session.refresh(exploration)
        assert (exploration.status, stats["active_count"]) == (ExplorationStatus.ACTIVE, 1)
        assert exploration.pos_y == pytest.approx(origin[1] - SPEED * 1, abs=0.5)

        forward_end = exploration.start_time + timedelta(hours=2)
        mid = await exploration_service.advance(async_session, exploration.id, now=forward_end + timedelta(seconds=1))
        assert (mid.status, mid.pos_y) == (ExplorationStatus.RETURNING, pytest.approx(origin[1] - SPEED * 2, abs=1e-6))
        arrived = await exploration_service.advance(async_session, exploration.id, now=forward_end + timedelta(hours=2))
        assert (arrived.status, arrived.pos_x, arrived.pos_y) == (
            ExplorationStatus.RETURNING,
            pytest.approx(origin[0], abs=1e-6),
            pytest.approx(origin[1], abs=1e-6),
        )
        assert arrived.return_completes_at == pytest.approx(forward_end + timedelta(hours=2), abs=timedelta(seconds=1))
