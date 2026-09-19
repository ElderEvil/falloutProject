"""Live-PostgreSQL concurrency checks for the earned hazard roster.

A place is read-then-insert, so two overlapping rounds could both pass the read and then
collide on ``uq_team_vault_hazard`` / ``uq_team_member_slot``. The mutation is guarded by a
transaction-scoped lock, which SQLite cannot demonstrate because it serializes writers.
"""

import uuid
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import crud
from app.core import db_locks
from app.core.config import settings
from app.core.enums import HazardTeam
from app.models.incident import IncidentType
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.hazard_team_service import QUALIFYING_INCIDENTS, hazard_team_service, roster_lock_key
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.vaults import random_vault_number

pytestmark = pytest.mark.integration

_ROUNDS = QUALIFYING_INCIDENTS + 1


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncIterator[AsyncEngine]:
    """Connect to the live PostgreSQL database, skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping the roster concurrency check")

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
async def roster(live_pg_engine: AsyncEngine, dweller_data: dict) -> AsyncIterator[dict]:
    """One vault, room, dweller and the incidents needed to earn a place, removed afterwards."""
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid4().hex[:8]

    async with maker() as session:
        user = await crud.user.create(
            session,
            obj_in=UserCreate(
                username=f"conc-{suffix}", email=f"conc-{suffix}@example.com", password="secret-password-123"
            ),
        )
        vault = await crud.vault.create(
            session,
            obj_in=VaultCreateWithUserID(
                number=random_vault_number(),
                bottle_caps=100,
                happiness=50,
                power=50,
                food=50,
                water=50,
                population_max=50,
                user_id=user.id,
            ),
        )
        room = await crud.room.create(session, RoomCreate(**create_fake_room(), vault_id=vault.id))
        dweller = await crud.dweller.create(
            session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id, room_id=room.id)
        )
        incidents = [
            await crud.incident_crud.create(
                session, vault_id=vault.id, room_id=room.id, incident_type=IncidentType.FIRE, difficulty=2
            )
            for _ in range(_ROUNDS)
        ]
        ids = {
            "maker": maker,
            "vault_id": vault.id,
            "dweller_id": dweller.id,
            "incident_ids": [incident.id for incident in incidents],
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
                "DELETE FROM team WHERE vault_id = :vault_id",
                "DELETE FROM room WHERE vault_id = :vault_id",
                "DELETE FROM dweller WHERE vault_id = :vault_id",
                "DELETE FROM vault WHERE id = :vault_id",
            ):
                await session.execute(text(statement), {"vault_id": ids["vault_id"]})
            await session.execute(text('DELETE FROM "user" WHERE id = :user_id'), {"user_id": ids["user_id"]})
            await session.commit()


async def _fight_for_place(maker: async_sessionmaker, vault_id, incident_id, dweller_id) -> list:
    """One hazard round for the dweller; returns the places it earned."""
    async with maker() as session:
        incident = await crud.incident_crud.get(session, incident_id)
        dweller = await crud.dweller.get(session, dweller_id)
        result = await hazard_team_service.record_participation(session, incident, [dweller])
        await session.commit()
        return result.new_places


@pytest.mark.asyncio
async def test_contended_roster_defers_the_place_instead_of_colliding(roster: dict) -> None:
    """A round that cannot take the roster lock defers the place; the roster stays consistent."""
    maker, vault_id = roster["maker"], roster["vault_id"]
    dweller_id = roster["dweller_id"]
    incidents = roster["incident_ids"]

    # Earn credits up to one short of qualifying, so the contended round is the qualifying one.
    for incident_id in incidents[: QUALIFYING_INCIDENTS - 1]:
        assert await _fight_for_place(maker, vault_id, incident_id, dweller_id) == []

    # One transaction holds the roster lock for the whole of another round's attempt.
    async with maker() as holder, maker() as other:
        assert await db_locks.try_advisory_xact_lock(holder, roster_lock_key(vault_id, HazardTeam.FIRE))

        incident = await crud.incident_crud.get(other, incidents[QUALIFYING_INCIDENTS - 1])
        dweller = await crud.dweller.get(other, dweller_id)
        result = await hazard_team_service.record_participation(other, incident, [dweller])
        await other.commit()

        # Qualified, but the place is deferred rather than colliding on the unique constraints.
        assert result.new_places == []
        await holder.rollback()

    async with maker() as session:
        team_rows = (
            await session.execute(text("SELECT count(*) FROM team WHERE vault_id = :vault_id"), {"vault_id": vault_id})
        ).scalar()
        member_rows = (
            await session.execute(
                text(
                    "SELECT count(*) FROM team_member tm JOIN team t ON t.id = tm.team_id "
                    "WHERE t.vault_id = :vault_id AND tm.dweller_id = :dweller_id"
                ),
                {"vault_id": vault_id, "dweller_id": dweller_id},
            )
        ).scalar()
        assert (team_rows, member_rows) == (0, 0)

    # The next round takes the lock, so the dweller joins cleanly.
    places = await _fight_for_place(maker, vault_id, incidents[QUALIFYING_INCIDENTS], dweller_id)

    assert len(places) == 1
    assert places[0].status == "active"
    assert places[0].slot_number == 1

    async with maker() as session:
        assert (
            await session.execute(text("SELECT count(*) FROM team WHERE vault_id = :vault_id"), {"vault_id": vault_id})
        ).scalar() == 1
        assert (
            await session.execute(
                text(
                    "SELECT count(*) FROM team_member tm JOIN team t ON t.id = tm.team_id "
                    "WHERE t.vault_id = :vault_id AND tm.dweller_id = :dweller_id"
                ),
                {"vault_id": vault_id, "dweller_id": dweller_id},
            )
        ).scalar() == 1
