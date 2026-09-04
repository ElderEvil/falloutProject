"""Tests for dweller status changes during exploration lifecycle."""

from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.user_profile import profile_crud
from app.schemas.common import AgeGroupEnum, DwellerStatusEnum, RoomTypeEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.exploration_service import exploration_service
from app.tests.factory.dwellers import create_fake_adult_dweller, create_fake_dweller
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException


async def _finish_exploration(async_session: AsyncSession, exploration) -> None:
    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)


@pytest.mark.asyncio
async def test_dweller_status_exploring_on_send(async_session: AsyncSession):
    """Test that dweller status becomes EXPLORING when sent to wasteland."""
    # Setup - create user, vault, and dweller
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_data = create_fake_adult_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Dweller should start as IDLE
    assert dweller.status == DwellerStatusEnum.IDLE

    # Send dweller to exploration
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    profile = await profile_crud.get_by_user_id(async_session, user.id)
    assert profile is not None
    assert profile.total_explorations == 1

    # Refresh dweller and check status is now EXPLORING
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.EXPLORING
    assert exploration is not None


@pytest.mark.asyncio
async def test_exploring_dweller_cannot_be_assigned_to_room(async_session: AsyncSession):
    """An active explorer must return before being assigned to a vault room."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    dweller_data = create_fake_dweller()
    dweller_data = create_fake_adult_dweller()
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**dweller_data, vault_id=str(vault.id)),
    )
    room_data = create_fake_room()
    room_data["category"] = RoomTypeEnum.PRODUCTION
    room = await crud.room.create(async_session, obj_in=RoomCreate(**room_data, vault_id=vault.id))

    await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    with pytest.raises(ResourceConflictException, match="exploring"):
        await crud.dweller.move_to_room(async_session, dweller.id, room.id)


@pytest.mark.asyncio
async def test_dweller_status_idle_on_exploration_complete_no_room(async_session: AsyncSession):
    """Test that dweller status becomes IDLE when exploration completes and dweller has no room."""
    # Setup
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_adult_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Send dweller to exploration
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.EXPLORING

    # Complete exploration
    await _finish_exploration(async_session, exploration)
    await exploration_service.complete_exploration(async_session, exploration.id)

    # Refresh dweller and check status is now IDLE (no room assigned)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.IDLE
    assert dweller.room_id is None


@pytest.mark.asyncio
async def test_dweller_status_working_on_exploration_complete_with_room(async_session: AsyncSession):
    """Test that dweller status becomes WORKING when exploration completes and dweller has production room."""
    # Setup
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_data["population_max"] = 200
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_data = create_fake_adult_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Create production room and assign dweller
    room_data = create_fake_room()
    room_data["category"] = RoomTypeEnum.PRODUCTION
    room = await crud.room.create(async_session, obj_in=RoomCreate(**room_data, vault_id=vault.id))

    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.WORKING

    # Send dweller to exploration
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.EXPLORING

    # Complete exploration
    await _finish_exploration(async_session, exploration)
    await exploration_service.complete_exploration(async_session, exploration.id)

    # Room was vacated at dispatch, so the dweller returns IDLE and must be
    # reassigned explicitly to work again.
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.IDLE
    assert dweller.room_id is None


@pytest.mark.asyncio
async def test_dweller_status_training_on_exploration_complete_with_training_room(async_session: AsyncSession):
    """Test that dweller status becomes TRAINING when exploration completes and dweller has training room."""
    # Setup
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_data["population_max"] = 200
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_data = create_fake_adult_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Create training room and assign dweller
    room_data = create_fake_room()
    room_data["category"] = RoomTypeEnum.TRAINING
    room = await crud.room.create(async_session, obj_in=RoomCreate(**room_data, vault_id=vault.id))

    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.TRAINING

    # Send dweller to exploration
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.EXPLORING

    # Complete exploration
    await _finish_exploration(async_session, exploration)
    await exploration_service.complete_exploration(async_session, exploration.id)

    # Room was vacated at dispatch, so the dweller returns IDLE and must be
    # reassigned explicitly to train again.
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.IDLE
    assert dweller.room_id is None


@pytest.mark.asyncio
async def test_dweller_status_on_exploration_recall(async_session: AsyncSession):
    """Test that dweller status is restored correctly when exploration is recalled early."""
    # Setup
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_data["population_max"] = 200
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_data = create_fake_adult_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Create production room and assign dweller
    room_data = create_fake_room()
    room_data["category"] = RoomTypeEnum.PRODUCTION
    room = await crud.room.create(async_session, obj_in=RoomCreate(**room_data, vault_id=vault.id))

    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.WORKING

    # Send dweller to exploration
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.EXPLORING

    # Recall exploration early
    await exploration_service.recall_exploration(async_session, exploration.id)

    # Room was vacated at dispatch, so the dweller returns IDLE and must be
    # reassigned explicitly to work again.
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.IDLE
    assert dweller.room_id is None
