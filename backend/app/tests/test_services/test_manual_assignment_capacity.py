"""Manual assignment must respect room worker capacity (issue #990).

The automatic assignment path counts worker slots through
``calculate_room_capacity`` (2 dwellers per 3 size units), but the manual
``dweller_service.move_to_room`` path persists the move without checking
capacity — so a full room accepts one more dweller, and two concurrent moves
can both take the last slot. These tests pin the gap through the real
assignment path before the service changes.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.dweller_assignment_service import dweller_assignment_service
from app.services.dweller_service import dweller_service
from app.services.room_assignment_policy import calculate_room_capacity
from app.tests.factory.vaults import random_vault_number
from app.utils.exceptions import ResourceConflictException, ValidationException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _production_room_create(
    vault_id: UUID, *, name: str, x: int, ability: SPECIALEnum = SPECIALEnum.STRENGTH
) -> RoomCreate:
    """A size-3 production room payload: 2 adult worker slots plus one apprentice slot."""
    return RoomCreate(
        vault_id=vault_id,
        name=name,
        category=RoomTypeEnum.PRODUCTION,
        ability=ability,
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
        capacity_formula=None,
        output_formula=None,
    )


async def _create_room(session: AsyncSession, vault_id: UUID, *, name: str, x: int) -> Room:
    return await crud.room.create(session, obj_in=_production_room_create(vault_id, name=name, x=x))


def _dweller_create(vault_id: UUID, surname: str, age_group: AgeGroupEnum) -> DwellerCreate:
    return DwellerCreate(
        vault_id=vault_id,
        first_name="Occupant",
        last_name=surname,
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        age_group=age_group,
        level=1,
        experience=0,
        max_health=100,
        health=100,
        radiation=0,
        happiness=50,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
    )


async def _create_adult(session: AsyncSession, vault_id: UUID, surname: str) -> Dweller:
    return await crud.dweller.create(session, obj_in=_dweller_create(vault_id, surname, AgeGroupEnum.ADULT))


async def _create_youth(session: AsyncSession, vault_id: UUID, surname: str) -> Dweller:
    return await crud.dweller.create(session, obj_in=_dweller_create(vault_id, surname, AgeGroupEnum.CHILD))


async def _occupants(session: AsyncSession, room: Room) -> int:
    return await crud.dweller.count_in_room(session, room.id)


# ---------------------------------------------------------------------------
# The gap: manual moves ignore worker capacity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_production_room_rejects_manual_move(async_session: AsyncSession, vault: Vault) -> None:
    """A size-3 production room holds 2 workers; the 3rd manual move is rejected."""
    room = await _create_room(async_session, vault.id, name="Power Generator", x=10)
    assert calculate_room_capacity(room.size) == 2

    first = await _create_adult(async_session, vault.id, "First")
    second = await _create_adult(async_session, vault.id, "Second")
    third = await _create_adult(async_session, vault.id, "Third")

    await dweller_service.move_to_room(async_session, first.id, room.id)
    await dweller_service.move_to_room(async_session, second.id, room.id)
    assert await _occupants(async_session, room) == 2

    with pytest.raises(ResourceConflictException, match="full capacity"):
        await dweller_service.move_to_room(async_session, third.id, room.id)

    assert await _occupants(async_session, room) == 2


@pytest.mark.asyncio
async def test_moving_between_rooms_frees_and_uses_slots(async_session: AsyncSession, vault: Vault) -> None:
    """A dweller leaving a full room frees its slot; the freed slot admits a newcomer."""
    full_room = await _create_room(async_session, vault.id, name="Power Generator", x=10)
    spare_room = await _create_room(async_session, vault.id, name="Water Treatment", x=13)

    first = await _create_adult(async_session, vault.id, "First")
    second = await _create_adult(async_session, vault.id, "Second")
    await dweller_service.move_to_room(async_session, first.id, full_room.id)
    await dweller_service.move_to_room(async_session, second.id, full_room.id)

    await dweller_service.move_to_room(async_session, first.id, spare_room.id)
    assert await _occupants(async_session, full_room) == 1

    third = await _create_adult(async_session, vault.id, "Third")
    await dweller_service.move_to_room(async_session, third.id, full_room.id)
    assert await _occupants(async_session, full_room) == 2


@pytest.mark.asyncio
async def test_junior_slot_sits_outside_full_worker_capacity(async_session: AsyncSession, vault: Vault) -> None:
    """A youth joins a worker-full production room as apprentice; a second youth is refused."""
    room = await _create_room(async_session, vault.id, name="Power Generator", x=10)

    first = await _create_adult(async_session, vault.id, "First")
    second = await _create_adult(async_session, vault.id, "Second")
    await dweller_service.move_to_room(async_session, first.id, room.id)
    await dweller_service.move_to_room(async_session, second.id, room.id)

    youth = await _create_youth(async_session, vault.id, "Junior")
    await dweller_service.move_to_room(async_session, youth.id, room.id)
    placed = await crud.dweller.get(async_session, youth.id)
    assert placed.apprentice_stat == SPECIALEnum.STRENGTH

    extra_youth = await _create_youth(async_session, vault.id, "Extra")
    with pytest.raises(ValidationException, match="already has an apprentice"):
        await dweller_service.move_to_room(async_session, extra_youth.id, room.id)


@pytest.mark.asyncio
async def test_bulk_assignment_does_not_overfill_a_stale_slot(async_session: AsyncSession, vault: Vault) -> None:
    """Bulk auto-assign re-checks capacity at persist time.

    The slot count is computed up front; a room that filled after selection
    must not be overfilled by the persist pass — the leftover dweller stays
    unassigned even if the caller selected the room from an earlier snapshot.
    """
    room = await _create_room(async_session, vault.id, name="Power Generator", x=10)

    first = await _create_adult(async_session, vault.id, "First")
    second = await _create_adult(async_session, vault.id, "Second")
    await dweller_service.move_to_room(async_session, first.id, room.id)
    await dweller_service.move_to_room(async_session, second.id, room.id)
    leftover = await _create_adult(async_session, vault.id, "Leftover")

    result = await dweller_assignment_service._persist_room_assignment(async_session, leftover.id, room)

    assert await _occupants(async_session, room) == 2
    assert result is False
    assert (await crud.dweller.get(async_session, leftover.id)).room_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("category", [RoomTypeEnum.PRODUCTION, RoomTypeEnum.TRAINING])
async def test_bulk_retries_candidate_in_next_room_when_first_is_busy(
    async_session: AsyncSession, vault: Vault, category: RoomTypeEnum
) -> None:
    rooms = [
        await crud.room.create(
            async_session,
            obj_in=_production_room_create(vault.id, name=f"Room {x}", x=x).model_copy(update={"category": category}),
        )
        for x in (10, 13)
    ]
    candidate = await _create_adult(async_session, vault.id, "Retry")
    assignments: list[dict[str, str]] = []
    with patch(
        "app.services.room_assignment_policy.db_locks.try_advisory_xact_lock",
        new=AsyncMock(side_effect=[False, True]),
    ):
        remaining = await dweller_assignment_service._assign_ability_dwellers(
            SPECIALEnum.STRENGTH, rooms, async_session, [candidate], assignments, set(), 1
        )

    await async_session.refresh(candidate)
    assert candidate.room_id == rooms[1].id
    assert remaining == []
    assert len(assignments) == 1
    assert assignments[0]["room_id"] == str(rooms[1].id)


# ---------------------------------------------------------------------------
# Live-PostgreSQL race: the last free worker slot goes to exactly one request
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def live_pg_engine() -> AsyncIterator[AsyncEngine]:
    """Connect to the live PostgreSQL database, skipping when unavailable."""
    uri = str(settings.ASYNC_DATABASE_URI)
    if make_url(uri).get_backend_name() != "postgresql":
        pytest.skip("ASYNC_DATABASE_URI is not PostgreSQL; skipping the capacity race check")

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
async def production_ctx(live_pg_engine: AsyncEngine) -> AsyncIterator[dict]:
    """One vault with a size-3 production room and adult dwellers, removed afterwards."""
    maker = async_sessionmaker(live_pg_engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid4().hex[:8]

    async with maker() as session:
        user = await crud.user.create(
            session,
            obj_in=UserCreate(
                username=f"capacity-{suffix}", email=f"capacity-{suffix}@example.com", password="secret-password-123"
            ),
        )
        vault = await crud.vault.create(
            session,
            obj_in=VaultCreateWithUserID(
                number=random_vault_number(),
                bottle_caps=100_000,
                population_max=200,
                user_id=user.id,
            ),
        )
        room = await crud.room.create(session, obj_in=_production_room_create(vault.id, name="Power Generator", x=10))
        dwellers = [
            await crud.dweller.create(session, obj_in=_dweller_create(vault.id, f"Racer{i}", AgeGroupEnum.ADULT))
            for i in range(3)
        ]
        ids = {
            "maker": maker,
            "vault_id": vault.id,
            "room_id": room.id,
            "dweller_ids": [dweller.id for dweller in dwellers],
            "user_id": user.id,
        }

    try:
        yield ids
    finally:
        async with maker() as session:
            for statement in (
                "DELETE FROM notification WHERE vault_id = :vault_id",
                "DELETE FROM room WHERE vault_id = :vault_id",
                "DELETE FROM dweller WHERE vault_id = :vault_id",
                "DELETE FROM vault WHERE id = :vault_id",
            ):
                await session.execute(text(statement), {"vault_id": ids["vault_id"]})
            await session.execute(text('DELETE FROM "user" WHERE id = :user_id'), {"user_id": ids["user_id"]})
            await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_two_concurrent_production_moves_admit_only_one(production_ctx: dict) -> None:
    """Real two-request race on the last worker slot: one succeeds, one conflicts."""
    room_id = production_ctx["room_id"]
    dweller_ids = production_ctx["dweller_ids"]

    async with production_ctx["maker"]() as session:
        await dweller_service.move_to_room(session, dweller_ids[0], room_id)

    async def assign(dweller_id) -> object:
        async with production_ctx["maker"]() as session:
            return await dweller_service.move_to_room(session, dweller_id, room_id)

    results = await asyncio.gather(assign(dweller_ids[1]), assign(dweller_ids[2]), return_exceptions=True)
    successes = [r for r in results if not isinstance(r, BaseException)]
    conflicts = [r for r in results if isinstance(r, ResourceConflictException)]

    async with production_ctx["maker"]() as reader:
        occupants = await crud.dweller.count_in_room(reader, room_id)

    assert len(successes) == 1, results
    assert len(conflicts) == 1, results
    assert occupants == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_and_manual_race_for_last_slot(production_ctx: dict) -> None:
    """Bulk auto-assign racing a manual move for the last worker slot: exactly one wins."""
    maker = production_ctx["maker"]
    vault_id = production_ctx["vault_id"]
    room_id = production_ctx["room_id"]
    prefill_id, bulk_id, manual_id = production_ctx["dweller_ids"]

    async with maker() as session:
        spare = await crud.room.create(
            session,
            obj_in=RoomCreate(
                vault_id=vault_id,
                name="Athletics Room",
                category=RoomTypeEnum.TRAINING,
                ability=SPECIALEnum.INTELLIGENCE,
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
                coordinate_x=16,
                coordinate_y=1,
                image_url=None,
                capacity_formula=None,
                output_formula=None,
            ),
        )
        # Prefill one of the two target slots; park the manual mover in the
        # training room so the bulk production flow cannot take it itself.
        await dweller_service.move_to_room(session, prefill_id, room_id)
        await dweller_service.move_to_room(session, manual_id, spare.id)

    async def manual() -> object:
        async with maker() as session:
            return await dweller_service.move_to_room(session, manual_id, room_id)

    async def bulk() -> object:
        async with maker() as session:
            return await dweller_assignment_service.auto_assign_production_rooms(session, vault_id)

    manual_res, bulk_res = await asyncio.gather(manual(), bulk(), return_exceptions=True)
    manual_ok = not isinstance(manual_res, BaseException)
    bulk_took_target = isinstance(bulk_res, dict) and any(
        entry["room_id"] == str(room_id) for entry in bulk_res["assignments"]
    )

    async with maker() as reader:
        occupants = await crud.dweller.count_in_room(reader, room_id)

    assert manual_ok ^ bulk_took_target
    if not manual_ok:
        assert isinstance(manual_res, ResourceConflictException)
    assert occupants == 2
