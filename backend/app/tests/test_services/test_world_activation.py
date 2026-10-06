"""World activation lifecycle: preview is structured and read-only, activation is
atomic and progress-preserving, and an affected in-progress expedition blocks it.

The requirement: one shared active world, independently stored candidates, an
explicit operator decision, and no destructive migration or local reset.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.world_snapshot import world_snapshot as snapshot_crud
from app.models.dweller import Dweller
from app.models.exploration import Exploration, ExplorationStatus
from app.models.user import User
from app.models.vault import Vault
from app.models.vault_slot import VaultSlot
from app.models.world_location import WorldLocation
from app.services.exploration_service import exploration_service
from app.services.map_service import map_service
from app.services.world_activation_service import ActivationPreview, world_activation_service
from app.services.world_generation_service import WORLD_ID, WorldRecipe
from app.services.world_snapshot_service import world_snapshot_service
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.places import WORLD_SCALE
from app.utils.vault_slots import slot_coords

pytestmark = pytest.mark.asyncio


async def _snapshot(session: AsyncSession, version: int, seed: str):
    return await world_snapshot_service.get_or_generate(
        session, WorldRecipe(seed=seed, generator_version=version, world_id=WORLD_ID)
    )


async def _make_active(session: AsyncSession, snapshot) -> None:
    snapshot.is_active = True
    snapshot.activated_at = datetime.utcnow()
    session.add(snapshot)
    await session.commit()


def _candidate_slots(snapshot) -> dict[int, tuple[float, float]]:
    return {int(s["slot_index"]): (float(s["coord_x"]), float(s["coord_y"])) for s in snapshot.slots}


def _first_moved_index(snapshot) -> int:
    for index, coord in _candidate_slots(snapshot).items():
        if coord != slot_coords(index):
            return index
    raise AssertionError("candidate unexpectedly matches the legacy slot grid for every index")


async def _count(session: AsyncSession, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_preview_reports_structured_deltas_and_writes_nothing(async_session: AsyncSession) -> None:
    active = await _snapshot(async_session, 1, "active-seed")
    candidate = await _snapshot(async_session, 2, "candidate-seed")
    await _make_active(async_session, active)

    preview = await world_activation_service.preview(async_session, candidate_version=2)

    assert isinstance(preview, ActivationPreview)
    assert (preview.active_version, preview.candidate_version) == (1, 2)
    assert preview.candidate_fingerprint == candidate.recipe_fingerprint
    assert preview.candidate_checksum == candidate.snapshot_checksum
    assert preview.terrain.total_tiles == 80 * 80
    assert preview.terrain.changed_tiles > 0
    assert any(delta.change == "moved" for delta in preview.slot_deltas)
    assert preview.activatable is True

    # Read-only: the pointer and the candidate's activation flag are untouched.
    reread_active = await snapshot_crud.get_active(async_session, world_id=WORLD_ID)
    assert reread_active is not None
    assert reread_active.generator_version == 1
    reread_candidate = await snapshot_crud.get_version(async_session, world_id=WORLD_ID, generator_version=2)
    assert reread_candidate is not None
    assert reread_candidate.is_active is False


async def test_activation_switches_pointer_and_agrees_coordinates(async_session: AsyncSession, vault: Vault) -> None:
    slot = VaultSlot(
        slot_index=_first_moved_index(await _snapshot(async_session, 2, "candidate-seed")), vault_id=vault.id
    )
    async_session.add(slot)
    await async_session.commit()
    await map_service.ensure_home_marker(async_session, vault)

    active = await _snapshot(async_session, 1, "active-seed")
    candidate = await _snapshot(async_session, 2, "candidate-seed")
    await _make_active(async_session, active)

    result = await world_activation_service.activate(
        async_session, candidate_version=2, expected_active_version=1, confirm=True
    )

    assert (result.active_version, result.previous_version) == (2, 1)
    reread_active = await snapshot_crud.get_active(async_session, world_id=WORLD_ID)
    assert reread_active is not None
    assert reread_active.generator_version == 2
    previous = await snapshot_crud.get_version(async_session, world_id=WORLD_ID, generator_version=1)
    assert previous is not None
    assert previous.is_active is False

    candidate_coord = _candidate_slots(candidate)[slot.slot_index]
    home = await map_service.ensure_home_marker(async_session, vault)
    # Snapshot slot, home marker, map marker, and dispatch origin all agree on the candidate placement.
    assert await world_snapshot_service.active_slot_coord(async_session, slot.slot_index) == candidate_coord
    assert (home.coord_x, home.coord_y) == candidate_coord
    origin, world_version = await exploration_service._vault_origin(async_session, vault.id)
    assert origin == candidate_coord
    assert world_version == 2

    vault_map = await map_service.get_vault_map(async_session, vault)
    marker = next(marker for marker in vault_map.player_vaults if marker.vault_id == vault.id)
    assert (marker.coord_x, marker.coord_y) == (
        round(candidate_coord[0] * WORLD_SCALE, 1),
        round(candidate_coord[1] * WORLD_SCALE, 1),
    )


async def test_spatial_departure_persists_the_active_snapshot_version(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    """A run departing an active placement stores that snapshot's version, not the default recipe's."""
    candidate = await _snapshot(async_session, 2, "candidate-seed")
    async_session.add(VaultSlot(slot_index=_first_moved_index(candidate), vault_id=vault.id))
    await async_session.commit()
    active = await _snapshot(async_session, 1, "active-seed")
    await _make_active(async_session, active)
    await world_activation_service.activate(async_session, candidate_version=2, expected_active_version=1, confirm=True)

    run = await exploration_service.depart(async_session, vault.id, [dweller.id], duration=4, heading_degrees=90)

    assert run.world_version == 2


async def test_activation_blocked_while_affected_expedition_active(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    candidate = await _snapshot(async_session, 2, "candidate-seed")
    moved_index = _first_moved_index(candidate)
    async_session.add(VaultSlot(slot_index=moved_index, vault_id=vault.id))
    await async_session.commit()

    active = await _snapshot(async_session, 1, "active-seed")
    await _make_active(async_session, active)

    async_session.add(
        Exploration(
            vault_id=vault.id,
            dweller_id=dweller.id,
            duration=4,
            dweller_strength=5,
            dweller_perception=5,
            dweller_endurance=5,
            dweller_charisma=5,
            dweller_intelligence=5,
            dweller_agility=5,
            dweller_luck=5,
            status=ExplorationStatus.ACTIVE,
        )
    )
    await async_session.commit()

    with pytest.raises(ResourceConflictException, match="in-progress expedition"):
        await world_activation_service.activate(
            async_session, candidate_version=2, expected_active_version=1, confirm=True
        )

    reread_active = await snapshot_crud.get_active(async_session, world_id=WORLD_ID)
    assert reread_active is not None
    assert reread_active.generator_version == 1
    reread_candidate = await snapshot_crud.get_version(async_session, world_id=WORLD_ID, generator_version=2)
    assert reread_candidate is not None
    assert reread_candidate.is_active is False


async def test_activation_preserves_progress(async_session: AsyncSession, vault: Vault) -> None:
    candidate = await _snapshot(async_session, 2, "candidate-seed")
    async_session.add(VaultSlot(slot_index=_first_moved_index(candidate), vault_id=vault.id))
    await async_session.commit()
    home = await map_service.ensure_home_marker(async_session, vault)

    active = await _snapshot(async_session, 1, "active-seed")
    await _make_active(async_session, active)

    tracked = (User, Vault, Dweller, WorldLocation, Exploration, VaultSlot)
    before = {model.__name__: await _count(async_session, model) for model in tracked}

    await world_activation_service.activate(async_session, candidate_version=2, expected_active_version=1, confirm=True)

    after = {model.__name__: await _count(async_session, model) for model in tracked}
    assert after == before

    reread_home = await map_service.ensure_home_marker(async_session, vault)
    assert reread_home.id == home.id


async def test_activation_rejects_stale_expected_active_version(async_session: AsyncSession) -> None:
    active = await _snapshot(async_session, 1, "active-seed")
    await _snapshot(async_session, 2, "candidate-seed")
    await _make_active(async_session, active)

    with pytest.raises(ResourceConflictException):
        await world_activation_service.activate(
            async_session, candidate_version=2, expected_active_version=99, confirm=True
        )
    assert (await snapshot_crud.get_active(async_session, world_id=WORLD_ID)).generator_version == 1


async def test_activation_requires_explicit_confirmation(async_session: AsyncSession) -> None:
    await _snapshot(async_session, 1, "first-seed")
    with pytest.raises(ValidationException):
        await world_activation_service.activate(
            async_session, candidate_version=1, expected_active_version=None, confirm=False
        )


async def test_first_activation_without_an_active_world(async_session: AsyncSession) -> None:
    await _snapshot(async_session, 1, "first-seed")
    result = await world_activation_service.activate(
        async_session, candidate_version=1, expected_active_version=None, confirm=True
    )
    assert (result.active_version, result.previous_version) == (1, None)
    active = await snapshot_crud.get_active(async_session, world_id=WORLD_ID)
    assert active is not None
    assert active.generator_version == 1

    candidates = await snapshot_crud.list_candidates(async_session, world_id=WORLD_ID)
    assert candidates == []
