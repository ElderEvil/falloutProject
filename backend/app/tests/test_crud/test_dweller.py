import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.enums import AgeGroupEnum, DwellerStatusEnum, RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.schemas.dweller import DwellerCreate, DwellerUpdate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.dweller_service import dweller_service
from app.tests.factory.dwellers import create_fake_adult_dweller, create_fake_dweller
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import (
    InvalidVaultTransferException,
    ResourceConflictException,
    ValidationException,
)

_ARENA = {
    "name": "Arena",
    "category": RoomTypeEnum.ARENA,
    "ability": SPECIALEnum.STRENGTH,
    "base_cost": 800,
    "t2_upgrade_cost": 3000,
    "t3_upgrade_cost": 9000,
    "size_min": 6,
    "size_max": 6,
}


async def _user_vault(async_session: AsyncSession, **vault_overrides):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    return await crud.vault.create(
        async_session, obj_in=VaultCreateWithUserID(**(create_fake_vault() | vault_overrides), user_id=user.id)
    )


async def _dweller(async_session, vault, factory=create_fake_dweller):
    return await crud.dweller.create(async_session, obj_in=DwellerCreate(**factory(), vault_id=str(vault.id)))


async def _room(async_session, vault, category=None):
    data = create_fake_room() if category is None else create_fake_room() | {"category": category}
    return await crud.room.create(async_session, obj_in=RoomCreate(**data, vault_id=vault.id))


async def test_move_dweller_to_room(async_session: AsyncSession):
    vault = await _user_vault(async_session)
    dweller = await _dweller(async_session, vault)
    room_1 = await _room(async_session, vault, category=RoomTypeEnum.PRODUCTION)
    room_2 = await _room(async_session, vault, category=RoomTypeEnum.PRODUCTION)
    dweller.room_id = room_1.id
    await async_session.commit()
    await dweller_service.move_to_room(async_session, dweller_id=dweller.id, room_id=room_2.id)
    assert dweller.room_id == room_2.id, "Dweller should be moved to the new room"
    with pytest.raises(ResourceConflictException) as exc_info:
        await dweller_service.move_to_room(async_session, dweller_id=dweller.id, room_id=room_2.id)
    assert "Dweller is already in the room" in str(exc_info.value), "Should raise conflict when moving to the same room"
    other_vault = await _user_vault(async_session)
    room_3 = await _room(async_session, other_vault)
    with pytest.raises(InvalidVaultTransferException):
        await dweller_service.move_to_room(async_session, dweller_id=dweller.id, room_id=room_3.id)


async def test_move_teen_to_arena_rejected(async_session: AsyncSession):
    vault = await _user_vault(async_session)
    dweller = await _dweller(async_session, vault)
    dweller.age_group = AgeGroupEnum.TEEN
    await async_session.commit()
    arena_room = await crud.room.create(async_session, obj_in=RoomCreate(**_ARENA, vault_id=vault.id))
    with pytest.raises(ValidationException):
        await dweller_service.move_to_room(async_session, dweller_id=dweller.id, room_id=arena_room.id)


async def test_move_child_to_training_room_rejected(
    async_session: AsyncSession,
    user_with_vault: tuple,
    dweller_in_vault,
):
    _, vault = user_with_vault
    vault.population_max = 1
    dweller_in_vault.age_group = AgeGroupEnum.CHILD
    await async_session.commit()
    training_room = await _room(async_session, vault, category=RoomTypeEnum.TRAINING)
    with pytest.raises(ValidationException, match="only be assigned to production rooms"):
        await dweller_service.move_to_room(async_session, dweller_in_vault.id, training_room.id)


async def test_move_adult_to_arena_sets_idle_status(async_session: AsyncSession):
    vault = await _user_vault(async_session)
    dweller = await _dweller(async_session, vault, create_fake_adult_dweller)
    await async_session.commit()
    starter_room = await _room(async_session, vault)
    dweller.room_id = starter_room.id
    await async_session.commit()
    arena_room = await crud.room.create(async_session, obj_in=RoomCreate(**_ARENA, vault_id=vault.id))
    moved = await dweller_service.move_to_room(async_session, dweller_id=dweller.id, room_id=arena_room.id)
    assert moved.room_id == arena_room.id
    assert moved.status == DwellerStatusEnum.IDLE


async def test_get_max_level(async_session: AsyncSession):
    vault = await _user_vault(async_session)
    assert await crud.dweller.get_max_level(async_session, vault.id) is None
    for level in (5, 20, 12):
        async_session.add(Dweller(**(create_fake_dweller() | {"level": level}), vault_id=vault.id))
    await async_session.commit()
    assert await crud.dweller.get_max_level(async_session, vault.id) == 20
    async_session.add(Dweller(**(create_fake_dweller() | {"level": 50, "is_dead": True}), vault_id=vault.id))
    await async_session.commit()
    assert await crud.dweller.get_max_level(async_session, vault.id) == 20


async def test_count_alive_in_vault_excludes_dead(async_session: AsyncSession):
    vault = await _user_vault(async_session)
    for level in (5, 20):
        async_session.add(Dweller(**(create_fake_dweller() | {"level": level}), vault_id=vault.id))
    async_session.add(Dweller(**(create_fake_dweller() | {"level": 46, "is_dead": True}), vault_id=vault.id))
    await async_session.commit()
    assert await crud.dweller.count_alive_in_vault(async_session, vault.id) == 2
    assert await crud.dweller.count_alive_in_vault(async_session, vault.id, min_level=20) == 1
    assert await crud.dweller.count_alive_in_vault(async_session, vault.id, min_level=46) == 0


async def test_get_dwellers_by_status(async_session: AsyncSession):
    vault = await _user_vault(async_session, population_max=200)
    dweller_1, dweller_2, dweller_3 = [await _dweller(async_session, vault) for _ in range(3)]
    await crud.dweller.update(async_session, dweller_1.id, DwellerUpdate(status=DwellerStatusEnum.WORKING))
    await crud.dweller.update(async_session, dweller_2.id, DwellerUpdate(status=DwellerStatusEnum.EXPLORING))
    for dweller, status in zip(
        (dweller_1, dweller_2, dweller_3),
        (DwellerStatusEnum.WORKING, DwellerStatusEnum.EXPLORING, DwellerStatusEnum.IDLE),
        strict=True,
    ):
        found = await crud.dweller.get_by_status(async_session, vault.id, status)
        assert len(found) == 1
        assert found[0].id == dweller.id
