"""Vault slots: placement coordinates, claim order, and the shared discovery list."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import vault as crud_vault
from app.crud.vault_slot import vault_slot
from app.crud.world_location import world_location as wl_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.exploration_service import dispatch_travel_hours, exploration_service, scout_band_hours
from app.services.map_service import map_service
from app.utils.vault_slots import slot_coords


def test_slot_coords_are_scattered_but_valid():
    cells = [slot_coords(i) for i in range(10)]
    # Distinct, in-bounds, and not laid out in a single row.
    assert len(set(cells)) == 10
    assert all(0 < x < 100 and 0 < y < 100 for x, y in cells)
    assert len({y for _, y in cells}) > 1
    assert slot_coords(0) == slot_coords(0)


@pytest.mark.asyncio
async def test_claim_next_assigns_distinct_slots(async_session: AsyncSession, vault: Vault):
    second = Vault(number=123, user_id=vault.user_id)
    async_session.add(second)
    await async_session.flush()

    a = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    b = await vault_slot.claim_next(db_session=async_session, vault_id=second.id)

    assert a.slot_index >= 0
    assert b.slot_index == a.slot_index + 1


@pytest.mark.asyncio
async def test_list_markers_reports_live_vaults(async_session: AsyncSession, vault: Vault):
    await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)

    markers = await vault_slot.list_markers(async_session)

    assert any(marker[1] == vault.id and marker[2] == vault.number for marker in markers)


@pytest.mark.asyncio
async def test_home_marker_sits_at_the_vault_slot(async_session: AsyncSession, vault: Vault):
    slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await async_session.commit()

    home = await map_service.ensure_home_marker(async_session, vault)

    assert (home.coord_x, home.coord_y) == slot_coords(slot.slot_index)


@pytest.mark.asyncio
async def test_center_home_marker_is_moved_to_the_slot(async_session: AsyncSession, vault: Vault):
    slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await async_session.commit()
    home = await wl_crud.get_or_create_home_marker(async_session, vault)
    assert (home.coord_x, home.coord_y) == (50.0, 50.0)

    moved = await map_service.ensure_home_marker(async_session, vault)

    assert (moved.coord_x, moved.coord_y) == slot_coords(slot.slot_index)


@pytest.mark.asyncio
async def test_dispatch_travel_origin_is_the_vault_slot(async_session: AsyncSession, vault: Vault):
    slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await async_session.commit()

    origin = await exploration_service._vault_origin(async_session, vault.id)

    assert origin == slot_coords(slot.slot_index)


def test_scout_band_widens_with_distance():
    assert scout_band_hours(1) == (1, 3)
    assert scout_band_hours(5) == (4, 8)
    assert scout_band_hours(10) == (8, 16)
    assert scout_band_hours(30) == (24, 40)


@pytest.mark.asyncio
async def test_scout_sends_a_run_from_the_vault_slot(async_session: AsyncSession, vault: Vault, dweller: Dweller):
    slot = await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await async_session.commit()

    exploration, band_low, band_high = await exploration_service.scout(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        target_coord_x=100.0,
        target_coord_y=100.0,
    )

    origin = slot_coords(slot.slot_index)
    distance = ((origin[0] - 100) ** 2 + (origin[1] - 100) ** 2) ** 0.5
    expected_low, expected_high = scout_band_hours(dispatch_travel_hours(distance))
    assert (band_low, band_high) == (max(1, min(24, expected_low)), max(1, min(24, expected_high)))
    assert exploration.duration == band_high


@pytest.mark.asyncio
async def test_create_with_user_id_claims_a_slot(async_session: AsyncSession, vault: Vault):
    created = await crud_vault.create_with_user_id(
        db_session=async_session,
        obj_in={"number": 124, "bottle_caps": 1000},
        user_id=vault.user_id,
    )

    slot = await vault_slot.get_by_vault(async_session, created.id)
    assert slot is not None


@pytest.mark.asyncio
async def test_slot_allocation_failure_leaves_no_vault(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
):
    from app.utils.exceptions import ResourceConflictException

    async def _exhausted(*args, **kwargs):
        raise ResourceConflictException("No vault slots are available.")

    monkeypatch.setattr(vault_slot, "claim_for_new_vault", _exhausted)
    with pytest.raises(ResourceConflictException):
        await crud_vault.create_with_user_id(
            db_session=async_session,
            obj_in={"number": 125, "bottle_caps": 1000},
            user_id=vault.user_id,
        )

    persisted = (await async_session.execute(select(Vault).where(Vault.number == 125))).scalar_one_or_none()
    assert persisted is None
