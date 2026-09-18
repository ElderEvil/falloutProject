"""Resource tick must see equipped outfits without paying a query per dweller.

The production path loads every dweller in every producing room once per tick
(`crud.resource.get_vault_resource_data`). Once outfit SPECIAL bonuses feed
`effective_stat`, that loader must carry the outfit too — and it must do so as
one batched query, not one per dweller, or the tick cost grows with vault size.

These tests pin the shape of the access rather than its speed: query counts are
stable across machines, wall time is not.
"""

import itertools
import math
import statistics
import time
from typing import Self

import pytest
from sqlalchemy import event
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.resource import resource as resource_crud
from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate

WARMUP_RUNS = 1
MEASURED_RUNS = 5
P95_UPPER_BOUND_SECONDS = 10.0


class _QueryCounter:
    """Counts executed statements for one engine connection."""

    def __init__(self, engine) -> None:
        self.statements: list[str] = []
        self._engine = engine

    def __enter__(self) -> Self:
        event.listen(self._engine.sync_engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *_exc) -> None:
        event.remove(self._engine.sync_engine, "before_cursor_execute", self._record)

    def _record(self, _conn, _cursor, statement, _params, _context, _executemany) -> None:
        self.statements.append(statement)

    @property
    def outfit_selects(self) -> list[str]:
        return [s for s in self.statements if "FROM outfit" in s]


async def _seed_producing_room(session: AsyncSession, vault_id, dwellers: int):
    room = await crud.room.create(
        session,
        obj_in=RoomCreate(
            name="Power Generator",
            category="Production",
            ability="Strength",
            base_cost=100,
            increment_cost=None,
            t2_upgrade_cost=None,
            t3_upgrade_cost=None,
            size_min=6,
            size_max=6,
            tier=1,
            output="1",
            capacity="1",
            vault_id=vault_id,
        ),
    )
    created = []
    for index in range(dwellers):
        dweller = await crud.dweller.create(
            session,
            obj_in=DwellerCreate(
                first_name=f"Worker{index}",
                last_name="Dweller",
                gender="male",
                rarity="common",
                vault_id=vault_id,
            ),
        )
        await crud.dweller.update(session, dweller.id, {"room_id": room.id})
        created.append(dweller)
    await session.commit()
    return room, created


_SUIT_SEQ = itertools.count()


async def _equip(session: AsyncSession, dweller_id, fire_resist: float = 0.0) -> Outfit:
    outfit = await crud.outfit.create(
        session,
        obj_in={
            "name": f"Worker suit {next(_SUIT_SEQ):02d}",
            "rarity": "Rare",
            "value": 100,
            "outfit_type": "rare_outfit",
            "fire_resist": fire_resist,
        },
    )
    return await crud.outfit.equip(db_session=session, item_id=outfit.id, dweller_id=dweller_id)


@pytest.mark.asyncio
async def test_resource_data_loads_equipped_outfits(async_session: AsyncSession, vault) -> None:
    """The tick's dweller load must carry the equipped outfit relationship."""
    _room, dwellers = await _seed_producing_room(async_session, vault.id, 2)
    suit = await _equip(async_session, dwellers[0].id, fire_resist=0.5)

    resource_data = await resource_crud.get_vault_resource_data(async_session, vault.id)

    loaded = {d.id: d for d in resource_data.rooms_with_dwellers[0][1]}
    assert loaded[dwellers[0].id].__dict__.get("outfit") is not None
    assert loaded[dwellers[0].id].__dict__["outfit"].id == suit.id
    assert loaded[dwellers[1].id].__dict__.get("outfit") is None


@pytest.mark.asyncio
async def test_resource_data_outfit_load_does_not_scale_per_dweller(async_session: AsyncSession, vault) -> None:
    """The outfit load is one batched query, so its count is flat in dweller count."""
    _room, dwellers = await _seed_producing_room(async_session, vault.id, 4)
    for dweller in dwellers:
        await _equip(async_session, dweller.id)
    async_session.expunge_all()

    with _QueryCounter(async_session.bind) as counter:
        await resource_crud.get_vault_resource_data(async_session, vault.id)

    assert len(counter.outfit_selects) == 1, (
        f"expected one batched outfit load, saw {len(counter.outfit_selects)}: {counter.outfit_selects}"
    )


@pytest.mark.asyncio
async def test_resource_data_outfit_query_count_is_constant(async_session: AsyncSession, vault) -> None:
    """Growing the vault must not add outfit queries to the tick's read."""
    _room, small = await _seed_producing_room(async_session, vault.id, 2)
    for dweller in small:
        await _equip(async_session, dweller.id)
    async_session.expunge_all()
    with _QueryCounter(async_session.bind) as small_counter:
        await resource_crud.get_vault_resource_data(async_session, vault.id)

    for index in range(2):
        dweller = await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(
                first_name=f"Extra{index}",
                last_name="Dweller",
                gender="female",
                rarity="common",
                vault_id=vault.id,
                room_id=small[0].room_id,
            ),
        )
        await _equip(async_session, dweller.id)
    await async_session.commit()
    async_session.expunge_all()

    with _QueryCounter(async_session.bind) as grown_counter:
        await resource_crud.get_vault_resource_data(async_session, vault.id)

    assert len(grown_counter.outfit_selects) == len(small_counter.outfit_selects)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_resource_tick_wall_time_with_outfits(async_session: AsyncSession, vault) -> None:
    """Wall-time probe for the tick once outfits are loaded.

    The printed timings are the signal — compare them across runs. The bound is
    deliberately generous, matching test_tick_perf.py, so CI never flakes on a
    loaded machine; the query-count tests above are the exact guard.

    Baseline at introduction (8 dwellers, local SQLite): mean ~2.8ms, p95 ~3.2ms.
    """
    _room, dwellers = await _seed_producing_room(async_session, vault.id, 8)
    for dweller in dwellers:
        await _equip(async_session, dweller.id)
    async_session.expunge_all()

    for _ in range(WARMUP_RUNS):
        await resource_crud.get_vault_resource_data(async_session, vault.id)
        async_session.expunge_all()

    samples_ms: list[float] = []
    for _ in range(MEASURED_RUNS):
        started = time.perf_counter()
        await resource_crud.get_vault_resource_data(async_session, vault.id)
        samples_ms.append((time.perf_counter() - started) * 1000.0)
        async_session.expunge_all()

    ordered = sorted(samples_ms)
    p95_ms = ordered[math.ceil(0.95 * len(ordered)) - 1]
    print(
        f"\n[resource-outfit-perf] dwellers={len(dwellers)} runs={MEASURED_RUNS} "
        f"mean={statistics.fmean(samples_ms):.1f}ms p95={p95_ms:.1f}ms max={max(samples_ms):.1f}ms"
    )
    assert p95_ms / 1000.0 < P95_UPPER_BOUND_SECONDS

    """Doubling the vault must not add outfit queries to the tick's read."""
    _room, small = await _seed_producing_room(async_session, vault.id, 2)
    for dweller in small:
        await _equip(async_session, dweller.id)
    async_session.expunge_all()
    with _QueryCounter(async_session.bind) as small_counter:
        await resource_crud.get_vault_resource_data(async_session, vault.id)

    for index in range(2):
        dweller = await crud.dweller.create(
            async_session,
            obj_in=DwellerCreate(
                first_name=f"Extra{index}",
                last_name="Dweller",
                gender="female",
                rarity="common",
                vault_id=vault.id,
                room_id=small[0].room_id,
            ),
        )
        await _equip(async_session, dweller.id)
    await async_session.commit()
    matched = (await async_session.execute(select(Dweller).where(Dweller.vault_id == vault.id))).scalars().all()
    assert len(matched) > len(small), "fixture failed to grow the vault"
    async_session.expunge_all()

    with _QueryCounter(async_session.bind) as grown_counter:
        await resource_crud.get_vault_resource_data(async_session, vault.id)

    assert len(grown_counter.outfit_selects) == len(small_counter.outfit_selects)
