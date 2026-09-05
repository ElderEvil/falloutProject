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
from app.schemas.dweller import DwellerCreate, DwellerCreateCommonOverride
from app.schemas.room import RoomCreate
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.tests.factory.rooms import create_fake_room
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.dwellers import create_random_common_dweller
from app.utils.exceptions import (
    ContentNoChangeException,
    InvalidVaultTransferException,
    ResourceConflictException,
    ValidationException,
)
from backend.app.tests.factory.dwellers import create_fake_dweller

RACE_VALUES = {race.value for race in RaceOption}


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
    assert dweller.status.value == "idle"  # Default status should be IDLE

    profile = await profile_crud.get_by_user_id(async_session, user.id)
    assert profile is not None
    assert profile.total_dwellers_created == 1


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

    # Seeded random dweller: race ∈ RaceOption, faction valid for that race.
    dweller = await crud.dweller.create_random(db_session=async_session, vault_id=vault.id, seed=42)
    assert dweller.id
    assert dweller.vault_id == vault.id  # Check vault association
    assert dweller.visual_attributes is not None
    race = dweller.visual_attributes.get("race")
    faction = dweller.visual_attributes.get("faction")
    assert race in RACE_VALUES
    assert faction in faction_restrictions[RaceOption(race)]

    # Create a random dweller with a special boost override
    special_stat = random.choice(list(SPECIALEnum))
    override = DwellerCreateCommonOverride(special_boost=special_stat)
    dweller_boosted = await crud.dweller.create_random(db_session=async_session, obj_in=override, vault_id=vault.id)
    assert dweller_boosted.id
    assert dweller_boosted.vault_id == vault.id  # Check vault association
    assert getattr(dweller_boosted, special_stat.value.lower()) == game_config.dweller.boosted_stat_value
    assert dweller_boosted.visual_attributes is not None
    boosted_race = dweller_boosted.visual_attributes.get("race")
    assert boosted_race in RACE_VALUES
    assert dweller_boosted.visual_attributes.get("faction") in faction_restrictions[RaceOption(boosted_race)]

    # Diversity policy (70/15/10/5): 200 seeded draws must surface every race.
    races_seen: set[str] = set()
    for seed in range(200):
        attrs = create_random_common_dweller(seed=seed)["visual_attributes"]
        assert attrs["race"] in RACE_VALUES
        assert attrs["faction"] in faction_restrictions[RaceOption(attrs["race"])]
        races_seen.add(attrs["race"])
    assert races_seen == RACE_VALUES


@pytest.mark.asyncio
async def test_create_random_common_dweller_seed_deterministic(async_session: AsyncSession):
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    # Same seed → identical dweller fields
    d1 = await crud.dweller.create_random(db_session=async_session, vault_id=vault.id, seed=42)
    d2 = await crud.dweller.create_random(db_session=async_session, vault_id=vault.id, seed=42)
    assert d1.first_name == d2.first_name
    assert d1.last_name == d2.last_name
    assert d1.gender == d2.gender
    assert d1.is_adult == d2.is_adult
    assert d1.strength == d2.strength
    assert d1.luck == d2.luck
    assert d1.age_group == d2.age_group
    assert d1.birth_date == d2.birth_date

    # Different seed → different output (overwhelmingly likely across all fields)
    d3 = await crud.dweller.create_random(db_session=async_session, vault_id=vault.id, seed=43)
    differing = [
        d3.first_name != d1.first_name,
        d3.last_name != d1.last_name,
        d3.gender != d1.gender,
        d3.is_adult != d1.is_adult,
        d3.strength != d1.strength,
        d3.luck != d1.luck,
    ]
    assert any(differing)


@pytest.mark.asyncio
async def test_create_random_common_dweller_age_fields_coherent(async_session: AsyncSession):
    """Procedurally generated dwellers are adult recruits with coherent age fields."""
    from app.utils.dwellers import _calendar_years_ago, create_random_common_dweller

    for _ in range(40):
        data = create_random_common_dweller()
        assert data["is_adult"] is True
        assert data["age_group"] == AgeGroupEnum.ADULT
        assert data["birth_date"] is not None
        assert data["birth_date"] <= _calendar_years_ago(datetime.now(UTC).replace(tzinfo=None), 18)
        assert data["max_health"] == 100
        assert data["health"] == 100


@pytest.mark.asyncio
async def test_create_random_common_dweller_persisted_age_coherent(async_session: AsyncSession):
    """Regression (DB-level): persisted random dwellers have coherent age fields."""
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    from app.utils.dwellers import _calendar_years_ago

    adult_cutoff = _calendar_years_ago(datetime(2000, 1, 1), 18)
    for seed in range(10):
        dweller = await crud.dweller.create_random(db_session=async_session, vault_id=vault.id, seed=seed)
        assert dweller.is_adult is True
        assert dweller.age_group == AgeGroupEnum.ADULT
        assert dweller.birth_date is not None
        assert dweller.birth_date <= adult_cutoff
        assert dweller.max_health == 100
        assert dweller.health == 100


@pytest.mark.asyncio
async def test_create_random_registers_bio_places(async_session: AsyncSession) -> None:
    """create_random registers the bio origin + visited places on the world map."""
    from sqlmodel import select

    from app.models.wasteland_location import LocationTypeEnum, WastelandLocation

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller = await crud.dweller.create_random(db_session=async_session, vault_id=vault.id, seed=1)
    assert dweller.bio

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    origin_rows = [r for r in rows if r.type == LocationTypeEnum.ORIGIN]
    visited_rows = [r for r in rows if r.type == LocationTypeEnum.VISITED]
    # seed=1 → rarity COMMON → max_visited 2
    assert len(origin_rows) == 1
    assert len(visited_rows) == 2


@pytest.mark.asyncio
async def test_create_random_skip_bio_places(async_session: AsyncSession) -> None:
    """register_bio_places=False creates the dweller but registers no map rows."""
    from sqlmodel import select

    from app.models.wasteland_location import WastelandLocation

    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)
    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller = await crud.dweller.create_random(
        db_session=async_session, vault_id=vault.id, seed=1, register_bio_places=False
    )
    assert dweller.bio

    rows = (await async_session.execute(select(WastelandLocation))).scalars().all()
    assert len(rows) == 0


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
async def test_move_child_to_arena_rejected(async_session: AsyncSession):
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)
    dweller.is_adult = False
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

    with pytest.raises(ValidationException) as exc_info:
        await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=arena_room.id)
    assert "Only adult dwellers can fight in the Arena" in str(exc_info.value)


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
async def test_move_adult_to_arena_allowed(async_session: AsyncSession):
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
async def test_dweller_status_on_room_assignment(async_session: AsyncSession):
    """Test that dweller status changes when assigned to/removed from a room."""
    from app.schemas.common import DwellerStatusEnum

    # Setup - create user, vault, and dweller
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_data["population_max"] = 200  # Ensure enough space
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Dweller should start as IDLE
    assert dweller.status == DwellerStatusEnum.IDLE

    # Create a production room (not training)
    room_data = create_fake_room()
    room_data["category"] = RoomTypeEnum.PRODUCTION  # Ensure it's a production room for WORKING status
    room = await crud.room.create(async_session, obj_in=RoomCreate(**room_data, vault_id=vault.id))

    # Move dweller to room - should become WORKING
    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.WORKING
    assert dweller.room_id == room.id


@pytest.mark.asyncio
async def test_dweller_status_production_room(async_session: AsyncSession):
    """Test that dwellers in production rooms get WORKING status."""
    from app.schemas.common import DwellerStatusEnum, RoomTypeEnum

    # Setup - create user, vault, and dweller
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_data["population_max"] = 200
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Create a production room
    room_data = create_fake_room()
    room_data["category"] = RoomTypeEnum.PRODUCTION
    room = await crud.room.create(async_session, obj_in=RoomCreate(**room_data, vault_id=vault.id))

    # Move dweller to production room - should become WORKING
    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.WORKING
    assert dweller.room_id == room.id


@pytest.mark.asyncio
async def test_dweller_status_training_room(async_session: AsyncSession):
    """Test that dwellers in training rooms get TRAINING status."""
    from app.schemas.common import DwellerStatusEnum, RoomTypeEnum

    # Setup - create user, vault, and dweller
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_data["population_max"] = 200
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_data["is_adult"] = True
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Create a training room
    room_data = create_fake_room()
    room_data["category"] = RoomTypeEnum.TRAINING
    room = await crud.room.create(async_session, obj_in=RoomCreate(**room_data, vault_id=vault.id))

    # Move dweller to training room - should become TRAINING
    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.TRAINING
    assert dweller.room_id == room.id


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


@pytest.mark.asyncio
async def test_dweller_status_on_unassign(async_session: AsyncSession):
    """Test that dweller status becomes IDLE when unassigned from room via update."""
    from app.schemas.common import DwellerStatusEnum, RoomTypeEnum
    from app.schemas.dweller import DwellerUpdate

    # Setup - create user, vault, and dweller
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_data["population_max"] = 200
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Create a production room and assign dweller
    room_data = create_fake_room()
    room_data["category"] = RoomTypeEnum.PRODUCTION
    room = await crud.room.create(async_session, obj_in=RoomCreate(**room_data, vault_id=vault.id))

    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.WORKING
    assert dweller.room_id == room.id

    # Unassign dweller by setting room_id to None via update
    await crud.dweller.update(async_session, dweller.id, DwellerUpdate(room_id=None, status=DwellerStatusEnum.IDLE))
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.IDLE
    assert dweller.room_id is None


@pytest.mark.asyncio
async def test_dweller_status_on_room_reassignment(async_session: AsyncSession):
    """Test that dweller status changes correctly when moved between different room types."""
    from app.schemas.common import DwellerStatusEnum, RoomTypeEnum

    # Setup
    user_data = create_fake_user()
    user_in = UserCreate(**user_data)
    user = await crud.user.create(async_session, obj_in=user_in)

    vault_data = create_fake_vault()
    vault_data["population_max"] = 200
    vault_in = VaultCreateWithUserID(**vault_data, user_id=user.id)
    vault = await crud.vault.create(async_session, obj_in=vault_in)

    dweller_data = create_fake_dweller()
    dweller_data.update(is_adult=True, age_group=AgeGroupEnum.ADULT)
    dweller_in = DwellerCreate(**dweller_data, vault_id=str(vault.id))
    dweller = await crud.dweller.create(async_session, obj_in=dweller_in)

    # Create production room and training room
    production_room_data = create_fake_room()
    production_room_data["category"] = RoomTypeEnum.PRODUCTION
    production_room = await crud.room.create(
        async_session, obj_in=RoomCreate(**production_room_data, vault_id=vault.id)
    )

    training_room_data = create_fake_room()
    training_room_data["category"] = RoomTypeEnum.TRAINING
    training_room = await crud.room.create(async_session, obj_in=RoomCreate(**training_room_data, vault_id=vault.id))

    # Assign to production room
    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=production_room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.WORKING

    # Move to training room
    await crud.dweller.move_to_room(async_session, dweller_id=dweller.id, room_id=training_room.id)
    await async_session.refresh(dweller)
    assert dweller.status == DwellerStatusEnum.TRAINING


@pytest.mark.asyncio
async def test_create_from_template_reservation_conflict(async_session: AsyncSession) -> None:
    """Second create_from_template for the same vault raises ResourceConflictException.

    The reservation lives in the shared _create_template flow (vault row lock +
    active-name check), so direct callers cannot bypass per-vault uniqueness.
    """
    user_data = create_fake_user()
    user = await crud.user.create(async_session, obj_in=UserCreate(**user_data))
    vault_data = create_fake_vault()
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**vault_data, user_id=user.id))

    first = await crud.dweller.create_from_template(async_session, vault.id, "abraham-washington")
    assert first.first_name == "Abraham"

    with pytest.raises(ResourceConflictException, match="already active"):
        await crud.dweller.create_from_template(async_session, vault.id, "abraham-washington")

    dwellers = await crud.dweller.get_multi_by_vault(async_session, vault_id=vault.id)
    curated = [d for d in dwellers if d.first_name == "Abraham" and d.last_name == "Washington"]
    assert len(curated) == 1


async def _make_medical_dweller(async_session: AsyncSession, **overrides):
    """Create a vault dweller with deterministic medical fields."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "max_health": 100,
            "health": 50,
            "radiation": 0,
            "stimpack": 2,
            "radaway": 2,
            **overrides,
        }
    )
    return await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=str(vault.id)))


@pytest.mark.asyncio
async def test_use_stimpack_respects_radiation_cap(async_session: AsyncSession) -> None:
    """A 40% heal stops at max_health minus radiation."""
    dweller = await _make_medical_dweller(async_session, health=50, radiation=20)

    healed = await crud.dweller.use_stimpack(async_session, dweller.id)

    assert healed.health == 80
    assert healed.stimpack == 1


@pytest.mark.asyncio
async def test_use_stimpack_at_radiation_cap_is_no_change(async_session: AsyncSession) -> None:
    """At the radiation cap the stimpack is kept and RadAway is prescribed."""
    dweller = await _make_medical_dweller(async_session, health=80, radiation=20)

    with pytest.raises(ContentNoChangeException, match="RadAway"):
        await crud.dweller.use_stimpack(async_session, dweller.id)

    await async_session.refresh(dweller)
    assert dweller.stimpack == 2


@pytest.mark.asyncio
async def test_use_radaway_removes_half_max_health_without_healing(async_session: AsyncSession) -> None:
    """RadAway capacity is fixed off max health and never restores health."""
    dweller = await _make_medical_dweller(async_session, health=60, radiation=80)

    treated = await crud.dweller.use_radaway(async_session, dweller.id)

    assert treated.radiation == 30
    assert treated.health == 60
    assert treated.radaway == 1


@pytest.mark.asyncio
async def test_use_radaway_clears_single_rad(async_session: AsyncSession) -> None:
    """Low radiation always clears so the item is never wasted."""
    dweller = await _make_medical_dweller(async_session, radiation=1)

    treated = await crud.dweller.use_radaway(async_session, dweller.id)

    assert treated.radiation == 0
