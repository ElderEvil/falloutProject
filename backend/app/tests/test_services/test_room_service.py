"""Tests for RoomService merge behavior and the adjacent-room backfill."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.training import Training
from app.models.vault import Vault
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.room_assignment_policy import calculate_room_capacity
from app.services.room_service import room_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, UniqueRoomViolationException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_room_create(
    vault_id: UUID,
    *,
    name: str = "Power Generator",
    coordinate_x: int = 0,
    coordinate_y: int = 1,
    size: int = 3,
    size_min: int = 3,
    size_max: int = 9,
    tier: int = 1,
    capacity_formula: str | None = "10*S",
    output_formula: str | None = "5*S",
) -> RoomCreate:
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
        size_min=size_min,
        size_max=size_max,
        size=size,
        tier=tier,
        coordinate_x=coordinate_x,
        coordinate_y=coordinate_y,
        image_url=None,
        speedup_multiplier=1.0,
        capacity_formula=capacity_formula,
        output_formula=output_formula,
    )


async def _create_elevator(session: AsyncSession, vault_id: UUID, coordinate_y: int, *, coordinate_x: int = 6) -> Room:
    return await crud.room.create(
        session,
        obj_in=RoomCreate(
            vault_id=vault_id,
            name="Elevator",
            category=RoomTypeEnum.MISC,
            ability=None,
            population_required=None,
            base_cost=100,
            incremental_cost=None,
            t2_upgrade_cost=None,
            t3_upgrade_cost=None,
            capacity=None,
            output=None,
            size_min=1,
            size_max=1,
            size=1,
            tier=1,
            coordinate_x=coordinate_x,
            coordinate_y=coordinate_y,
            image_url=None,
            speedup_multiplier=1.0,
        ),
    )


async def _create_existing_room(
    session: AsyncSession,
    vault_id: UUID,
    *,
    name: str = "Power Generator",
    coordinate_x: int,
    coordinate_y: int = 1,
    size: int = 3,
    size_max: int = 9,
    tier: int = 1,
    capacity_formula: str | None = "10*S",
    output_formula: str | None = "5*S",
    image_url: str | None = None,
) -> Room:
    return await crud.room.create(
        session,
        obj_in=RoomCreate(
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
            size_max=size_max,
            size=size,
            tier=tier,
            coordinate_x=coordinate_x,
            coordinate_y=coordinate_y,
            image_url=image_url,
            speedup_multiplier=1.0,
            capacity_formula=capacity_formula,
            output_formula=output_formula,
        ),
    )


async def _create_dweller_in_room(session: AsyncSession, vault_id: UUID, room: Room) -> Dweller:
    dweller_in = DwellerCreate(
        vault_id=vault_id,
        first_name="Test",
        last_name="Dweller",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        age_group=AgeGroupEnum.ADULT,
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
    dweller = await crud.dweller.create(session, obj_in=dweller_in)
    dweller.room_id = room.id
    session.add(dweller)
    await session.commit()
    await session.refresh(dweller)
    return dweller


@pytest.fixture
async def rich_vault(vault: Vault, async_session: AsyncSession) -> Vault:
    """Vault with enough caps to pay for any test build."""
    vault.bottle_caps = 1_000_000
    async_session.add(vault)
    await async_session.commit()
    await async_session.refresh(vault)
    return vault


@pytest.fixture(autouse=True)
def _stub_room_template():
    """Use the formulas provided in test RoomCreate payloads, not the static store."""
    with patch("app.services.room_service.game_data_store.get_room", return_value=None):
        yield


# ---------------------------------------------------------------------------
# _build merge scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_merges_adjacent_room_on_right(async_session: AsyncSession, rich_vault: Vault):
    """Building at x=3 next to an existing x=0 room merges into the leftmost room."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    existing = await _create_existing_room(
        async_session,
        rich_vault.id,
        name="Power Generator",
        coordinate_x=0,
        coordinate_y=1,
        size=3,
        tier=2,
    )

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result, created = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Power Generator",
                coordinate_x=3,
                coordinate_y=1,
                tier=2,
            ),
        )

    assert result.id == existing.id
    assert created is False
    assert result.coordinate_x == 0
    assert result.size == 6
    assert result.capacity == 60
    assert result.output == 30


@pytest.mark.asyncio
async def test_build_merges_adjacent_room_on_left(async_session: AsyncSession, rich_vault: Vault):
    """Building at x=0 next to an existing x=3 room keeps the merged room at x=0."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    existing = await _create_existing_room(
        async_session,
        rich_vault.id,
        name="Power Generator",
        coordinate_x=3,
        coordinate_y=1,
        size=3,
        tier=2,
    )

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result, created = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Power Generator",
                coordinate_x=0,
                coordinate_y=1,
                tier=2,
            ),
        )

    assert result.id != existing.id
    assert created is True
    assert result.coordinate_x == 0
    assert result.size == 6
    remaining = await crud.room.get_all_by_vault(async_session, rich_vault.id)
    assert existing.id not in {room.id for room in remaining}


@pytest.mark.asyncio
async def test_build_three_way_merge_to_size_max(async_session: AsyncSession, rich_vault: Vault):
    """Building between two identical neighbours merges all three when the sum fits size_max."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    left = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0, size=3)
    right = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=6, size=3)

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result, created = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Power Generator",
                coordinate_x=3,
                coordinate_y=1,
            ),
        )

    assert result.id == left.id
    assert created is False
    assert result.size == 9
    assert result.coordinate_x == 0
    remaining = await crud.room.get_all_by_vault(async_session, rich_vault.id)
    remaining_ids = {room.id for room in remaining}
    assert left.id in remaining_ids
    assert right.id not in remaining_ids


@pytest.mark.asyncio
async def test_build_no_merge_different_tier(async_session: AsyncSession, rich_vault: Vault):
    """Adjacent rooms of different tiers do not merge."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    existing = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0, tier=1)

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result, created = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Power Generator",
                coordinate_x=3,
                coordinate_y=1,
                tier=2,
            ),
        )

    assert created is True
    assert result.id != existing.id
    assert result.size == 3


@pytest.mark.asyncio
async def test_build_no_merge_different_name(async_session: AsyncSession, rich_vault: Vault):
    """Adjacent rooms of different names do not merge."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    existing = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result, created = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Diner",
                coordinate_x=3,
                coordinate_y=1,
            ),
        )

    assert created is True
    assert result.id != existing.id
    assert result.name == "Diner"


@pytest.mark.asyncio
async def test_build_no_merge_exceeds_size_max(async_session: AsyncSession, rich_vault: Vault):
    """When the combined footprint exceeds size_max a second room is created."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    existing = await _create_existing_room(
        async_session, rich_vault.id, name="Power Generator", coordinate_x=0, size=3, size_max=3
    )

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result, created = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Power Generator",
                coordinate_x=3,
                coordinate_y=1,
                size_max=3,
            ),
        )

    assert created is True
    assert result.id != existing.id
    assert result.size == 3


@pytest.mark.asyncio
async def test_build_same_coordinate_same_name_expands(async_session: AsyncSession, rich_vault: Vault):
    """Building at the same coordinate as an identical room still expands it."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    existing = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0, size=3)

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result, created = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Power Generator",
                coordinate_x=0,
                coordinate_y=1,
            ),
        )

    assert result.id == existing.id
    assert created is False
    assert result.size == 6


@pytest.mark.asyncio
async def test_build_merge_reassigns_dwellers(async_session: AsyncSession, rich_vault: Vault):
    """Dwellers in absorbed rooms are reassigned to the surviving room."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    existing = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)
    await _create_dweller_in_room(async_session, rich_vault.id, existing)

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result, _created = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Power Generator",
                coordinate_x=3,
                coordinate_y=1,
            ),
        )

    dwellers = await crud.dweller.get_by_room(async_session, result.id)
    assert len(dwellers) == 1
    assert dwellers[0].room_id == result.id


@pytest.mark.asyncio
async def test_build_merge_charges_price(async_session: AsyncSession, rich_vault: Vault):
    """The vault is charged the normal build price for the added segment."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)
    caps_before = rich_vault.bottle_caps

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Power Generator",
                coordinate_x=3,
                coordinate_y=1,
            ),
        )

    await async_session.refresh(rich_vault)
    assert rich_vault.bottle_caps < caps_before


@pytest.mark.asyncio
async def test_build_merge_recomputes_image_url(async_session: AsyncSession, rich_vault: Vault):
    """The survivor image_url is recomputed for the new size."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    existing = await _create_existing_room(
        async_session, rich_vault.id, name="Power Generator", coordinate_x=0, image_url=None
    )
    existing.image_url = "/static/old.png"
    async_session.add(existing)
    await async_session.commit()

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result, _created = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(
                rich_vault.id,
                name="Power Generator",
                coordinate_x=3,
                coordinate_y=1,
            ),
        )

    assert result.image_url != "/static/old.png"


# ---------------------------------------------------------------------------
# Backfill merge-rooms
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_merge_rooms_dry_run_reports_without_writing(async_session: AsyncSession, rich_vault: Vault):
    """Dry run reports merges but leaves the database unchanged."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=3)
    rooms_before = len(await crud.room.get_all_by_vault(async_session, rich_vault.id))

    summary = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=True)

    assert summary["merged"] == 1
    rooms_after = len(await crud.room.get_all_by_vault(async_session, rich_vault.id))
    assert rooms_after == rooms_before


@pytest.mark.asyncio
async def test_backfill_merge_rooms_apply_merges(async_session: AsyncSession, rich_vault: Vault):
    """Apply mode actually merges adjacent duplicate rooms."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    left = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)
    right = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=3)

    summary = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)

    assert summary["merged"] == 1
    survivor = await crud.room.get(async_session, left.id)
    assert survivor.size == 6
    with pytest.raises(ResourceNotFoundException):
        await crud.room.get(async_session, right.id)


@pytest.mark.asyncio
async def test_backfill_merge_rooms_idempotent(async_session: AsyncSession, rich_vault: Vault):
    """A second apply pass makes no further changes."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=3)

    first = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)
    second = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)

    assert first["merged"] == 1
    assert second["merged"] == 0


@pytest.mark.asyncio
async def test_backfill_skips_unplaced_rooms_without_sort_crash(async_session: AsyncSession, rich_vault: Vault):
    """Unplaced (NULL-coordinate) rooms must not crash the backfill sort."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=3)
    await _create_existing_room(async_session, rich_vault.id, name="Storage", coordinate_x=None, coordinate_y=None)

    summary = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=True)

    assert summary["merged"] == 1


@pytest.mark.asyncio
async def test_backfill_dry_run_matches_apply_for_chain(async_session: AsyncSession, rich_vault: Vault):
    """Dry-run reports the same merge count as apply for a three-room chain."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    for coordinate_x in (0, 3, 6):
        await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=coordinate_x)

    dry = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=True)
    applied = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)

    assert dry["merged"] == applied["merged"] == 2


@pytest.mark.asyncio
async def test_build_merge_reassigns_training(async_session: AsyncSession, rich_vault: Vault):
    """Training sessions of absorbed rooms move to the surviving room before deletion."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    absorbed = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=3)
    dweller = await _create_dweller_in_room(async_session, rich_vault.id, absorbed)
    training = Training(
        vault_id=rich_vault.id,
        dweller_id=dweller.id,
        room_id=absorbed.id,
        stat_being_trained=SPECIALEnum.STRENGTH,
        current_stat_value=5,
        target_stat_value=6,
        started_at=datetime.utcnow(),
        estimated_completion_at=datetime.utcnow(),
    )
    async_session.add(training)
    await async_session.commit()

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        survivor, _ = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(rich_vault.id, name="Power Generator", coordinate_x=0, tier=1),
        )

    await async_session.refresh(training)
    assert survivor.size == 6
    assert training.room_id == survivor.id


@pytest.mark.asyncio
async def test_build_merge_moves_absorbed_dwellers_to_survivor(async_session: AsyncSession, rich_vault: Vault):
    """Dwellers of the absorbed room are moved into the surviving merged room."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    absorbed = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=3)
    dweller = await _create_dweller_in_room(async_session, rich_vault.id, absorbed)

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        survivor, _ = await room_service._build(
            db_session=async_session,
            obj_in=_make_room_create(rich_vault.id, name="Power Generator", coordinate_x=0, tier=1),
        )

    await async_session.refresh(dweller)
    assert dweller.room_id == survivor.id


@pytest.mark.asyncio
async def test_backfill_merge_moves_dwellers_into_survivor(async_session: AsyncSession, rich_vault: Vault):
    """Backfill merges keep dwellers of both rooms in the surviving merged room."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    left = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)
    right = await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=3)
    left_dweller = await _create_dweller_in_room(async_session, rich_vault.id, left)
    right_dweller = await _create_dweller_in_room(async_session, rich_vault.id, right)

    summary = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)

    assert summary["merged"] == 1
    survivor = await crud.room.get(async_session, left.id)
    await async_session.refresh(left_dweller)
    await async_session.refresh(right_dweller)
    assert left_dweller.room_id == survivor.id
    assert right_dweller.room_id == survivor.id


# ---------------------------------------------------------------------------
# _upgrade merge scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upgrade_merges_adjacent_same_tier_room(async_session: AsyncSession, rich_vault: Vault):
    """Upgrading a room to its neighbour's tier fuses them into one survivor."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    survivor = await _create_existing_room(
        async_session,
        rich_vault.id,
        name="Power Generator",
        coordinate_x=0,
        coordinate_y=1,
        size=3,
        tier=2,
    )
    upgraded = await _create_existing_room(
        async_session,
        rich_vault.id,
        name="Power Generator",
        coordinate_x=3,
        coordinate_y=1,
        size=3,
        tier=1,
    )
    dweller = await _create_dweller_in_room(async_session, rich_vault.id, upgraded)

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result = await room_service._upgrade(async_session, upgraded.id)

    assert result.id == survivor.id
    assert result.tier == 2
    assert result.size == 6
    with pytest.raises(ResourceNotFoundException):
        await crud.room.get(async_session, upgraded.id)
    await async_session.refresh(dweller)
    assert dweller.room_id == survivor.id


@pytest.mark.asyncio
async def test_upgrade_no_merge_different_tier(async_session: AsyncSession, rich_vault: Vault):
    """Upgrading past the neighbour's tier still leaves two separate rooms."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    await _create_existing_room(
        async_session,
        rich_vault.id,
        name="Power Generator",
        coordinate_x=0,
        coordinate_y=1,
        size=3,
        tier=3,
    )
    upgraded = await _create_existing_room(
        async_session,
        rich_vault.id,
        name="Power Generator",
        coordinate_x=3,
        coordinate_y=1,
        size=3,
        tier=1,
    )

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        result = await room_service._upgrade(async_session, upgraded.id)

    assert result.id == upgraded.id
    assert result.tier == 2
    assert result.size == 3


# ---------------------------------------------------------------------------
# Response Station — unique room growth via an adjacent segment (issue #997)
# ---------------------------------------------------------------------------


def _make_response_room_create(
    vault_id: UUID, *, coordinate_x: int, coordinate_y: int = 0, size: int = 3
) -> RoomCreate:
    """A Response Station catalog payload: unique (null incremental cost), 3..9 footprint."""
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
        coordinate_x=coordinate_x,
        coordinate_y=coordinate_y,
        image_url=None,
        speedup_multiplier=1.0,
        capacity_formula=None,
        output_formula=None,
    )


async def _create_response_station(
    session: AsyncSession, vault_id: UUID, *, coordinate_x: int = 1, size: int = 3
) -> Room:
    return await crud.room.create(
        session, obj_in=_make_response_room_create(vault_id, coordinate_x=coordinate_x, size=size)
    )


@pytest.mark.asyncio
async def test_adjacent_station_segment_merges_into_one_row(async_session: AsyncSession, rich_vault: Vault):
    """An adjacent segment joins the station (same row id) and grows it 3 -> 6 -> 9."""
    station = await _create_response_station(async_session, rich_vault.id, coordinate_x=1)
    assert calculate_room_capacity(station.size) == 2

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        grown_to_six, created = await room_service._build(
            db_session=async_session,
            obj_in=_make_response_room_create(rich_vault.id, coordinate_x=4),
        )

    assert grown_to_six.id == station.id
    assert created is False
    assert grown_to_six.size == 6
    assert calculate_room_capacity(grown_to_six.size) == 4

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        grown_to_nine, created = await room_service._build(
            db_session=async_session,
            obj_in=_make_response_room_create(rich_vault.id, coordinate_x=7),
        )

    assert grown_to_nine.id == station.id
    assert created is False
    assert grown_to_nine.size == 9
    assert calculate_room_capacity(grown_to_nine.size) == 6

    names = await crud.room.get_names_by_vault(async_session, rich_vault.id)
    assert names.count("Response Station") == 1


@pytest.mark.asyncio
async def test_adjacent_station_segment_charges_one_build_price_per_segment(
    async_session: AsyncSession, rich_vault: Vault
):
    """Each adjacent segment costs one station build price; the row id never changes."""
    await _create_response_station(async_session, rich_vault.id, coordinate_x=1)
    starting_caps = rich_vault.bottle_caps

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        await room_service._build(
            db_session=async_session, obj_in=_make_response_room_create(rich_vault.id, coordinate_x=4)
        )
        await room_service._build(
            db_session=async_session, obj_in=_make_response_room_create(rich_vault.id, coordinate_x=7)
        )

    await async_session.refresh(rich_vault)
    assert rich_vault.bottle_caps == starting_caps - 1200


@pytest.mark.asyncio
async def test_adjacent_station_segment_preserves_dwellers(async_session: AsyncSession, rich_vault: Vault):
    """A merge keeps the station row and its occupants; no second station row appears."""
    station = await _create_response_station(async_session, rich_vault.id, coordinate_x=1)
    dweller = await _create_dweller_in_room(async_session, rich_vault.id, station)

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        grown, _created = await room_service._build(
            db_session=async_session,
            obj_in=_make_response_room_create(rich_vault.id, coordinate_x=4),
        )

    assert grown.id == station.id
    await async_session.refresh(dweller)
    assert dweller.room_id == station.id
    names = await crud.room.get_names_by_vault(async_session, rich_vault.id)
    assert names.count("Response Station") == 1


@pytest.mark.asyncio
async def test_disconnected_second_station_rejected_without_charge(async_session: AsyncSession, rich_vault: Vault):
    """A second station that cannot merge is rejected before any caps move or row is created."""
    await _create_response_station(async_session, rich_vault.id, coordinate_x=1)
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1, coordinate_x=0)
    starting_caps = rich_vault.bottle_caps

    with pytest.raises(UniqueRoomViolationException):
        await room_service._build(
            db_session=async_session,
            obj_in=_make_response_room_create(rich_vault.id, coordinate_x=1, coordinate_y=1),
        )

    await async_session.refresh(rich_vault)
    assert rich_vault.bottle_caps == starting_caps
    names = await crud.room.get_names_by_vault(async_session, rich_vault.id)
    assert names.count("Response Station") == 1


@pytest.mark.asyncio
async def test_adjacent_station_segment_at_size_max_rejected_without_charge(
    async_session: AsyncSession, rich_vault: Vault
):
    """A station already at size_max rejects another adjacent segment and charges nothing."""
    station = await _create_response_station(async_session, rich_vault.id, coordinate_x=1, size=9)
    starting_caps = rich_vault.bottle_caps

    with pytest.raises(UniqueRoomViolationException):
        await room_service._build(
            db_session=async_session,
            obj_in=_make_response_room_create(rich_vault.id, coordinate_x=10),
        )

    await async_session.refresh(rich_vault)
    assert rich_vault.bottle_caps == starting_caps
    await async_session.refresh(station)
    assert station.size == 9
    names = await crud.room.get_names_by_vault(async_session, rich_vault.id)
    assert names.count("Response Station") == 1


@asynccontextmanager
async def _placement_lock_held(*_args, **_kwargs):
    """Stand-in for hold_advisory_lock when another build owns the vault placement lock."""
    yield False


@pytest.mark.asyncio
async def test_build_refused_when_vault_placement_lock_is_held(async_session: AsyncSession, rich_vault: Vault):
    """A concurrent build cannot run while another holds the vault placement lock."""
    starting_caps = rich_vault.bottle_caps

    with (
        patch("app.services.room_service.db_locks.hold_advisory_lock", new=_placement_lock_held),
        pytest.raises(ResourceConflictException),
    ):
        await room_service._build(
            db_session=async_session,
            obj_in=_make_response_room_create(rich_vault.id, coordinate_x=1),
        )

    await async_session.refresh(rich_vault)
    assert rich_vault.bottle_caps == starting_caps


@pytest.mark.asyncio
async def test_upgrade_refused_when_vault_placement_lock_is_held(async_session: AsyncSession, rich_vault: Vault):
    """An upgrade merges under the vault placement lock; a concurrent build's lock refuses it."""
    room = await _create_existing_room(async_session, rich_vault.id, coordinate_x=0, tier=1)

    with (
        patch("app.services.room_service.db_locks.hold_advisory_lock", new=_placement_lock_held),
        pytest.raises(ResourceConflictException),
    ):
        await room_service._upgrade(async_session, room.id)


@pytest.mark.asyncio
async def test_backfill_apply_refused_when_vault_placement_lock_is_held(
    async_session: AsyncSession, rich_vault: Vault
):
    """Apply-mode backfill merges under the vault placement lock; a held lock refuses it."""
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=3)

    with (
        patch("app.services.room_service.db_locks.hold_advisory_lock", new=_placement_lock_held),
        pytest.raises(ResourceConflictException),
    ):
        await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=False)


@pytest.mark.asyncio
async def test_backfill_dry_run_ignores_vault_placement_lock(async_session: AsyncSession, rich_vault: Vault):
    """Dry run is lock-free, so it still reports merges while another holder owns the lock."""
    await _create_elevator(async_session, rich_vault.id, coordinate_y=1)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=0)
    await _create_existing_room(async_session, rich_vault.id, name="Power Generator", coordinate_x=3)

    with patch("app.services.room_service.db_locks.hold_advisory_lock", new=_placement_lock_held):
        summary = await room_service.backfill_merge_rooms_for_vault(async_session, rich_vault.id, dry_run=True)

    assert summary["merged"] == 1


@pytest.mark.asyncio
async def test_boosted_seeded_station_grows_to_nine(async_session: AsyncSession, rich_vault: Vault):
    """The real boosted layout's station slot merges two adjacent segments to size 9.

    The seeded station at (13, 0) must have free adjacent cells at (16, 0) and
    (19, 0); the test fails if the slot has no room to grow.
    """
    from app.core.game_data import get_static_game_data
    from app.services.vault import seeding

    game_data = await get_static_game_data()
    prepared = seeding.prepare_initial_rooms(game_data.rooms, rich_vault.id, is_boosted=True)
    await crud.vault.create_storage(db_session=async_session, vault_id=rich_vault.id)
    await seeding.create_initial_rooms(async_session, rich_vault, prepared)

    station = next(
        room
        for room in await crud.room.get_all_by_vault(async_session, rich_vault.id)
        if room.name == "Response Station"
    )
    assert station.size == 3
    assert calculate_room_capacity(station.size) == 2

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        grown_to_six, _created = await room_service._build(
            db_session=async_session,
            obj_in=_make_response_room_create(rich_vault.id, coordinate_x=16, coordinate_y=0),
        )
    assert grown_to_six.id == station.id
    assert grown_to_six.size == 6
    assert calculate_room_capacity(grown_to_six.size) == 4

    with patch("app.services.vault_service.vault_service.recalculate_vault_attributes", new_callable=AsyncMock):
        grown_to_nine, _created = await room_service._build(
            db_session=async_session,
            obj_in=_make_response_room_create(rich_vault.id, coordinate_x=19, coordinate_y=0),
        )
    assert grown_to_nine.id == station.id
    assert grown_to_nine.size == 9
    assert calculate_room_capacity(grown_to_nine.size) == 6

    names = await crud.room.get_names_by_vault(async_session, rich_vault.id)
    assert names.count("Response Station") == 1
