"""Live-PostgreSQL concurrency checks for incident responder assignment.

Skips without a reachable PostgreSQL database: SQLite serializes every
write, so it cannot prove row locking. Each test writes its own user,
vault, room, incident, and dweller rows and removes them afterwards.
"""

import asyncio
import random
import uuid

import pytest
import pytest_asyncio
from pydantic import UUID4
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.enums import GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.models.incident import Incident, IncidentType
from app.models.room import Room
from app.models.user import User
from app.models.vault import Vault
from app.services.combat.incident_service import incident_service

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncEngine:
    """Connect to the live PostgreSQL database, skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping incident responder concurrency check")

    engine = create_async_engine(uri, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text

            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def incident_context(live_pg_engine: AsyncEngine) -> tuple[UUID4, UUID4, UUID4, list[UUID4]]:
    """An active incident with eight healthy adult dwellers, removed on teardown."""
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    tag = uuid.uuid4().hex[:12]
    async with maker() as session:
        user = User(username=f"incident_{tag}", email=f"incident_{tag}@vault.test", hashed_password="x")
        session.add(user)
        await session.flush()
        vault = Vault(number=random.randint(700, 999), user_id=user.id)
        session.add(vault)
        await session.flush()
        room = Room(
            name="Power Generator",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=3,
            size_max=6,
            coordinate_x=1,
            coordinate_y=1,
            vault_id=vault.id,
        )
        session.add(room)
        await session.flush()
        incident = Incident(vault_id=vault.id, room_id=room.id, type=IncidentType.FIRE, difficulty=1)
        session.add(incident)
        await session.flush()
        dwellers = [
            Dweller(
                first_name=f"Responder{i}",
                last_name="Test",
                gender=GenderEnum.MALE,
                rarity=RarityEnum.COMMON,
                vault_id=vault.id,
                max_health=100,
                health=100,
                radiation=0,
            )
            for i in range(8)
        ]
        session.add_all(dwellers)
        await session.commit()
        ids = (incident.id, vault.id, user.id, [dweller.id for dweller in dwellers])
    yield ids
    async with maker() as session:
        await session.execute(delete(Dweller).where(Dweller.vault_id == ids[1]))
        await session.execute(delete(Incident).where(Incident.id == ids[0]))
        await session.execute(delete(Room).where(Room.vault_id == ids[1]))
        await session.execute(delete(Vault).where(Vault.id == ids[1]))
        await session.execute(delete(User).where(User.id == ids[2]))
        await session.commit()


def _sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_assign_responders_blocks_on_incident_row_lock(
    live_pg_engine: AsyncEngine, incident_context: tuple[UUID4, UUID4, UUID4, list[UUID4]]
) -> None:
    """A concurrent assignment blocks on the incident row lock, then lands once it is released.

    ``assign_responders`` re-loads the incident ``FOR UPDATE`` before reading the
    roster and checking the cap. Holding that lock from another transaction must
    therefore block a second assignment (proving the read→check→insert is
    serialized) until the holder commits.
    """
    incident_id, vault_id, _user_id, dweller_ids = incident_context
    maker = _sessions(live_pg_engine)

    async with maker() as holder, maker() as actor:
        async with holder.begin():
            held = await holder.execute(select(Incident).where(Incident.id == incident_id).with_for_update())
            assert held.scalar_one_or_none() is not None

            async def assign() -> list[UUID4]:
                incident = await actor.get(Incident, incident_id)
                assert incident is not None
                return await incident_service.assign_responders(actor, incident, dweller_ids[:4])

            task = asyncio.create_task(assign())
            await asyncio.sleep(0.5)
            assert not task.done(), "assignment did not block on the incident row lock"

        assigned = await asyncio.wait_for(task, timeout=10)

    assert len(assigned) == 4

    from app.crud.team import team_crud

    async with maker() as check:
        members = await team_crud.get_incident_team(check, incident_id, vault_id)
        assert len(members) == 4
