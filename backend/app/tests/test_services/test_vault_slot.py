"""Vault slots: placement coordinates, claim order, and the shared discovery list."""

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import vault as crud_vault
from app.crud.vault_slot import vault_slot
from app.crud.world_location import world_location as wl_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service
from app.utils.exceptions import ResourceConflictException
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


@pytest.mark.asyncio
async def test_soft_delete_releases_the_slot(async_session: AsyncSession, vault: Vault):
    await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    assert await vault_slot.get_by_vault(async_session, vault.id) is not None

    deleted = await crud_vault.delete(async_session, vault.id, soft=True)

    assert deleted.is_deleted is True
    assert await vault_slot.get_by_vault(async_session, vault.id) is None


@pytest.mark.asyncio
async def test_restore_reclaims_a_slot(async_session: AsyncSession, vault: Vault):
    await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await crud_vault.delete(async_session, vault.id, soft=True)

    restored = await crud_vault.restore(async_session, vault.id)

    assert restored.is_deleted is False
    assert await vault_slot.get_by_vault(async_session, vault.id) is not None


@pytest.mark.asyncio
async def test_restore_fails_when_no_slot_is_available(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
):
    from app.core.game_config import game_config

    await vault_slot.claim_next(db_session=async_session, vault_id=vault.id)
    await crud_vault.delete(async_session, vault.id, soft=True)

    # Shrink the atlas to a single slot and fill it with another vault.
    monkeypatch.setattr(game_config.vault_slots, "count", 1)
    other = Vault(number=126, user_id=vault.user_id)
    async_session.add(other)
    await async_session.flush()
    await vault_slot.claim_for_new_vault(db_session=async_session, vault_id=other.id)
    await async_session.commit()

    with pytest.raises(ResourceConflictException):
        await crud_vault.restore(async_session, vault.id)

    refreshed = await crud_vault.get(async_session, vault.id, include_deleted=True)
    assert refreshed.is_deleted is True
