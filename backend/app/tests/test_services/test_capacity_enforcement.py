"""Strict vault-capacity enforcement: every living dweller counts, assigned or not.

Regression tests for the assigned-only counting loophole that let vaults
overflow their population_max (e.g. a vault at 23/8 capacity).
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.dweller_service import dweller_service
from app.services.vault_service import vault_service
from app.utils.exceptions import NoLivingSpaceError


async def _set_population_max(async_session: AsyncSession, vault, population_max: int | None) -> None:
    vault.population_max = population_max
    async_session.add(vault)
    await async_session.commit()


@pytest.mark.asyncio
async def test_unassigned_dweller_counts_toward_capacity(
    async_session: AsyncSession,
    vault,
    dweller,
) -> None:
    """The old assigned-only counting ignored unassigned dwellers; the cap must not."""
    dweller.room_id = None
    async_session.add(dweller)
    await async_session.commit()

    await _set_population_max(async_session, vault, population_max=1)
    assert not await vault_service.is_enough_population_space(
        db_session=async_session, vault_id=vault.id, space_required=1
    ), "A full vault must refuse another dweller even if the resident is unassigned"

    await _set_population_max(async_session, vault, population_max=2)
    assert await vault_service.is_enough_population_space(db_session=async_session, vault_id=vault.id, space_required=1)


@pytest.mark.asyncio
async def test_create_dweller_raises_at_capacity(
    async_session: AsyncSession,
    vault,
    dweller,
    dweller_data: dict,
) -> None:
    await _set_population_max(async_session, vault, population_max=1)

    with pytest.raises(NoLivingSpaceError, match="population capacity reached"):
        await dweller_service.create_dweller(
            async_session, DwellerCreate(**dweller_data, vault_id=vault.id), commit=False
        )


@pytest.mark.asyncio
async def test_create_random_dweller_bypasses_for_bootstrap(
    async_session: AsyncSession,
    vault,
    dweller,
) -> None:
    """Seeding/pregen run at vault bootstrap and must be able to fill a fresh vault."""
    await _set_population_max(async_session, vault, population_max=1)

    bootstrap_dweller = await dweller_service.create_random_dweller(async_session, vault.id, enforce_capacity=False)
    assert bootstrap_dweller.vault_id == vault.id

    with pytest.raises(NoLivingSpaceError, match="population capacity reached"):
        await dweller_service.create_random_dweller(async_session, vault.id)


@pytest.mark.asyncio
async def test_work_assignment_allowed_when_vault_full(
    async_session: AsyncSession,
    vault,
    dweller,
) -> None:
    """Assigning a resident to a work room never changes population: no capacity gate."""
    await _set_population_max(async_session, vault, population_max=1)

    room = await crud.room.create(
        db_session=async_session,
        obj_in=RoomCreate(
            vault_id=vault.id,
            name="Test Room",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            capacity=4,
            output=100,
            size_min=1,
            size_max=3,
            size=2,
            tier=1,
            coordinate_x=1,
            coordinate_y=1,
        ),
    )

    assigned = await dweller_service.move_to_room(async_session, dweller.id, room.id)
    assert assigned.room_id == room.id
