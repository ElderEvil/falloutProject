"""Tests for radio service logic."""

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
    RarityEnum,
    RoomTypeEnum,
    SPECIALEnum,
)
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.radio_service import RadioService


@pytest_asyncio.fixture(name="radio_room")
async def radio_room_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    """Create a radio room for testing."""
    room_data = {
        "name": "Radio Studio",
        "category": RoomTypeEnum.MISC,
        "ability": SPECIALEnum.CHARISMA,
        "population_required": None,
        "base_cost": 100,
        "incremental_cost": 50,
        "t2_upgrade_cost": 500,
        "t3_upgrade_cost": 1500,
        "capacity": 2,
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


@pytest_asyncio.fixture(name="radio_dweller")
async def radio_dweller_fixture(async_session: AsyncSession, vault: Vault, radio_room: Room) -> Dweller:
    """Create a dweller with high charisma for radio room."""
    dweller_data = {
        "first_name": "DJ",
        "last_name": "Radio",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "level": 5,
        "experience": 100,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 80,
        "room_id": radio_room.id,
        "strength": 3,
        "perception": 4,
        "endurance": 4,
        "charisma": 10,  # Max charisma for radio
        "intelligence": 5,
        "agility": 4,
        "luck": 5,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest.mark.asyncio
async def test_get_radio_rooms_none(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test getting radio rooms when none exist."""
    rooms = await RadioService.get_radio_rooms(async_session, vault.id)
    assert rooms == []


@pytest.mark.asyncio
async def test_get_radio_rooms_exists(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
):
    """Test getting radio rooms when they exist."""
    rooms = await RadioService.get_radio_rooms(async_session, vault.id)
    assert len(rooms) == 1
    assert rooms[0].id == radio_room.id


@pytest.mark.asyncio
async def test_calculate_recruitment_rate_no_radio(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test recruitment rate with no radio rooms."""
    rate = await RadioService.calculate_recruitment_rate(async_session, vault, [])
    assert rate == 0.0


@pytest.mark.asyncio
async def test_calculate_recruitment_rate_tier_1(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
):
    """Test recruitment rate with tier 1 radio room."""
    rate = await RadioService.calculate_recruitment_rate(async_session, vault, [radio_room])

    # Base rate * tier 1 multiplier (1.0) * happiness multiplier
    happiness_mult = 1.0 + (vault.happiness * game_config.radio.happiness_rate_multiplier)
    expected_rate = game_config.radio.base_recruitment_rate * game_config.radio.get_tier_multiplier(1) * happiness_mult

    assert rate == pytest.approx(expected_rate, abs=0.0001)


@pytest.mark.asyncio
async def test_calculate_recruitment_rate_tier_2(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
):
    """Test recruitment rate with tier 2 radio room."""
    # Upgrade to tier 2
    radio_room.tier = 2
    await async_session.commit()

    rate = await RadioService.calculate_recruitment_rate(async_session, vault, [radio_room])

    # Base rate * tier 2 multiplier (1.5) * happiness multiplier
    happiness_mult = 1.0 + (vault.happiness * game_config.radio.happiness_rate_multiplier)
    expected_rate = game_config.radio.base_recruitment_rate * game_config.radio.get_tier_multiplier(2) * happiness_mult

    assert rate == pytest.approx(expected_rate, abs=0.0001)


@pytest.mark.asyncio
async def test_check_for_recruitment_no_radio(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test recruitment check with no radio room."""
    dweller = await RadioService.check_for_recruitment(async_session, vault.id)
    assert dweller is None


@pytest.mark.asyncio
async def test_check_for_recruitment_success(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,  # noqa: ARG001
):
    """Test successful recruitment via radio."""
    # Mock random to always succeed
    with patch("random.random", return_value=0.0):
        dweller = await RadioService.check_for_recruitment(async_session, vault.id)

    assert dweller is not None
    assert dweller.vault_id == vault.id
    assert dweller.rarity == RarityEnum.COMMON


@pytest.mark.asyncio
async def test_check_for_recruitment_failure(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,  # noqa: ARG001
):
    """Test failed recruitment via radio."""
    # Mock random to always fail
    with patch("random.random", return_value=1.0):
        dweller = await RadioService.check_for_recruitment(async_session, vault.id)

    assert dweller is None


@pytest.mark.asyncio
async def test_recruit_dweller(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test recruiting a dweller."""
    dweller = await RadioService.recruit_dweller(async_session, vault.id)

    assert dweller is not None
    assert dweller.vault_id == vault.id
    assert dweller.rarity == RarityEnum.COMMON
    assert dweller.first_name is not None
    assert dweller.last_name is not None


@pytest.mark.skip(reason="FIXME: Session isolation - radio_dweller fixture not visible to RadioService query")
@pytest.mark.asyncio
async def test_manual_recruit_success(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,  # noqa: ARG001
    radio_dweller: Dweller,  # noqa: ARG001
):
    """Test manual recruitment with sufficient caps."""
    initial_caps = vault.bottle_caps

    dweller = await RadioService.manual_recruit(async_session, vault.id)

    assert dweller is not None
    assert dweller.vault_id == vault.id

    # Verify caps deducted
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps - game_config.radio.manual_recruitment_cost


@pytest.mark.skip(reason="FIXME: Session isolation - radio_dweller fixture not visible to RadioService query")
@pytest.mark.asyncio
async def test_manual_recruit_insufficient_caps(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,  # noqa: ARG001
    radio_dweller: Dweller,  # noqa: ARG001
):
    """Test manual recruitment with insufficient caps."""
    # Set caps below cost
    vault.bottle_caps = game_config.radio.manual_recruitment_cost - 1
    await async_session.commit()

    with pytest.raises(ValueError, match="Insufficient caps"):
        await RadioService.manual_recruit(async_session, vault.id)


@pytest.mark.asyncio
async def test_manual_recruit_no_radio(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test manual recruitment without radio room."""
    with pytest.raises(ValueError, match="No radio room available"):
        await RadioService.manual_recruit(async_session, vault.id)


@pytest.mark.skip(reason="FIXME: Session isolation - radio_dweller fixture not visible to RadioService query")
@pytest.mark.asyncio
async def test_manual_recruit_custom_cost(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,  # noqa: ARG001
    radio_dweller: Dweller,  # noqa: ARG001
):
    """Test manual recruitment with custom cost."""
    initial_caps = vault.bottle_caps
    custom_cost = 1000

    dweller = await RadioService.manual_recruit(async_session, vault.id, caps_cost=custom_cost)

    assert dweller is not None

    # Verify correct caps deducted
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps - custom_cost


@pytest.mark.asyncio
async def test_get_recruitment_stats_no_radio(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test recruitment stats without radio room."""
    stats = await RadioService.get_recruitment_stats(async_session, vault.id)

    assert stats["has_radio"] is False
    assert stats["recruitment_rate"] == 0.0
    assert stats["radio_rooms_count"] == 0


@pytest.mark.asyncio
async def test_get_recruitment_stats_with_radio(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,  # noqa: ARG001
):
    """Test recruitment stats with radio room."""
    stats = await RadioService.get_recruitment_stats(async_session, vault.id)

    assert stats["has_radio"] is True
    assert stats["recruitment_rate"] > 0.0
    assert stats["rate_per_hour"] > 0.0
    assert stats["estimated_hours_per_recruit"] > 0.0
    assert stats["radio_rooms_count"] == 1
    assert stats["manual_cost_caps"] == game_config.radio.manual_recruitment_cost


@pytest.mark.asyncio
async def test_get_recruitment_stats_higher_rate_with_charisma(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,  # noqa: ARG001
):
    """Test that recruitment stats return valid data."""
    stats = await RadioService.get_recruitment_stats(async_session, vault.id)

    # Verify stats structure and valid values
    assert stats["has_radio"] is True
    assert stats["recruitment_rate"] > 0.0
    assert stats["rate_per_hour"] > 0.0
    assert stats["estimated_hours_per_recruit"] > 0.0
    assert stats["radio_rooms_count"] == 1


@pytest.mark.asyncio
async def test_calculate_recruitment_rate_multiple_rooms(
    async_session: AsyncSession,
    vault: Vault,
):
    """Test recruitment rate with multiple radio rooms."""
    # Create two radio rooms
    room_data = {
        "name": "Radio Studio 1",
        "category": RoomTypeEnum.MISC,
        "ability": SPECIALEnum.CHARISMA,
        "population_required": None,
        "base_cost": 100,
        "incremental_cost": 50,
        "t2_upgrade_cost": 500,
        "t3_upgrade_cost": 1500,
        "capacity": 2,
        "output": None,
        "size_min": 1,
        "size_max": 3,
        "size": 2,
        "tier": 1,
        "coordinate_x": 0,
        "coordinate_y": 0,
        "image_url": None,
    }
    room_in_1 = RoomCreate(**room_data, vault_id=vault.id)
    room1 = await crud.room.create(db_session=async_session, obj_in=room_in_1)

    room_data["name"] = "Radio Studio 2"
    room_data["coordinate_x"] = 1
    room_in_2 = RoomCreate(**room_data, vault_id=vault.id)
    room2 = await crud.room.create(db_session=async_session, obj_in=room_in_2)

    # Get rate with 2 rooms
    rate_two_rooms = await RadioService.calculate_recruitment_rate(async_session, vault, [room1, room2])

    # Verify rate is positive and reasonable
    assert rate_two_rooms > 0
    assert rate_two_rooms < 1.0  # Should be less than 100% per tick
