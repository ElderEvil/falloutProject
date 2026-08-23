"""Tests for breeding service logic."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import (
    AgeGroupEnum,
    GenderEnum,
    PregnancyStatusEnum,
    RarityEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.schemas.dweller import SPECIAL_STATS, DwellerCreate
from app.schemas.room import RoomCreate
from app.services.breeding_service import BreedingService


@pytest_asyncio.fixture(name="living_quarters")
async def living_quarters_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    """Create a living quarters room for testing."""
    room_data = {
        "name": "Living Quarters",
        "category": RoomTypeEnum.CAPACITY,
        "ability": SPECIALEnum.CHARISMA,
        "population_required": None,
        "base_cost": 100,
        "incremental_cost": 50,
        "t2_upgrade_cost": 500,
        "t3_upgrade_cost": 1500,
        "capacity": 6,
        "output": None,
        "size_min": 1,
        "size_max": 3,
        "size": 2,
        "tier": 1,
        "coordinate_x": 0,
        "coordinate_y": 0,
        "image_url": None,
    }
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    return await crud.room.create(db_session=async_session, obj_in=room_in)


@pytest_asyncio.fixture(name="male_dweller")
async def male_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a male dweller for breeding tests."""
    dweller_data = {
        "first_name": "John",
        "last_name": "Smith",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "level": 10,
        "experience": 100,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 75,
        "strength": 6,
        "perception": 5,
        "endurance": 7,
        "charisma": 5,
        "intelligence": 4,
        "agility": 6,
        "luck": 5,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="male_dweller_2")
async def male_dweller_2_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a second male dweller for same-sex couple breeding tests."""
    dweller_data = {
        "first_name": "Mike",
        "last_name": "Rogers",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "level": 7,
        "experience": 70,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 70,
        "strength": 7,
        "perception": 4,
        "endurance": 6,
        "charisma": 6,
        "intelligence": 5,
        "agility": 5,
        "luck": 6,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="female_dweller")
async def female_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a female dweller for breeding tests."""
    dweller_data = {
        "first_name": "Jane",
        "last_name": "Smith",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.RARE,
        "age_group": AgeGroupEnum.ADULT,
        "level": 8,
        "experience": 80,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 80,
        "strength": 4,
        "perception": 7,
        "endurance": 5,
        "charisma": 8,
        "intelligence": 6,
        "agility": 5,
        "luck": 7,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="female_dweller_2")
async def female_dweller_2_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a second female dweller for population-capacity breeding tests."""
    dweller_data = {
        "first_name": "Sarah",
        "last_name": "Rogers",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "level": 6,
        "experience": 60,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 65,
        "strength": 5,
        "perception": 6,
        "endurance": 5,
        "charisma": 7,
        "intelligence": 5,
        "agility": 6,
        "luck": 5,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest.mark.asyncio
async def test_create_pregnancy(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test creating a pregnancy."""
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    assert pregnancy is not None
    assert pregnancy.mother_id == female_dweller.id
    assert pregnancy.father_id == male_dweller.id
    assert pregnancy.status == PregnancyStatusEnum.PREGNANT

    # Check duration is correct
    duration = (pregnancy.due_at - pregnancy.conceived_at).total_seconds() / 3600
    assert duration == pytest.approx(game_config.breeding.pregnancy_duration_hours, abs=0.1)


@pytest.mark.asyncio
async def test_create_pregnancy_missing_mother(
    async_session: AsyncSession,
    male_dweller: Dweller,
):
    """create_pregnancy raises ValueError when mother not found."""
    from uuid import uuid4

    with pytest.raises(ValueError, match="Mother not found"):
        await BreedingService.create_pregnancy(async_session, uuid4(), male_dweller.id)


@pytest.mark.asyncio
async def test_create_pregnancy_missing_father(
    async_session: AsyncSession,
    female_dweller: Dweller,
):
    """create_pregnancy raises ValueError when father not found."""
    from uuid import uuid4

    with pytest.raises(ValueError, match="Father not found"):
        await BreedingService.create_pregnancy(async_session, female_dweller.id, uuid4())


@pytest.mark.asyncio
async def test_create_pregnancy_mother_not_adult(
    async_session: AsyncSession,
    vault: Vault,
    male_dweller: Dweller,
):
    """create_pregnancy raises ValueError when mother is not an adult."""
    child_in = DwellerCreate(
        first_name="Kid",
        last_name="Test",
        gender=GenderEnum.FEMALE,
        rarity=RarityEnum.COMMON,
        age_group=AgeGroupEnum.CHILD,
        birth_date=datetime.utcnow(),
        vault_id=vault.id,
    )
    child = await crud.dweller.create(db_session=async_session, obj_in=child_in)
    with pytest.raises(ValueError, match="Mother must be an adult"):
        await BreedingService.create_pregnancy(async_session, child.id, male_dweller.id)


@pytest.mark.asyncio
async def test_create_pregnancy_father_not_adult(
    async_session: AsyncSession,
    vault: Vault,
    female_dweller: Dweller,
):
    """create_pregnancy raises ValueError when father is not an adult."""
    child_in = DwellerCreate(
        first_name="Kid",
        last_name="Test",
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        age_group=AgeGroupEnum.CHILD,
        birth_date=datetime.utcnow(),
        vault_id=vault.id,
    )
    child = await crud.dweller.create(db_session=async_session, obj_in=child_in)
    with pytest.raises(ValueError, match="Father must be an adult"):
        await BreedingService.create_pregnancy(async_session, female_dweller.id, child.id)


@pytest.mark.asyncio
async def test_create_pregnancy_mother_not_female(
    async_session: AsyncSession,
    male_dweller: Dweller,
):
    """create_pregnancy raises ValueError when mother is not female."""
    with pytest.raises(ValueError, match="Mother must be female"):
        await BreedingService.create_pregnancy(async_session, male_dweller.id, male_dweller.id)


@pytest.mark.asyncio
async def test_create_pregnancy_father_not_male(
    async_session: AsyncSession,
    female_dweller: Dweller,
):
    """create_pregnancy raises ValueError when father is not male."""
    with pytest.raises(ValueError, match="Father must be male"):
        await BreedingService.create_pregnancy(async_session, female_dweller.id, female_dweller.id)


@pytest.mark.asyncio
async def test_check_for_conception_no_partners(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
):
    """Test that no conception occurs when dwellers are not partners."""
    pregnancies = await BreedingService.check_for_conception(
        async_session,
        vault.id,
    )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_check_for_conception_not_in_living_quarters(
    async_session: AsyncSession,
    vault: Vault,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that conception doesn't occur outside living quarters."""
    # Make them partners
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id

    # Don't assign to living quarters (room_id is None)
    await async_session.commit()

    pregnancies = await BreedingService.check_for_conception(
        async_session,
        vault.id,
    )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_check_for_conception_in_living_quarters(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test conception can occur in living quarters."""
    # Make them partners
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id

    # Assign to living quarters
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = living_quarters.id
    await async_session.commit()

    # Mock random to always succeed
    with patch("random.random", return_value=0.0):  # Always less than CONCEPTION_CHANCE_PER_TICK
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    assert len(pregnancies) == 1
    assert pregnancies[0].mother_id == female_dweller.id
    assert pregnancies[0].father_id == male_dweller.id


@pytest.mark.asyncio
async def test_check_for_conception_same_sex_couple_never_conceives(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    male_dweller_2: Dweller,
):
    """Test that a same-sex partner couple never conceives, even at high affinity.

    Same-sex couples may form (partner/MARRIED) but cannot reproduce — this is a
    deliberate Fallout-universe / vault-logic rule. Auto-conception must skip the
    pair regardless of affinity.
    """
    # Make them partners in living quarters
    male_dweller.partner_id = male_dweller_2.id
    male_dweller_2.partner_id = male_dweller.id
    male_dweller.room_id = living_quarters.id
    male_dweller_2.room_id = living_quarters.id
    await async_session.commit()

    from app.crud.relationship import relationship_crud
    from app.schemas.common import RelationshipTypeEnum

    await relationship_crud.create_with_defaults(
        async_session,
        male_dweller.id,
        male_dweller_2.id,
        relationship_type=RelationshipTypeEnum.MARRIED,
        affinity=100,
    )

    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_check_for_conception_already_pregnant(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that already pregnant dwellers don't conceive again."""
    # Make them partners in living quarters
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = living_quarters.id
    await async_session.commit()

    # Create existing pregnancy
    await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    # Try to conceive again
    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    # Should not create new pregnancy
    assert pregnancies == []


@pytest.mark.asyncio
async def test_check_for_conception_postpartum_cooldown(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that mothers who recently delivered can't conceive again within cooldown."""
    # Make them partners in living quarters
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = living_quarters.id
    await async_session.commit()

    # Deliver a pregnancy now (within cooldown window)
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )
    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()
    await BreedingService.deliver_baby(async_session, pregnancy.id)

    # Try to conceive again while still in the postpartum cooldown
    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_check_for_conception_after_cooldown_expires(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that mothers can conceive again once the postpartum cooldown expires."""
    # Make them partners in living quarters
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = living_quarters.id
    await async_session.commit()

    # Deliver a pregnancy, then backdate the delivery outside the cooldown window
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )
    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()
    await BreedingService.deliver_baby(async_session, pregnancy.id)

    pregnancy.updated_at = datetime.utcnow() - timedelta(hours=game_config.breeding.birth_cooldown_hours + 1)
    await async_session.commit()

    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    assert len(pregnancies) == 1
    assert pregnancies[0].mother_id == female_dweller.id


@pytest.mark.asyncio
async def test_check_for_conception_only_one_in_living_quarters(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that both partners must be in living quarters."""
    # Make them partners
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id

    # Only assign male to living quarters
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = None
    await async_session.commit()

    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_check_for_conception_at_capacity(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """No new conception when the vault population is exactly at capacity.

    Regression guard: check_for_conception must refuse new conceptions once
    the vault population reaches population_max, even for an eligible couple
    with a guaranteed-successful conception roll.
    """
    # Make them partners in living quarters (eligible couple)
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = living_quarters.id
    await async_session.commit()

    # The vault holds exactly these 2 dwellers -> population_max of 2 is at capacity
    vault.population_max = 2
    async_session.add(vault)
    await async_session.commit()

    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_check_for_conception_over_capacity(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """No new conception when the vault population is already over capacity."""
    # Make them partners in living quarters (eligible couple)
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = living_quarters.id
    await async_session.commit()

    # 2 dwellers with population_max of 1 -> over capacity
    vault.population_max = 1
    async_session.add(vault)
    await async_session.commit()

    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_check_for_conception_one_slot_allows_single(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Exactly one free population slot allows exactly one conception."""
    # Make them partners in living quarters (eligible couple)
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = living_quarters.id
    await async_session.commit()

    # 2 dwellers, population_max of 3 -> exactly one free slot
    vault.population_max = 3
    async_session.add(vault)
    await async_session.commit()

    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    assert len(pregnancies) == 1
    assert pregnancies[0].mother_id == female_dweller.id
    assert pregnancies[0].father_id == male_dweller.id


@pytest.mark.asyncio
async def test_check_for_conception_reserves_for_committed_pregnancies(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
    male_dweller_2: Dweller,
    female_dweller_2: Dweller,
):
    """A committed pregnancy reserves the last free population slot.

    The eligible couple (male+female) would otherwise conceive, but the vault
    already has a PREGNANT mother whose committed pregnancy counts toward
    capacity: one free slot minus one committed pregnancy leaves no room, so
    no new conception may occur.
    """
    # Eligible couple in living quarters
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = living_quarters.id
    await async_session.commit()

    # Second mother is already carrying a committed pregnancy
    await BreedingService.create_pregnancy(
        async_session,
        female_dweller_2.id,
        male_dweller_2.id,
    )

    # 4 dwellers, population_max of 5 -> one free slot, consumed by the committed pregnancy
    vault.population_max = 5
    async_session.add(vault)
    await async_session.commit()

    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_check_for_conception_single_slot_limits_pairs(
    async_session: AsyncSession,
    vault: Vault,
    living_quarters: Room,
    male_dweller: Dweller,
    female_dweller: Dweller,
    male_dweller_2: Dweller,
    female_dweller_2: Dweller,
):
    """A single free slot allows at most one conception even with two couples."""
    # Two eligible couples in the same living quarters
    male_dweller.partner_id = female_dweller.id
    female_dweller.partner_id = male_dweller.id
    male_dweller_2.partner_id = female_dweller_2.id
    female_dweller_2.partner_id = male_dweller_2.id
    male_dweller.room_id = living_quarters.id
    female_dweller.room_id = living_quarters.id
    male_dweller_2.room_id = living_quarters.id
    female_dweller_2.room_id = living_quarters.id
    await async_session.commit()

    # 4 dwellers, population_max of 5 -> exactly one free slot
    vault.population_max = 5
    async_session.add(vault)
    await async_session.commit()

    with patch("random.random", return_value=0.0):
        pregnancies = await BreedingService.check_for_conception(
            async_session,
            vault.id,
        )

    # Both couples have guaranteed-successful rolls, but the single free slot
    # caps the tick at exactly one conception.
    assert len(pregnancies) == 1


@pytest.mark.asyncio
async def test_check_due_pregnancies_none_due(
    async_session: AsyncSession,
    vault: Vault,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test checking for due pregnancies when none are due."""
    # Create pregnancy that's not due yet
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    due_pregnancies = await BreedingService.check_due_pregnancies(
        async_session,
        vault.id,
    )

    assert due_pregnancies == []


@pytest.mark.asyncio
async def test_check_due_pregnancies_one_due(
    async_session: AsyncSession,
    vault: Vault,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test checking for due pregnancies when one is due."""
    # Create pregnancy
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    # Manipulate due date to be in the past
    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    due_pregnancies = await BreedingService.check_due_pregnancies(
        async_session,
        vault.id,
    )

    assert len(due_pregnancies) == 1
    assert due_pregnancies[0].id == pregnancy.id


@pytest.mark.asyncio
async def test_deliver_baby_not_due_fails(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that delivery fails if pregnancy not due."""
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    with pytest.raises(ValueError, match="not due yet"):
        await BreedingService.deliver_baby(
            async_session,
            pregnancy.id,
        )


@pytest.mark.asyncio
async def test_deliver_baby_success(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test successful baby delivery."""
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    # Make pregnancy due
    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    # Deliver baby
    child = await BreedingService.deliver_baby(
        async_session,
        pregnancy.id,
    )

    assert child is not None
    assert child.age_group == AgeGroupEnum.CHILD
    assert child.birth_date is not None
    assert child.parent_1_id == female_dweller.id
    assert child.parent_2_id == male_dweller.id
    assert child.vault_id == female_dweller.vault_id

    # Check pregnancy status updated
    await async_session.refresh(pregnancy)
    assert pregnancy.status == PregnancyStatusEnum.DELIVERED


@pytest.mark.asyncio
async def test_deliver_baby_inherits_stats(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that baby inherits stats from parents."""
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    child = await BreedingService.deliver_baby(
        async_session,
        pregnancy.id,
    )

    # Check that child stats are roughly averaged from parents
    # Father strength: 6, Mother strength: 4, Average: 5
    # With variance of ±2 and child multiplier of 0.5, should be in range
    assert 1 <= child.strength <= 10
    assert 1 <= child.charisma <= 10

    # All SPECIAL stats should be valid
    special_attrs = SPECIAL_STATS
    for attr in special_attrs:
        stat = getattr(child, attr)
        assert 1 <= stat <= 10


@pytest.mark.asyncio
async def test_deliver_baby_inherits_rarity(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that baby inherits rarity from parents."""
    # Male is COMMON, Female is RARE
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    child = await BreedingService.deliver_baby(
        async_session,
        pregnancy.id,
    )

    # Child should be at least RARE (highest parent rarity)
    rarity_order = [RarityEnum.COMMON, RarityEnum.RARE, RarityEnum.LEGENDARY]
    child_rarity_idx = rarity_order.index(child.rarity)

    # Should be at least RARE (index 1)
    assert child_rarity_idx >= 1


@pytest.mark.asyncio
async def test_deliver_baby_random_gender(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that baby gender is random."""
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    child = await BreedingService.deliver_baby(
        async_session,
        pregnancy.id,
    )

    # Gender should be valid
    assert child.gender in [GenderEnum.MALE, GenderEnum.FEMALE]


@pytest.mark.asyncio
async def test_deliver_baby_inherits_name(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that baby inherits name from parents."""
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    with patch("random.random", return_value=0.99):
        child = await BreedingService.deliver_baby(
            async_session,
            pregnancy.id,
        )

    # First name should be from one of the parents
    assert child.first_name in [male_dweller.first_name, female_dweller.first_name]

    # Father's last name is the default inheritance
    assert child.last_name == male_dweller.last_name


@pytest.mark.asyncio
async def test_deliver_baby_inherits_mother_last_name_on_chance(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that baby occasionally inherits mother's last name."""
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    pregnancy.due_at = datetime.utcnow() - timedelta(hours=1)
    await async_session.commit()

    # random.random < maternal_last_name_chance (0.2) triggers mother's last name
    with patch("random.random", return_value=0.1):
        child = await BreedingService.deliver_baby(
            async_session,
            pregnancy.id,
        )

    assert child.last_name == female_dweller.last_name


@pytest.mark.asyncio
async def test_age_children_no_children(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test aging children when there are no children."""
    aged = await BreedingService.age_children(
        async_session,
        vault.id,
    )

    assert aged == []


@pytest.mark.asyncio
async def test_age_children_not_old_enough(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test that children not old enough are not aged."""
    # Create child dweller
    child_data = {
        "first_name": "Baby",
        "last_name": "Test",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.CHILD,
        "birth_date": datetime.utcnow(),  # Just born
        "level": 1,
        "experience": 0,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 50,
        "strength": 2,
        "perception": 2,
        "endurance": 2,
        "charisma": 2,
        "intelligence": 2,
        "agility": 2,
        "luck": 2,
    }
    child_in = DwellerCreate(**child_data, vault_id=vault.id)
    child = await crud.dweller.create(db_session=async_session, obj_in=child_in)

    aged = await BreedingService.age_children(
        async_session,
        vault.id,
    )

    assert aged == []

    # Child should still be child
    await async_session.refresh(child)
    assert child.age_group == AgeGroupEnum.CHILD


@pytest.mark.asyncio
async def test_age_children_old_enough(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test that children old enough are aged to adults."""
    # Create child dweller with birth date in the past
    birth_date = datetime.utcnow() - timedelta(hours=game_config.breeding.child_growth_duration_hours + 1)

    child_data = {
        "first_name": "Baby",
        "last_name": "Test",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.CHILD,
        "is_adult": False,
        "birth_date": birth_date,
        "level": 1,
        "experience": 0,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 50,
        "strength": 3,
        "perception": 3,
        "endurance": 3,
        "charisma": 3,
        "intelligence": 3,
        "agility": 3,
        "luck": 3,
    }
    child_in = DwellerCreate(**child_data, vault_id=vault.id)
    child = await crud.dweller.create(db_session=async_session, obj_in=child_in)

    aged = await BreedingService.age_children(
        async_session,
        vault.id,
    )

    assert len(aged) == 1
    assert aged[0].id == child.id

    # Child should now be a working adult: age group AND adult flag flip together
    await async_session.refresh(child)
    assert child.age_group == AgeGroupEnum.ADULT
    assert child.is_adult is True

    # Stats should be scaled up (3 / 0.5 = 6)
    assert child.strength == 6
    assert child.charisma == 6


@pytest.mark.asyncio
async def test_get_active_pregnancies_none(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test getting active pregnancies when there are none."""
    pregnancies = await BreedingService.get_active_pregnancies(
        async_session,
        vault.id,
    )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_get_active_pregnancies(
    async_session: AsyncSession,
    vault: Vault,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test getting active pregnancies."""
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    pregnancies = await BreedingService.get_active_pregnancies(
        async_session,
        vault.id,
    )

    assert len(pregnancies) == 1
    assert pregnancies[0].id == pregnancy.id


@pytest.mark.asyncio
async def test_get_active_pregnancies_excludes_delivered(
    async_session: AsyncSession,
    vault: Vault,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that delivered pregnancies are not included."""
    pregnancy = await BreedingService.create_pregnancy(
        async_session,
        female_dweller.id,
        male_dweller.id,
    )

    # Mark as delivered
    pregnancy.status = PregnancyStatusEnum.DELIVERED
    await async_session.commit()

    pregnancies = await BreedingService.get_active_pregnancies(
        async_session,
        vault.id,
    )

    assert pregnancies == []


@pytest.mark.asyncio
async def test_calculate_inherited_stats_variance(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test that stat inheritance includes variance."""
    # Run multiple times to test variance
    stats_list = []
    for _ in range(10):
        stats = BreedingService._calculate_inherited_stats(male_dweller, female_dweller)
        stats_list.append(stats)

    # Should have some variance in results
    strength_values = [s["strength"] for s in stats_list]

    # All should be valid (1-10)
    assert all(1 <= s <= 10 for s in strength_values)


@pytest.mark.asyncio
async def test_calculate_inherited_rarity_upgrade_chance(
    async_session: AsyncSession,
    male_dweller: Dweller,
    female_dweller: Dweller,
):
    """Test rarity inheritance with upgrade chance."""
    # Run multiple times to test upgrade chance
    rarities = []
    for _ in range(50):
        rarity = BreedingService._calculate_inherited_rarity(male_dweller, female_dweller)
        rarities.append(rarity)

    # Should all be at least RARE (highest parent)
    rarity_order = [RarityEnum.COMMON, RarityEnum.RARE, RarityEnum.LEGENDARY]

    for rarity in rarities:
        rarity_idx = rarity_order.index(rarity)
        assert rarity_idx >= 1  # At least RARE


@pytest.mark.asyncio
async def test_deliver_baby_pregnancy_not_found(
    async_session: AsyncSession,
):
    """Test delivery fails if pregnancy not found."""
    from uuid import uuid4

    fake_id = uuid4()

    with pytest.raises(ValueError, match="Pregnancy not found"):
        await BreedingService.deliver_baby(
            async_session,
            fake_id,
        )


def test_generate_newborn_bio_format():
    """Test that newborn bio format works correctly."""
    from unittest.mock import patch

    from app.services.breeding_service import _generate_newborn_bio

    with patch("app.services.breeding_service.random.choice") as mock_choice:
        mock_choice.side_effect = [
            "Born during a {event}. {mother} and {father} couldn't be prouder.",
            "a vault celebration",
        ]
        bio = _generate_newborn_bio(
            mother_name="Jane",
            father_name="John",
            mother_id="mother-123",
            father_id="father-456",
            vault_id="vault-789",
        )

    assert "Jane" in bio
    assert "John" in bio
    assert 'href="/vault/vault-789/dwellers/mother-123"' in bio
    assert 'href="/vault/vault-789/dwellers/father-456"' in bio


def test_breeding_config_values():
    """Test that breeding config has valid values."""
    from app.core.game_config import game_config

    assert 0.0 <= game_config.breeding.conception_chance_per_tick <= 1.0
    assert game_config.breeding.pregnancy_duration_hours > 0
    assert game_config.breeding.child_growth_duration_hours > 0
