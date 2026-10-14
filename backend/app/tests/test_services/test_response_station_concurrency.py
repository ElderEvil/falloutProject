"""Live-PostgreSQL concurrency checks for Response Station expansion and occupancy.

Two concurrent expands must charge and grow exactly once, and a station down to
its last free slot must admit exactly one of two concurrent assignments. The guard
is the repo's existing advisory-lock primitive; SQLite cannot demonstrate it (no
advisory locks, single writer), so these run against live PostgreSQL and skip when
it is unavailable — mirroring ``test_hazard_team_concurrency``.
"""

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core import db_locks
from app.core.config import settings
from app.models.incident import IncidentType
from app.models.team import DISPATCHED_STATUS
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.dweller_service import dweller_service
from app.services.hazard_team_service import hazard_team_service
from app.services.room_service import room_service
from app.tests.factory.vaults import random_vault_number
from app.utils.exceptions import ResourceConflictException

pytestmark = pytest.mark.integration

#: Format the production helper must produce; kept literal here so the collision
#: tests do not depend on the (new) production symbol to collect.
_STATION_KEY_PREFIX = "response-station"


def _station_lock_key(room_id) -> str:
    return f"{_STATION_KEY_PREFIX}:{room_id}"


def _response_station_create(vault_id, *, x: int = 1, size: int = 3) -> RoomCreate:
    """The unique Response Station catalog payload (null incremental cost, 3..9 footprint)."""
    return RoomCreate(
        vault_id=vault_id,
        name="Response Station",
        category=RoomTypeEnum.RESPONSE,
        ability=SPECIALEnum.ENDURANCE,
        population_required=None,
        base_cost=600,
        incremental_cost=None,
        t2_upgrade_cost=None,
        t3_upgrade_cost=None,
        capacity=None,
        output=None,
        size_min=3,
        size_max=9,
        size=size,
        tier=1,
        coordinate_x=x,
        coordinate_y=1,
        image_url=None,
        speedup_multiplier=1.0,
        capacity_formula=None,
        output_formula=None,
    )


def _production_room_create(vault_id, *, name: str = "Incident Room", x: int = 12) -> RoomCreate:
    return RoomCreate(
        vault_id=vault_id,
        name=name,
        category=RoomTypeEnum.PRODUCTION,
        ability=SPECIALEnum.STRENGTH,
        population_required=None,
        base_cost=100,
        incremental_cost=25,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        capacity=None,
        output=None,
        size_min=3,
        size_max=9,
        size=3,
        tier=1,
        coordinate_x=x,
        coordinate_y=1,
        image_url=None,
        speedup_multiplier=1.0,
        capacity_formula=None,
        output_formula=None,
    )


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncIterator[AsyncEngine]:
    """Connect to the live PostgreSQL database, skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping the station concurrency check")

    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def station_ctx(live_pg_engine: AsyncEngine, dweller_data: dict) -> AsyncIterator[dict]:
    """One vault with a Response Station, a production room and adult dwellers, removed afterwards."""
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid4().hex[:8]

    async with maker() as session:
        user = await crud.user.create(
            session,
            obj_in=UserCreate(
                username=f"station-{suffix}", email=f"station-{suffix}@example.com", password="secret-password-123"
            ),
        )
        vault = await crud.vault.create(
            session,
            obj_in=VaultCreateWithUserID(
                number=random_vault_number(),
                bottle_caps=100_000,
                happiness=50,
                power=50,
                food=50,
                water=50,
                population_max=200,
                user_id=user.id,
            ),
        )
        station = await crud.room.create(session, obj_in=_response_station_create(vault.id))
        incident_room = await crud.room.create(session, obj_in=_production_room_create(vault.id))
        dwellers = [
            await crud.dweller.create(session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
            for _ in range(6)
        ]
        ids = {
            "maker": maker,
            "vault_id": vault.id,
            "station_id": station.id,
            "incident_room_id": incident_room.id,
            "dweller_ids": [dweller.id for dweller in dwellers],
            "user_id": user.id,
        }

    try:
        yield ids
    finally:
        async with maker() as session:
            for statement in (
                "DELETE FROM incident_participant WHERE incident_id IN (SELECT id FROM incident WHERE vault_id = :vault_id)",
                "DELETE FROM incident WHERE vault_id = :vault_id",
                "DELETE FROM notification WHERE vault_id = :vault_id",
                "DELETE FROM team_member WHERE team_id IN (SELECT id FROM team WHERE vault_id = :vault_id)",
                "DELETE FROM team WHERE vault_id = :vault_id",
                "DELETE FROM room WHERE vault_id = :vault_id",
                "DELETE FROM dweller WHERE vault_id = :vault_id",
                "DELETE FROM vault WHERE id = :vault_id",
            ):
                await session.execute(text(statement), {"vault_id": ids["vault_id"]})
            await session.execute(text('DELETE FROM "user" WHERE id = :user_id'), {"user_id": ids["user_id"]})
            await session.commit()


async def _read_station_and_caps(ctx: dict) -> tuple[int, int]:
    async with ctx["maker"]() as reader:
        station = await crud.room.get(reader, ctx["station_id"])
        vault = await crud.vault.get(reader, id=ctx["vault_id"])
        return station.size, vault.bottle_caps


async def _occupants(ctx: dict) -> int:
    async with ctx["maker"]() as reader:
        return await crud.dweller.count_in_room(reader, ctx["station_id"])


# ---------------------------------------------------------------------------
# Expansion: one concurrent request wins, the other charges and grows nothing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_concurrent_expand_is_rejected_without_charge_or_growth(station_ctx: dict) -> None:
    """While one expand holds the vault placement lock, a second is refused; net: one charge, one growth."""
    from app.services.room_assignment_policy import vault_placement_lock_key

    station_id = station_ctx["station_id"]
    starting_size, starting_caps = await _read_station_and_caps(station_ctx)

    async with (
        station_ctx["maker"]() as holder,
        db_locks.hold_advisory_lock(holder, vault_placement_lock_key(station_ctx["vault_id"])) as acquired,
    ):
        assert acquired is True
        async with station_ctx["maker"]() as contender:
            with pytest.raises(ResourceConflictException):
                await room_service.expand_room(contender, station_id)

    # The refused request moved no caps and changed no footprint.
    assert (await _read_station_and_caps(station_ctx)) == (starting_size, starting_caps)

    # Exactly one charge and one growth when the room is free again.
    async with station_ctx["maker"]() as worker:
        grown = await room_service.expand_room(worker, station_id)

    size_after, caps_after = await _read_station_and_caps(station_ctx)
    assert grown.size == starting_size + 3
    assert size_after == starting_size + 3
    assert caps_after == starting_caps - 600


@pytest.mark.asyncio
async def test_lock_key_format_matches_production_helper(station_ctx: dict) -> None:
    """The literal key the tests contend on must equal the production helper's key."""
    from app.services.room_assignment_policy import response_station_lock_key

    assert response_station_lock_key(station_ctx["station_id"]) == _station_lock_key(station_ctx["station_id"])


# ---------------------------------------------------------------------------
# Manual assignment: the last free slot goes to exactly one request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_assignment_to_last_slot_admits_only_one(station_ctx: dict) -> None:
    """Two assignments racing for the last slot: the lock admits one and refuses the other."""
    station_id = station_ctx["station_id"]
    dweller_ids = station_ctx["dweller_ids"]

    async with station_ctx["maker"]() as s:
        await dweller_service.move_to_room(s, dweller_ids[0], station_id)
    assert await _occupants(station_ctx) == 1

    async with (
        station_ctx["maker"]() as holder,
        station_ctx["maker"]() as contender,
    ):
        assert await db_locks.try_advisory_xact_lock(holder, _station_lock_key(station_id))
        with pytest.raises(ResourceConflictException):
            await dweller_service.move_to_room(contender, dweller_ids[1], station_id)
        await holder.rollback()

    assert await _occupants(station_ctx) == 1

    async with station_ctx["maker"]() as worker:
        await dweller_service.move_to_room(worker, dweller_ids[1], station_id)
    assert await _occupants(station_ctx) == 2


@pytest.mark.asyncio
async def test_two_concurrent_assignments_overfill_nothing(station_ctx: dict) -> None:
    """Real two-request race on the last slot: exactly one succeeds and occupancy stays within capacity."""
    station_id = station_ctx["station_id"]
    dweller_ids = station_ctx["dweller_ids"]

    async with station_ctx["maker"]() as s:
        await dweller_service.move_to_room(s, dweller_ids[0], station_id)
    assert await _occupants(station_ctx) == 1

    async def assign(dweller_id) -> object:
        async with station_ctx["maker"]() as session:
            return await dweller_service.move_to_room(session, dweller_id, station_id)

    results = await asyncio.gather(assign(dweller_ids[1]), assign(dweller_ids[2]), return_exceptions=True)
    successes = [r for r in results if not isinstance(r, BaseException)]
    conflicts = [r for r in results if isinstance(r, ResourceConflictException)]

    station_size, _ = await _read_station_and_caps(station_ctx)
    occupants = await _occupants(station_ctx)

    assert len(successes) == 1, results
    assert len(conflicts) == 1, results
    assert occupants == station_size // 3 * 2 == 2


# ---------------------------------------------------------------------------
# Automatic return pass: same lock, same guarantee
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_return_pass_cannot_overfill_the_last_station_slot(station_ctx: dict) -> None:
    """A return that races a concurrent assignment defers instead of overfilling the station."""
    vault_id = station_ctx["vault_id"]
    station_id = station_ctx["station_id"]
    incident_room_id = station_ctx["incident_room_id"]
    occupant_id, responder_id = station_ctx["dweller_ids"][0], station_ctx["dweller_ids"][1]

    async with station_ctx["maker"]() as s:
        await dweller_service.move_to_room(s, occupant_id, station_id)

    async with station_ctx["maker"]() as s:
        incident = await crud.incident_crud.create(
            s, vault_id=vault_id, room_id=incident_room_id, incident_type=IncidentType.FIRE, difficulty=2
        )
        await dweller_service.move_to_room(s, responder_id, incident_room_id)
        members = await crud.team_crud.add_incident_team_members(
            s, incident.id, vault_id, [responder_id], status=DISPATCHED_STATUS
        )
        for member in members:
            member.origin_room_id = station_id
            s.add(member)
        await s.commit()
        incident_id = incident.id

    # Hold the station lock as a concurrent assignment would; the return pass must defer.
    async with station_ctx["maker"]() as holder, station_ctx["maker"]() as worker:
        assert await db_locks.try_advisory_xact_lock(holder, _station_lock_key(station_id))
        loaded = await crud.incident_crud.get(worker, incident_id)
        returned = await hazard_team_service.return_dispatched_responders(worker, loaded)
        members = await crud.team_crud.get_incident_team(worker, incident_id, vault_id)
        assert returned == 0
        assert all(member.status == DISPATCHED_STATUS for member in members)
        assert await crud.dweller.count_in_room(worker, station_id) == 1
        await holder.rollback()

    # Released: the posting is restored on the next pass.
    async with station_ctx["maker"]() as worker:
        loaded = await crud.incident_crud.get(worker, incident_id)
        returned = await hazard_team_service.return_dispatched_responders(worker, loaded)

    assert returned == 1
    assert await _occupants(station_ctx) == 2
