import random
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.crud.user_profile import profile_crud
from app.options.factions import faction_restrictions
from app.options.races import RaceOption
from app.schemas.common import AgeGroupEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate, DwellerCreateCommonOverride, DwellerCreateWithoutVaultID
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.dwellers import create_random_common_dweller
from app.utils.exceptions import (
    InvalidVaultTransferException,
    ResourceConflictException,
    ValidationException,
)
from backend.app.tests.factory.dwellers import create_fake_dweller

RACE_VALUES = {race.value for race in RaceOption}


@pytest.mark.asyncio
async def test_move_dweller_to_room(async_session: AsyncSession):
    # Setup - create user, vault, and dweller
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Create initial room and another room for the move
    room_data_1 = create_fake_room()
    room_data_1["category"] = RoomTypeEnum.PRODUCTION
    room_1 = await crud.room.create(async_session, obj_in=RoomCreate(**room_data_1, vault_id=vault.id))

    room_data_2 = create_fake_room()
    room_data_2["category"] = RoomTypeEnum.PRODUCTION
    room_2 = await crud.room.create(async_session, obj_in=RoomCreate(**room_data_2, vault_id=vault.id))

    # Initially assign the dweller to room 1
    dweller.room_id = room_1.id
    await async_session.commit()

    # Test: Move dweller from room 1 to room 2
    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room_2.id)
    assert dweller.room_id == room_2.id, "Dweller should be moved to the new room"

    # Test: Attempt to move dweller to the same room they are already in
    with pytest.raises(ResourceConflictException) as exc_info:
        await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room_2.id)
    assert "Dweller is already in the room" in str(exc_info.value), "Should raise conflict when moving to the same room"

    # Test: Try to move dweller to a room in a different vault
    vault_data_2 = create_fake_vault()
    vault_in_2 = VaultCreateWithUserID(**vault_data_2, user_id=user.id)
    vault_2 = await crud.vault.create(async_session, obj_in=vault_in_2)
    room_data_3 = create_fake_room()
    room_3 = await crud.room.create(async_session, obj_in=RoomCreate(**room_data_3, vault_id=vault_2.id))
    with pytest.raises(InvalidVaultTransferException):
        await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room_3.id)


@pytest.mark.asyncio
async def test_move_teen_with_is_adult_flag_to_arena_rejected(async_session: AsyncSession):
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)
    dweller.is_adult = True
    dweller.age_group = AgeGroupEnum.TEEN
    await async_session.commit()

    arena_room = await crud.room.create(
        async_session,
        obj_in=RoomCreate(
            name="Arena",
            category=RoomTypeEnum.ARENA,
            ability=SPECIALEnum.STRENGTH,
            base_cost=800,
            t2_upgrade_cost=3000,
            t3_upgrade_cost=9000,
            size_min=6,
            size_max=6,
            vault_id=vault.id,
        ),
    )

    with pytest.raises(ValidationException):
        await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=arena_room.id)


@pytest.mark.asyncio
async def test_move_child_to_training_room_rejected(
    async_session: AsyncSession,
    user_with_vault: tuple,
    dweller_in_vault,
):
    _, vault = user_with_vault
    vault.population_max = 1
    dweller_in_vault.age_group = AgeGroupEnum.CHILD
    dweller_in_vault.is_adult = False
    await async_session.commit()

    room_data = create_fake_room()
    room_data["category"] = RoomTypeEnum.TRAINING
    training_room = await crud.room.create(async_session, RoomCreate(**room_data, vault_id=vault.id))

    with pytest.raises(ValidationException, match="only be assigned to production rooms"):
        await crud.dweller.move_to_room(async_session, dweller_in_vault.id, training_room.id)


@pytest.mark.asyncio
async def test_move_adult_to_arena_sets_fighting_status(async_session: AsyncSession):
    from app.schemas.common import DwellerStatusEnum

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)
    dweller.is_adult = True
    await async_session.commit()

    starter_room = await crud.room.create(async_session, obj_in=RoomCreate(**create_fake_room(), vault_id=vault.id))
    dweller.room_id = starter_room.id
    await async_session.commit()

    arena_room = await crud.room.create(
        async_session,
        obj_in=RoomCreate(
            name="Arena",
            category=RoomTypeEnum.ARENA,
            ability=SPECIALEnum.STRENGTH,
            base_cost=800,
            t2_upgrade_cost=3000,
            t3_upgrade_cost=9000,
            size_min=6,
            size_max=6,
            vault_id=vault.id,
        ),
    )

    moved = await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=arena_room.id)
    assert moved.room_id == arena_room.id
    assert moved.status == DwellerStatusEnum.FIGHTING


@pytest.mark.asyncio
async def test_get_dwellers_by_status(async_session: AsyncSession):
    """Test getting dwellers filtered by status."""
    from app.schemas.common import DwellerStatusEnum
    from app.schemas.dweller import DwellerUpdate

    # Setup - create user, vault, and multiple dwellers
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_data["population_max"] = 200  # Ensure enough space
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create 3 dwellers with different statuses
    dweller_1_data = create_fake_dweller()
    dweller_1_in = DwellerCreate(**dweller_1_data, vault_id=str(vault.id))
    dweller_1 = await crud.dweller.create(async_session, obj_in=dweller_1_in)

    dweller_2_data = create_fake_dweller()
    dweller_2_in = DwellerCreate(**dweller_2_data, vault_id=str(vault.id))
    dweller_2 = await crud.dweller.create(async_session, obj_in=dweller_2_in)

    dweller_3_data = create_fake_dweller()
    dweller_3_in = DwellerCreate(**dweller_3_data, vault_id=str(vault.id))
    dweller_3 = await crud.dweller.create(async_session, obj_in=dweller_3_in)

    # Set different statuses
    await crud.dweller.update(async_session, dweller_1.id, DwellerUpdate(status=DwellerStatusEnum.WORKING))
    await crud.dweller.update(async_session, dweller_2.id, DwellerUpdate(status=DwellerStatusEnum.EXPLORING))
    # dweller_3 stays IDLE

    # Get only WORKING dwellers
    working_dwellers = await crud.dweller.get_by_status(async_session, vault.id, DwellerStatusEnum.WORKING)
    assert len(working_dwellers) == 1
    assert working_dwellers[0].id == dweller_1.id

    # Get only EXPLORING dwellers
    exploring_dwellers = await crud.dweller.get_by_status(async_session, vault.id, DwellerStatusEnum.EXPLORING)
    assert len(exploring_dwellers) == 1
    assert exploring_dwellers[0].id == dweller_2.id

    # Get only IDLE dwellers
    idle_dwellers = await crud.dweller.get_by_status(async_session, vault.id, DwellerStatusEnum.IDLE)
    assert len(idle_dwellers) == 1
    assert idle_dwellers[0].id == dweller_3.id
