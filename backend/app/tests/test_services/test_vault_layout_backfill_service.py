"""Tests for the vault layout backfill service summary and dry-run behavior."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.vault import Vault
from app.schemas.common import RoomTypeEnum
from app.schemas.room import RoomCreate
from app.services.vault_layout_backfill_service import vault_layout_backfill_service

FIXED_ROOMS = {"Vault Door", "Elevator"}


def _room_payload(
    vault_id: UUID,
    *,
    name: str,
    coordinate_x: int,
    coordinate_y: int,
    size: int = 3,
) -> RoomCreate:
    is_fixed = name in FIXED_ROOMS
    return RoomCreate(
        vault_id=vault_id,
        name=name,
        category=RoomTypeEnum.MISC if is_fixed else RoomTypeEnum.PRODUCTION,
        ability=None,
        population_required=None,
        base_cost=100,
        incremental_cost=None if is_fixed else 25,
        t2_upgrade_cost=None,
        t3_upgrade_cost=None,
        capacity=None,
        output=None,
        size_min=size,
        size_max=size,
        size=size,
        tier=1,
        coordinate_x=coordinate_x,
        coordinate_y=coordinate_y,
        image_url=None,
        speedup_multiplier=1.0,
    )


@pytest.mark.asyncio
async def test_relayout_empty_vault_reports_floor_width(async_session: AsyncSession):
    """An empty vault still returns the full summary shape the CLI reads."""
    summary = await vault_layout_backfill_service.relayout(async_session, uuid4(), dry_run=True)

    assert summary == {
        "rooms": 0,
        "moved": 0,
        "elevators_to_add": 0,
        "overlaps": 0,
        "floating": 0,
        "floor_width_ok": True,
    }


@pytest.mark.asyncio
async def test_relayout_does_not_flag_a_lone_elevator_as_floating(async_session: AsyncSession, vault: Vault):
    """A level holding only the shaft elevator is anchored vertically, not floating."""
    await crud.room.create(
        async_session,
        obj_in=_room_payload(vault.id, name="Vault Door", coordinate_x=0, coordinate_y=0, size=6),
    )
    await crud.room.create(
        async_session,
        obj_in=_room_payload(vault.id, name="Elevator", coordinate_x=6, coordinate_y=0, size=1),
    )
    await crud.room.create(
        async_session,
        obj_in=_room_payload(vault.id, name="Elevator", coordinate_x=6, coordinate_y=1, size=1),
    )

    summary = await vault_layout_backfill_service.relayout(async_session, vault.id, dry_run=True)

    assert summary["floating"] == 0


@pytest.mark.asyncio
async def test_relayout_dry_run_does_not_move_the_door(async_session: AsyncSession, vault: Vault):
    """A dry run leaves the vault door where it is while still reporting it as moved."""
    door = await crud.room.create(
        async_session,
        obj_in=_room_payload(vault.id, name="Vault Door", coordinate_x=3, coordinate_y=2, size=6),
    )

    summary = await vault_layout_backfill_service.relayout(async_session, vault.id, dry_run=True)

    await async_session.refresh(door)
    assert (door.coordinate_x, door.coordinate_y) == (3, 2)
    assert summary["moved"] >= 1
