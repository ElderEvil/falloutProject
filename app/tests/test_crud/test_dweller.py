import random

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.crud.dweller import BOOSTED_STAT_VALUE
from app.schemas.common import SPECIAL
from app.schemas.dweller import DwellerCreate, DwellerCreateCommonOverride
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, InvalidVaultTransferException


@pytest.mark.asyncio
async def test_create_dweller(async_session: AsyncSession) -> None:
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)
    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)
    assert dweller.first_name == dweller_data["first_name"]
    assert dweller.last_name == dweller_data["last_name"]
    assert dweller.is_adult == dweller_data["is_adult"]
    assert dweller.gender == dweller_data["gender"]
    assert dweller.rarity == dweller_data["rarity"]
    assert dweller.level == dweller_data["level"]
    assert dweller.experience == dweller_data["experience"]
    assert dweller.max_health == dweller_data["max_health"]
    assert dweller.health == dweller_data["health"]
    assert dweller.radiation == dweller_data["radiation"]
    assert dweller.happiness == dweller_data["happiness"]


@pytest.mark.asyncio
async def test_read_dweller(async_session: AsyncSession):
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)
    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)
    dweller_read = await crud.dweller.get(async_session, id=dweller.id)
    assert dweller_read
    assert dweller.first_name == dweller_read.first_name
    assert dweller.last_name == dweller_read.last_name


@pytest.mark.asyncio
async def test_create_random_common_dweller(async_session: AsyncSession):
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Create a random dweller without overrides
    dweller = await crud.dweller.create_random(db_session=async_session, vault_id=vault.id)
    assert dweller.id
    assert dweller.vault_id == vault.id  # Check vault association

    # Create a random dweller with a special boost override
    special_stat = random.choice(list(SPECIAL))
    override = DwellerCreateCommonOverride(special_boost=special_stat)
    dweller_boosted = await crud.dweller.create_random(db_session=async_session, obj_in=override, vault_id=vault.id)
    assert dweller_boosted.id
    assert dweller_boosted.vault_id == vault.id  # Check vault association
    assert getattr(dweller_boosted, special_stat.value.lower()) == BOOSTED_STAT_VALUE


@pytest.mark.asyncio
async def test_dweller_add_exp(async_session: AsyncSession):
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)
    dweller_data = create_fake_dweller()
    dweller_data["experience"] = 0
    dweller_data["level"] = 1
    dweller_data["vault_id"] = vault.id
    dweller_in = DwellerCreate(**dweller_data)
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)
    assert dweller.experience == dweller_data["experience"]
    await crud.dweller.add_experience(async_session, dweller_obj=dweller, amount=10)
    assert dweller.experience == 10
    exp_amount = crud.dweller.calculate_experience_required(dweller_obj=dweller)
    await crud.dweller.add_experience(async_session, dweller_obj=dweller, amount=exp_amount)
    assert dweller.experience == 10
    assert dweller.level == 2


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
    room_1 = await crud.room.create(async_session, obj_in=RoomCreate(**room_data_1, vault_id=vault.id))

    room_data_2 = create_fake_room()
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
    assert "Dweller is already in the room" in str(
        exc_info.value
    ), "Should raise conflict when moving to the same room"

    # Test: Try to move dweller to a room in a different vault
    vault_data_2 = create_fake_vault()
    vault_in_2 = VaultCreateWithUserID(**vault_data_2, user_id=user.id)
    vault_2 = await crud.vault.create(async_session, obj_in=vault_in_2)
    room_data_3 = create_fake_room()
    room_3 = await crud.room.create(async_session, obj_in=RoomCreate(**room_data_3, vault_id=vault_2.id))
    with pytest.raises(InvalidVaultTransferException):
        await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room_3.id)
