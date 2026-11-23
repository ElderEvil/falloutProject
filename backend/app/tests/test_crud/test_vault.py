import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.models.room import Room
from app.models.storage import Storage
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.room_service import RoomService
from app.tests.factory.dwellers import create_fake_adult_dweller
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ValidationException
from app.utils.place_seed import get_seeded_vault_numbers

_STORAGE = {
    "name": "Storage room",
    "category": RoomTypeEnum.CAPACITY,
    "ability": SPECIALEnum.ENDURANCE,
    "tier": 1,
    "size": 3,
    "capacity": 30,
    "population_required": None,
    "base_cost": 300,
    "incremental_cost": 75,
    "t2_upgrade_cost": 750,
    "t3_upgrade_cost": 1500,
    "size_min": 3,
    "size_max": 9,
}
_LIVING = _STORAGE | {
    "name": "Living room",
    "ability": SPECIALEnum.CHARISMA,
    "capacity": None,
    "capacity_formula": None,
    "t2_upgrade_cost": 500,
}
_ELEVATOR = {
    "name": "Elevator",
    "category": RoomTypeEnum.MISC,
    "ability": None,
    "base_cost": 100,
    "incremental_cost": 25,
    "t2_upgrade_cost": None,
    "t3_upgrade_cost": None,
    "size_min": 1,
    "size_max": 1,
    "size": 1,
    "coordinate_x": 0,
}


async def _user_vault(async_session: AsyncSession, caps: int | None = None):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault_data = create_fake_vault() | ({} if caps is None else {"bottle_caps": caps})
    return await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))


async def _add_elevator_on_level(async_session, vault_id, y):
    """Create an elevator row directly so a room build passes elevator gating."""
    return await crud.room.create(async_session, RoomCreate(**_ELEVATOR | {"coordinate_y": y}, vault_id=vault_id))


def _storage_room(vault_id, x: int = 1, y: int = 1) -> RoomCreate:
    """A storage room wired like its catalog entry, planted at (x, y)."""
    return RoomCreate(**_STORAGE | {"capacity_formula": "5*S*(L+1)"}, vault_id=vault_id, coordinate_x=x, coordinate_y=y)


async def _storage_row(async_session, vault_id):
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault_id))
    return result.scalars().first()


async def _first_room(async_session, vault_id, name):
    result = await async_session.execute(select(Room).where(Room.vault_id == vault_id, Room.name == name))
    return result.scalars().first()


async def _dweller(async_session, vault):
    return await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**create_fake_adult_dweller(), vault_id=vault.id)
    )


async def test_building_storage_room_updates_storage_capacity(async_session: AsyncSession) -> None:
    vault = await _user_vault(async_session, caps=10_000)
    initial = await _storage_row(async_session, vault.id)
    initial_max_space = initial.max_space if initial else 0
    room_data = RoomCreate(**_STORAGE, vault_id=vault.id, coordinate_x=1, coordinate_y=1)
    await _add_elevator_on_level(async_session, vault.id, room_data.coordinate_y)
    await RoomService()._build(db_session=async_session, obj_in=room_data)

    storage = await _storage_row(async_session, vault.id)
    assert storage is not None, "Storage should be created when building storage room"
    assert storage.max_space == 30, f"Expected storage max_space to be 30, got {storage.max_space}"
    assert storage.max_space == initial_max_space + 30


async def test_building_living_room_without_capacity_formula_computes_capacity(async_session: AsyncSession) -> None:
    vault = await _user_vault(async_session)
    initial_population_max = vault.population_max
    # Deliberately omit capacity_formula and capacity — backend should derive both.
    room_data = RoomCreate(**(_LIVING | {"base_cost": 100}), vault_id=vault.id, coordinate_x=1, coordinate_y=2)
    await _add_elevator_on_level(async_session, vault.id, room_data.coordinate_y)
    await _add_elevator_on_level(async_session, vault.id, room_data.coordinate_y)
    created_room, _ = await RoomService()._build(db_session=async_session, obj_in=room_data)

    await async_session.refresh(vault)
    assert created_room.capacity == 8, "backend derives 2*S/3*(L+4)-2"
    assert vault.population_max == initial_population_max + 8


async def test_upgrading_living_room_grows_population_capacity(async_session: AsyncSession) -> None:
    vault = await _user_vault(async_session, caps=10_000)
    initial_population_max = vault.population_max or 0
    room_data = RoomCreate(
        **(_LIVING | {"capacity_formula": "2*S/3*(L+4)-2"}), vault_id=vault.id, coordinate_x=1, coordinate_y=1
    )
    await _add_elevator_on_level(async_session, vault.id, room_data.coordinate_y)
    await RoomService()._build(db_session=async_session, obj_in=room_data)

    await async_session.refresh(vault)
    assert vault.population_max == initial_population_max + 8, "a tier 1 living room houses 8"

    room = await _first_room(async_session, vault.id, "Living room")
    await RoomService().upgrade_room(async_session, room.id)

    await async_session.refresh(room)
    await async_session.refresh(vault)
    assert room.capacity == 10, "tier 2 follows 2*S/3*(L+4)-2 at L=2"
    assert vault.population_max == initial_population_max + 10, "the room replaces its old 8, not adds to it"


async def test_create_rejects_seeded_vault_number(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    reserved = min(get_seeded_vault_numbers())
    reserved_in = VaultCreateWithUserID(**create_fake_vault() | {"number": reserved}, user_id=user.id)

    with pytest.raises(ValidationException, match="reserved"):
        await crud.vault.create(async_session, obj_in=reserved_in)
    with pytest.raises(ValidationException, match="reserved"):
        await crud.vault.create_with_user_id(db_session=async_session, obj_in=reserved_in, user_id=user.id)

    allowed = await crud.vault.create(
        async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id)
    )
    assert allowed.number not in get_seeded_vault_numbers()


@pytest.mark.parametrize(
    ("segments", "target_tier", "expected_capacity"),
    [(1, 1, 30), (1, 2, 45), (1, 3, 60), (2, 1, 60), (2, 2, 90), (2, 3, 120), (3, 1, 90), (3, 2, 135), (3, 3, 180)],
)
async def test_storage_capacity_matches_room_width_and_tier(
    async_session: AsyncSession, segments: int, target_tier: int, expected_capacity: int
) -> None:
    vault = await _user_vault(async_session)
    vault.bottle_caps = 900_000
    async_session.add(vault)
    await async_session.commit()
    await _add_elevator_on_level(async_session, vault.id, 1)
    service = RoomService()
    for x in range(1, segments * 3 + 1, 3):
        await service._build(db_session=async_session, obj_in=_storage_room(vault.id, x=x, y=1))

    room = await _first_room(async_session, vault.id, "Storage room")
    for _ in range(target_tier - 1):
        await service.upgrade_room(async_session, room.id)

    await async_session.refresh(room)
    storage = await _storage_row(async_session, vault.id)
    await async_session.refresh(storage)

    assert room.size == segments * 3
    assert room.capacity == expected_capacity
    assert storage.max_space == expected_capacity


async def test_vault_dweller_count_matches_living_population(async_session: AsyncSession) -> None:
    # A vault at its cap holding a dead and a soft-deleted dweller must not render over capacity.
    vault = await _user_vault(async_session)
    await _dweller(async_session, vault)
    dead = await _dweller(async_session, vault)
    soft_deleted = await _dweller(async_session, vault)
    dead.is_dead = True
    soft_deleted.is_deleted = True
    async_session.add_all([dead, soft_deleted])
    await async_session.commit()

    row = await crud.vault.get_vault_count_row(db_session=async_session, vault_id=vault.id)
    living_count = await crud.dweller.count_living_in_vault(async_session, vault.id)

    assert living_count == 1, "only the living dweller counts"
    assert row.dweller_count == living_count, "displayed population must exclude the dead and soft-deleted"


async def test_backfilling_merged_capacity_rooms_keeps_vault_totals_current(async_session: AsyncSession) -> None:
    # The seed and the merge-rooms command fuse stored rooms, so totals must follow.
    vault = await _user_vault(async_session)
    # Two adjacent tier 1 living rooms, summed the way the vault seed sums them: 8 each, so 16.
    for x in (1, 4):
        await crud.room.create(
            async_session, RoomCreate(**(_LIVING | {"capacity": 8}), vault_id=vault.id, coordinate_x=x, coordinate_y=1)
        )
    vault.population_max = 16
    async_session.add(vault)
    await async_session.commit()

    merged = await RoomService().backfill_merge_rooms_for_vault(async_session, vault.id, dry_run=False)
    assert merged["merged"] == 1

    survivor = await _first_room(async_session, vault.id, "Living room")
    await async_session.refresh(survivor)
    refreshed_vault = await async_session.get(Vault, vault.id)

    assert survivor.size == 6, "the two rooms fused"
    assert survivor.capacity == 18, "the survivor follows 2*S/3*(L+4)-2 at S=6, not blank"
    assert refreshed_vault.population_max == 18, "the vault replaces the fused rooms' 16 with the survivor's 18"
