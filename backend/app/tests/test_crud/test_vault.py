import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.crud.room import room as room_crud
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.schemas.room import RoomCreate
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault


@pytest.mark.asyncio
async def test_create_vault_with_user(async_session: AsyncSession) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    assert vault.user_id == user.id


@pytest.mark.asyncio
async def test_building_living_room_updates_population_max(async_session: AsyncSession) -> None:
    """Test that building a living room updates vault.population_max."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    initial_population_max = vault.population_max

    room_data = RoomCreate(
        vault_id=vault.id,
        name="Living room",
        category=RoomTypeEnum.CAPACITY,
        tier=1,
        size=3,
        ability=SPECIALEnum.CHARISMA,
        capacity=8,
        population_required=None,
        base_cost=100,
        incremental_cost=25,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=3,
        size_max=9,
        coordinate_x=1,
        coordinate_y=1,
    )

    await room_crud.build(db_session=async_session, obj_in=room_data)

    await async_session.refresh(vault)

    assert vault.population_max == initial_population_max + 8, (
        f"Expected population_max to increase by 8, but went from {initial_population_max} to {vault.population_max}"
    )


@pytest.mark.asyncio
async def test_building_storage_room_updates_storage_capacity(async_session: AsyncSession) -> None:
    """Test that building a storage room updates vault storage."""
    from app.models.storage import Storage
    from sqlmodel import select

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    room_data = RoomCreate(
        vault_id=vault.id,
        name="Storage room",
        category=RoomTypeEnum.CAPACITY,
        tier=1,
        size=3,
        ability=SPECIALEnum.ENDURANCE,
        capacity=20,
        population_required=None,
        base_cost=300,
        incremental_cost=75,
        t2_upgrade_cost=750,
        t3_upgrade_cost=1500,
        size_min=3,
        size_max=9,
        coordinate_x=1,
        coordinate_y=1,
    )

    await room_crud.build(db_session=async_session, obj_in=room_data)

    storage_result = await async_session.execute(select(Storage).where(Storage.vault_id == vault.id))
    storage = storage_result.scalars().first()

    assert storage is not None, "Storage should be created when building storage room"
    assert storage.max_space == 20, f"Expected storage max_space to be 20, got {storage.max_space}"
