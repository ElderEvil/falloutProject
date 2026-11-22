from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import AgeGroupEnum, GenderEnum, NotificationType, RarityEnum, RoomTypeEnum, SPECIALEnum
from app.core.event_bus import event_bus
from app.core.game_config import game_config
from app.crud.notification import notification as notification_crud
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.options.factions import faction_restrictions
from app.options.races import RaceOption
from app.schemas.dweller import DwellerCreate, DwellerCreateCommonOverride
from app.schemas.room import RoomCreate
from app.services.dweller_recycling_service import dweller_recycling_service
from app.services.radio_service import RadioService
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.utils.query_counter import count_sql_statements
from app.utils.exceptions import ResourceConflictException

# Fixtures


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
        "visual_attributes": {"race": "ghoul", "faction": "none"},
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


# Existing tests (radio rooms / rates / manual recruit)


@pytest.mark.asyncio
async def test_calculate_recruitment_rate_no_radio(
    async_session: AsyncSession,
    vault: Vault,
):
    rate = await RadioService.calculate_recruitment_rate(async_session, vault, [])
    assert rate == 0.0


@pytest.mark.asyncio
async def test_calculate_recruitment_rate_batches_room_dwellers(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
    radio_dweller: Dweller,
):
    second_room = await crud.room.create(
        db_session=async_session,
        obj_in=RoomCreate(
            name="Radio Studio Two",
            category=RoomTypeEnum.MISC,
            ability=SPECIALEnum.CHARISMA,
            population_required=None,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            capacity=2,
            output=None,
            size_min=1,
            size_max=3,
            size=2,
            tier=1,
            coordinate_x=3,
            coordinate_y=0,
            image_url=None,
            vault_id=vault.id,
        ),
    )
    second_dweller = await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(
            first_name="Co-host",
            last_name="Radio",
            gender=GenderEnum.FEMALE,
            rarity=RarityEnum.COMMON,
            age_group=AgeGroupEnum.ADULT,
            level=5,
            experience=100,
            max_health=100,
            health=100,
            radiation=0,
            happiness=80,
            strength=3,
            perception=4,
            endurance=4,
            charisma=5,
            intelligence=5,
            agility=4,
            luck=5,
            vault_id=vault.id,
        ),
    )
    second_dweller.room_id = second_room.id
    async_session.add(second_dweller)
    await async_session.commit()

    with count_sql_statements(async_session) as single_room:
        await RadioService.calculate_recruitment_rate(async_session, vault, [radio_room])
    with count_sql_statements(async_session) as two_rooms:
        rate = await RadioService.calculate_recruitment_rate(async_session, vault, [radio_room, second_room])

    # Adding a room must not add a per-room dweller query.
    assert two_rooms.value <= single_room.value

    expected = game_config.radio.base_recruitment_rate
    for room, dwellers in ((radio_room, [radio_dweller]), (second_room, [second_dweller])):
        expected *= game_config.radio.get_tier_multiplier(room.tier)
        for dweller in dwellers:
            expected += (
                game_config.radio.base_recruitment_rate
                * dweller.charisma
                * (game_config.radio.charisma_rate_multiplier)
            )
    expected *= 1.0 + vault.happiness * game_config.radio.happiness_rate_multiplier
    assert rate == pytest.approx(expected)


@pytest.mark.asyncio
async def test_check_for_recruitment_no_radio(
    async_session: AsyncSession,
    vault: Vault,
):
    dweller = await RadioService.check_for_recruitment(async_session, vault.id)
    assert dweller is None


@pytest.mark.asyncio
async def test_check_for_recruitment_success(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
):
    # Mock random to always succeed the rate roll; pin rare_chance=0 so the
    # rare roll (0.0 < 0.04 default) cannot flip the fresh dweller to RARE.
    with patch("random.random", return_value=0.0), patch.object(game_config.radio, "rare_chance", new=0.0):
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
    # Mock random to always fail the rate roll
    with patch("random.random", return_value=1.0):
        dweller = await RadioService.check_for_recruitment(async_session, vault.id)

    assert dweller is None


@pytest.mark.asyncio
async def test_check_for_recruitment_skips_full_vault_before_the_roll(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
):
    vault.population_max = 0
    async_session.add(vault)
    await async_session.commit()
    rng = MagicMock()

    dweller = await RadioService.check_for_recruitment(async_session, vault.id, rng=rng)

    assert dweller is None
    rng.random.assert_not_called()
    await async_session.refresh(vault)
    assert vault.radio_mode == "happiness"
    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 0
    notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
    assert notifications[0].notification_type == NotificationType.RADIO_AUTO_SWITCHED_TO_HAPPINESS


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
@pytest.mark.parametrize("race", [RaceOption.HUMAN, RaceOption.SUPER_MUTANT])
async def test_recruit_dweller_fresh_when_pool_empty(
    async_session: AsyncSession,
    vault: Vault,
    race: RaceOption,
):
    # rare_chance=0 pins the rarity roll to COMMON (default 0.04 would give RARE at random=0.0)
    with (
        patch("random.random", return_value=0.0),
        patch.object(game_config.radio, "rare_chance", new=0.0),
        patch.object(
            game_config.dweller, "race_weights", new={option.value: int(option == race) for option in RaceOption}
        ),
    ):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is False
    assert dweller.vault_id == vault.id
    assert dweller.rarity == RarityEnum.COMMON
    assert dweller.first_name is not None
    assert dweller.visual_attributes["race"] == race.value
    if race == RaceOption.HUMAN:
        assert dweller.last_name is not None
    else:
        assert dweller.last_name is None


@pytest.mark.parametrize(
    ("scenario_key", "majority", "minority"),
    [
        ("vault_68_test", GenderEnum.MALE, GenderEnum.FEMALE),
        ("vault_69_test", GenderEnum.FEMALE, GenderEnum.MALE),
    ],
)
async def test_ratio_vault_rolls_gender_for_fresh_rare_and_recycled_radio_recruits(
    async_session: AsyncSession,
    vault: Vault,
    radio_dweller: Dweller,
    deleted_dweller: Dweller,
    scenario_key: str,
    majority: GenderEnum,
    minority: GenderEnum,
):
    vault.scenario_key = scenario_key
    deleted_dweller.gender = minority
    await async_session.commit()
    with (
        patch("random.random", return_value=0.0),
        patch("random.randrange", return_value=7) as gender_roll,
        patch.object(game_config.radio, "rare_chance", new=1.0),
    ):
        recruit = await RadioService.check_for_recruitment(async_session, vault.id)
    gender_roll.assert_called_once_with(9)
    assert recruit is not None
    assert recruit.gender == majority
    assert recruit.rarity == RarityEnum.RARE
    assert recruit.id != deleted_dweller.id

    with patch("random.random", return_value=0.0), patch("random.randrange", return_value=8):
        recruit, recycled = await RadioService.manual_recruit(async_session, vault.id, caps_cost=0)
    assert recycled
    assert recruit.id == deleted_dweller.id
    assert recruit.gender == minority


async def test_failed_ratio_recruit_preserves_caps_and_emits_no_success(
    async_session: AsyncSession,
    db_connection: AsyncConnection,
    vault: Vault,
    radio_dweller: Dweller,
):
    vault.scenario_key = "vault_69_test"
    vault.bottle_caps = 1000
    await async_session.commit()
    vault_id = vault.id
    initial_population = await crud.dweller.count_living_in_vault(async_session, vault_id)

    def fail_recruit_insert(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("INSERT INTO dweller "):
            raise RuntimeError("recruit insert failed")

    event.listen(db_connection.sync_connection, "before_cursor_execute", fail_recruit_insert)
    try:
        with (
            patch.object(event_bus, "emit", wraps=event_bus.emit) as delivered,
            patch.object(game_config.radio, "recycle_enabled", new=False),
            pytest.raises(RuntimeError, match="recruit insert failed"),
        ):
            await RadioService.manual_recruit(async_session, vault_id, caps_cost=100)
    finally:
        event.remove(db_connection.sync_connection, "before_cursor_execute", fail_recruit_insert)
    await async_session.rollback()

    reloaded = await crud.vault.get(async_session, vault_id)
    assert reloaded.bottle_caps == 1000
    assert await crud.dweller.count_living_in_vault(async_session, vault_id) == initial_population
    delivered.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_recruit_success(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
    radio_dweller: Dweller,
):
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
    # Set caps below cost
    vault.bottle_caps = game_config.radio.manual_recruitment_cost - 1
    await async_session.commit()

    with pytest.raises(ValueError, match="Insufficient caps"):
        await RadioService.manual_recruit(async_session, vault.id)


@pytest.mark.asyncio
async def test_manual_recruit_does_not_spend_caps_when_vault_is_full(
    async_session: AsyncSession,
    vault: Vault,
    radio_room: Room,
    radio_dweller: Dweller,
):
    vault.population_max = 1
    vault.bottle_caps = game_config.radio.manual_recruitment_cost + 500
    async_session.add(vault)
    await async_session.commit()
    initial_caps = vault.bottle_caps

    with pytest.raises(ValueError, match="population capacity"):
        await RadioService.manual_recruit(async_session, vault.id)

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps
    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 1


@pytest.mark.asyncio
async def test_manual_recruit_no_radio(
    async_session: AsyncSession,
    vault: Vault,
):
    with pytest.raises(ValueError, match="No radio room available"):
        await RadioService.manual_recruit(async_session, vault.id)


@pytest.mark.asyncio
async def test_get_recruitment_stats_no_radio(
    async_session: AsyncSession,
    vault: Vault,
):
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
    stats = await RadioService.get_recruitment_stats(async_session, vault.id)

    assert stats["has_radio"] is True
    assert stats["recruitment_rate"] > 0.0
    assert stats["rate_per_hour"] > 0.0
    assert stats["estimated_hours_per_recruit"] > 0.0
    assert stats["radio_rooms_count"] == 1
    assert stats["manual_cost_caps"] == game_config.radio.manual_recruitment_cost


# New tests: radio asset repurpose (2.14-repurpose)


@pytest.mark.asyncio
async def test_recruit_dweller_recycles_from_pool(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
):
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
    partner = await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(**create_fake_dweller(), vault_id=vault.id),
    )
    deleted_dweller.level = 12
    deleted_dweller.experience = 500
    deleted_dweller.radiation = 75
    deleted_dweller.partner_id = partner.id
    async_session.add(deleted_dweller)
    await async_session.commit()

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
    # rare_chance=0 pins the rarity roll to COMMON (default 0.04 would give RARE at random=0.0)
    with (
        patch.object(game_config.radio, "recycle_enabled", new=False),
        patch.object(game_config.radio, "rare_chance", new=0.0),
        patch("random.random", return_value=0.0),
    ):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is False
    assert dweller.id != deleted_dweller.id
    assert dweller.rarity == RarityEnum.COMMON


@pytest.mark.asyncio
async def test_recruit_dweller_rare_chance_rolls_rare(async_session: AsyncSession, vault: Vault) -> None:
    # 0.5 < 1.0 → RARE; 0.5 < 0.0 is False → COMMON. Both rolls use the same mocked value.
    with patch.object(game_config.radio, "rare_chance", new=1.0), patch("random.random", return_value=0.5):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)
    assert recycled is False
    assert dweller.rarity == RarityEnum.RARE

    with patch.object(game_config.radio, "rare_chance", new=0.0), patch("random.random", return_value=0.5):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)
    assert recycled is False
    assert dweller.rarity == RarityEnum.COMMON


@pytest.mark.asyncio
async def test_recruit_dweller_fresh_recruit_inherits_race_weights(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    """Fresh radio recruits inherit race_weights diversity: race ∈ RaceOption, faction valid for race."""
    with patch.object(game_config.radio, "recycle_enabled", new=False), patch("random.random", return_value=0.99):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is False
    race = dweller.visual_attributes.get("race")
    faction = dweller.visual_attributes.get("faction")
    assert race in {r.value for r in RaceOption}
    assert faction in faction_restrictions[RaceOption(race)]


@pytest.mark.asyncio
async def test_recruit_dweller_recycling_preserves_race(
    async_session: AsyncSession,
    vault: Vault,
    deleted_dweller: Dweller,
) -> None:
    """Recycling restores the original dweller identity — race is never re-rolled (plan §6.2)."""
    original_race = deleted_dweller.visual_attributes.get("race")

    with patch("random.random", return_value=0.0):
        dweller, recycled = await RadioService.recruit_dweller(async_session, vault.id)

    assert recycled is True
    assert dweller.id == deleted_dweller.id
    assert dweller.visual_attributes.get("race") == original_race


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
