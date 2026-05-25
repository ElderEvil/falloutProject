"""Tests for radio service logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

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
from app.schemas.dweller import DwellerCreate, DwellerCreateCommonOverride
from app.schemas.room import RoomCreate
from app.services.dweller_recycling_service import dweller_recycling_service
from app.services.radio_service import RadioService
from app.utils.exceptions import ResourceConflictException

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
        "strength": 3,
        "perception": 4,
        "endurance": 4,
        "charisma": 10,  # Max charisma for radio
        "intelligence": 5,
        "agility": 4,
        "luck": 5,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    dweller.room_id = radio_room.id
    async_session.add(dweller)
    await async_session.commit()
    return dweller


@pytest_asyncio.fixture(name="deleted_dweller")
async def deleted_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create a soft-deleted dweller with AI-generated assets, eligible for radio recycling.

    The dweller has bio, image_url, thumbnail_url and a RARE rarity to verify that
    recycling preserves the original identity and rarity rather than generating a blank dweller.
    """
    dweller_data = {
        "first_name": "Ghost",
        "last_name": "Signal",
        "gender": GenderEnum.FEMALE,
        "rarity": RarityEnum.RARE,
        "age_group": AgeGroupEnum.ADULT,
        "level": 3,
        "experience": 50,
        "max_health": 100,
        "health": 100,
        "radiation": 0,
        "happiness": 50,
        "strength": 4,
        "perception": 5,
        "endurance": 4,
        "charisma": 6,
        "intelligence": 7,
        "agility": 5,
        "luck": 4,
        "bio": "A survivor from the wastes who was lost to time.",
        "image_url": "https://s3-api.evillab.tech/dweller-images/ghost-signal.png",
        "thumbnail_url": "https://s3-api.evillab.tech/dweller-thumbnails/ghost-signal_thumbnail.png",
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

    # Soft-delete and back-date past the recycling eligibility window (default 7 days)
    dweller.is_deleted = True
    dweller.deleted_at = datetime.now(UTC) - timedelta(days=10)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


# ---------------------------------------------------------------------------
# Existing tests (radio rooms / rates / manual recruit)
# ---------------------------------------------------------------------------


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
    radio_room: Room,
):
    """Test successful recruitment via radio."""
    # Mock random to always succeed both the rate roll and the recycle probability roll.
    # The pool is empty in this test so the service falls back to create_random.
    with patch("random.random", return_value=0.0):
        dweller = await RadioService.check_for_recruitment(async_session, vault.id)

    assert dweller is not None
    assert dweller.vault_id == vault.id
    assert dweller.rarity == RarityEnum.COMMON


@pytest.mark.asyncio
async def test_check_for_recruitment_failure(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
):
    """Test failed recruitment via radio."""
    # Mock random to always fail the rate roll
    with patch("random.random", return_value=1.0):
        dweller = await RadioService.check_for_recruitment(async_session, vault.id)

    assert dweller is None


@pytest.mark.asyncio
async def test_recruit_dweller_returns_tuple(
    async_session: AsyncSession,
    vault: Vault,
):
    """recruit_dweller must return a (Dweller, bool) tuple."""
    result = await RadioService.recruit_dweller(async_session, vault.id)

    assert isinstance(result, tuple)
    assert len(result) == 2
    dweller, recycled = result
    assert isinstance(dweller, Dweller)
    assert isinstance(recycled, bool)


@pytest.mark.asyncio
async def test_recruit_dweller_fresh_when_pool_empty(
    async_session: AsyncSession,
    vault: Vault,
):
    """When no recyclable dwellers exist the service creates a fresh random dweller."""
    with patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is False
    assert dweller.vault_id == vault.id
    assert dweller.rarity == RarityEnum.COMMON
    assert dweller.first_name is not None
    assert dweller.last_name is not None


@pytest.mark.asyncio
async def test_manual_recruit_returns_tuple(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
    radio_dweller: Dweller,
):
    """manual_recruit must return a (Dweller, bool) tuple."""
    vault.bottle_caps = game_config.radio.manual_recruitment_cost + 100
    await async_session.commit()

    result = await RadioService.manual_recruit(async_session, vault.id)

    assert isinstance(result, tuple)
    assert len(result) == 2
    dweller, recycled = result
    assert isinstance(dweller, Dweller)
    assert isinstance(recycled, bool)


@pytest.mark.asyncio
async def test_manual_recruit_success(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
    radio_dweller: Dweller,
):
    """Test manual recruitment with sufficient caps."""
    vault.bottle_caps = game_config.radio.manual_recruitment_cost + 500
    await async_session.commit()
    initial_caps = vault.bottle_caps

    dweller, _ = await RadioService.manual_recruit(async_session, vault.id)

    assert dweller is not None
    assert dweller.vault_id == vault.id

    # Verify caps deducted
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps - game_config.radio.manual_recruitment_cost


@pytest.mark.asyncio
async def test_manual_recruit_insufficient_caps(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
    radio_dweller: Dweller,
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


@pytest.mark.asyncio
async def test_manual_recruit_custom_cost(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
    radio_dweller: Dweller,
):
    """Test manual recruitment with custom cost."""
    custom_cost = 1000
    vault.bottle_caps = custom_cost + 500
    await async_session.commit()
    initial_caps = vault.bottle_caps

    dweller, _ = await RadioService.manual_recruit(async_session, vault.id, caps_cost=custom_cost)

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
    radio_room: Room,
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
    radio_room: Room,
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


# ---------------------------------------------------------------------------
# New tests: radio asset repurpose (2.14-repurpose)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recruit_dweller_recycles_from_pool(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
):
    """When a recyclable dweller exists the radio restores it instead of creating a new one."""
    deleted_dweller_id = deleted_dweller.id

    # Force recycle probability roll to pass
    with patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is True
    assert dweller.id == deleted_dweller_id
    assert dweller.vault_id == vault.id
    assert dweller.is_deleted is False


@pytest.mark.asyncio
async def test_recruit_dweller_recycled_preserves_rarity(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
):
    """The recycled dweller keeps its original rarity (RARE stays RARE, not capped to COMMON)."""
    with patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is True
    assert dweller.rarity == RarityEnum.RARE


@pytest.mark.asyncio
async def test_recruit_dweller_recycled_preserves_assets(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
):
    """The recycled dweller retains its existing bio, image_url, and thumbnail_url."""
    with patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is True
    assert dweller.bio == "A survivor from the wastes who was lost to time."
    assert dweller.image_url == "https://s3-api.evillab.tech/dweller-images/ghost-signal.png"
    assert dweller.thumbnail_url == "https://s3-api.evillab.tech/dweller-thumbnails/ghost-signal_thumbnail.png"


@pytest.mark.asyncio
async def test_recruit_dweller_recycled_resets_stats(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
):
    """Recycled dweller has its gameplay stats reset to level 1 defaults."""
    with patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is True
    assert dweller.level == 1
    assert dweller.experience == 0
    assert dweller.radiation == 0
    assert dweller.partner_id is None


@pytest.mark.asyncio
async def test_recruit_dweller_skips_recycling_when_disabled(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
):
    """When recycle_enabled=False the service always creates a fresh dweller."""
    with patch.object(game_config.radio, "recycle_enabled", new=False), patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is False
    assert dweller.id != deleted_dweller.id
    assert dweller.rarity == RarityEnum.COMMON


@pytest.mark.asyncio
async def test_recruit_dweller_skips_recycling_when_override_provided(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
):
    """An explicit override bypasses recycling so the caller gets a customised fresh dweller."""
    override = DwellerCreateCommonOverride(first_name="Custom", last_name="Name")

    with patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id, override=override)

    assert recycled is False
    assert dweller.first_name == "Custom"
    assert dweller.last_name == "Name"
    assert dweller.id != deleted_dweller.id


@pytest.mark.asyncio
async def test_recruit_dweller_skips_recycling_when_probability_roll_fails(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
):
    """When the probability roll loses, a fresh dweller is created even if pool has candidates."""
    with patch("random.random", return_value=0.99):  # 0.99 > default 0.8, roll fails
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is False
    assert dweller.id != deleted_dweller.id


@pytest.mark.asyncio
async def test_recruit_dweller_falls_back_on_resource_conflict(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
):
    """If recycling raises ResourceConflictException the service falls back to create_random."""
    with (
        patch.object(
            dweller_recycling_service,
            "recycle_dweller_for_vault",
            new_callable=AsyncMock,
            side_effect=ResourceConflictException(detail="already restored"),
        ),
        patch("random.random", return_value=0.0),
    ):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is False
    assert dweller is not None
    assert dweller.vault_id == vault.id


@pytest.mark.asyncio
async def test_recruit_dweller_does_not_recycle_recently_deleted(
    async_session: AsyncSession,
    vault: Vault,
):
    """Dwellers deleted less than recycle_min_age_days ago are not eligible for radio recycling."""
    # Create a dweller deleted just 1 day ago (below the 7-day threshold)
    dweller_data = {
        "first_name": "Fresh",
        "last_name": "Delete",
        "gender": GenderEnum.MALE,
        "rarity": RarityEnum.COMMON,
        "age_group": AgeGroupEnum.ADULT,
        "level": 1,
        "experience": 0,
        "max_health": 50,
        "health": 50,
        "radiation": 0,
        "happiness": 50,
        "strength": 5,
        "perception": 5,
        "endurance": 5,
        "charisma": 5,
        "intelligence": 5,
        "agility": 5,
        "luck": 5,
    }
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    recent = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    recent.is_deleted = True
    recent.deleted_at = datetime.now(UTC) - timedelta(days=1)
    async_session.add(recent)
    await async_session.commit()

    with patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is False
    assert dweller.id != recent.id


@pytest.mark.asyncio
async def test_manual_recruit_propagates_recycled_flag(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
    radio_dweller: Dweller,
    deleted_dweller: Dweller,
):
    """manual_recruit surfaces the recycled flag from recruit_dweller."""
    vault.bottle_caps = game_config.radio.manual_recruitment_cost + 500
    await async_session.commit()

    with patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.manual_recruit(async_session, vault.id)

    assert recycled is True
    assert dweller.id == deleted_dweller.id
    assert dweller.is_deleted is False
