from datetime import timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, RoomTypeEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.dweller_service import dweller_service
from app.services.exploration_service import exploration_service
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException
from app.utils.time import utcnow


async def _user_vault(async_session: AsyncSession, **vault_overrides):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(
        async_session, obj_in=VaultCreateWithUserID(**(create_fake_vault() | vault_overrides), user_id=user.id)
    )


async def _dweller(async_session: AsyncSession, vault):
    return await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=str(vault.id))
    )


async def _room(async_session: AsyncSession, vault, category):
    return await crud.room.create(
        async_session, obj_in=RoomCreate(**(create_fake_room() | {"category": category}), vault_id=vault.id)
    )


async def _finish_exploration(async_session: AsyncSession, exploration) -> None:
    exploration.start_time = utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.commit()
    await async_session.refresh(exploration)
    await exploration_service.start_return(async_session, exploration.id)
    await async_session.refresh(exploration)
    exploration.return_completes_at = utcnow() - timedelta(seconds=1)
    async_session.add(exploration)
    await async_session.commit()
    await exploration_service.finalize_return(async_session, exploration.id)


async def test_exploring_dweller_cannot_be_assigned_to_room(async_session: AsyncSession):
    # An active explorer must return before being assigned to a vault room.
    vault = await _user_vault(async_session)
    dweller = await _dweller(async_session, vault)
    room = await _room(async_session, vault, RoomTypeEnum.PRODUCTION)
    await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    with pytest.raises(ResourceConflictException, match="exploring"):
        await dweller_service.move_to_room(async_session, dweller.id, room.id)


async def test_dweller_status_training_on_exploration_complete_with_training_room(async_session: AsyncSession):
    vault = await _user_vault(async_session, population_max=200)
    dweller = await _dweller(async_session, vault)
    room = await _room(async_session, vault, RoomTypeEnum.TRAINING)
    await dweller_service.move_to_room(async_session, dweller_id=dweller.id, room_id=room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.TRAINING
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.EXPLORING
    await _finish_exploration(async_session, exploration)
    # Room was vacated at dispatch, so the dweller returns IDLE and must be reassigned to train again.
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.IDLE
    assert dweller.room_id is None
