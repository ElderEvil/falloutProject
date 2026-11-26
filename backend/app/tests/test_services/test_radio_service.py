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

GHOST_BIO = "A survivor from the wastes who was lost to time."
GHOST_IMAGE = "https://s3-api.evillab.tech/dweller-images/ghost-signal.png"
GHOST_THUMB = "https://s3-api.evillab.tech/dweller-thumbnails/ghost-signal_thumbnail.png"
GHOST = {
    "first_name": "Ghost",
    "last_name": "Signal",
    "gender": GenderEnum.FEMALE,
    "rarity": RarityEnum.RARE,
    "bio": GHOST_BIO,
    "image_url": GHOST_IMAGE,
    "thumbnail_url": GHOST_THUMB,
    "visual_attributes": {"race": "ghoul", "faction": "none"},
}
COHOST = {
    "first_name": "Co-host",
    "last_name": "Radio",
    "gender": GenderEnum.FEMALE,
    "charisma": 5,
    "happiness": 80,
    "level": 5,
}
COST = game_config.radio.manual_recruitment_cost


RADIO_ROOM = {
    "category": RoomTypeEnum.MISC,
    "ability": SPECIALEnum.CHARISMA,
    "base_cost": 100,
    "incremental_cost": 50,
    "t2_upgrade_cost": 500,
    "t3_upgrade_cost": 1500,
    "capacity": 2,
    "size_min": 1,
    "size_max": 3,
    "size": 2,
}


async def _make_radio_room(session, vault, name="Radio Studio", *, x: int = 0) -> Room:
    room_in = RoomCreate(**RADIO_ROOM, name=name, coordinate_x=x, vault_id=vault.id)
    return await crud.room.create(db_session=session, obj_in=room_in)


async def _make_dweller(session: AsyncSession, vault, room: Room | None = None, **overrides) -> Dweller:
    payload = create_fake_dweller() | {"age_group": AgeGroupEnum.ADULT} | overrides
    dweller = await crud.dweller.create(db_session=session, obj_in=DwellerCreate(**payload, vault_id=vault.id))
    if room is not None:
        dweller.room_id = room.id
        session.add(dweller)
    await session.commit()
    return dweller


async def _commit(session: AsyncSession, vault, **fields) -> Vault:
    for name, value in fields.items():
        setattr(vault, name, value)
    session.add(vault)
    await session.commit()
    return vault


async def _recruit(session: AsyncSession, vault, roll: float = 0.0, **kwargs):
    with patch("random.random", return_value=roll):
        return await RadioService.recruit_dweller(session, vault.id, **kwargs)


@pytest_asyncio.fixture(name="radio_room")
async def radio_room_fixture(async_session, vault) -> Room:
    return await _make_radio_room(async_session, vault)


DJ = {
    "first_name": "DJ",
    "last_name": "Radio",
    "gender": GenderEnum.MALE,
    "rarity": RarityEnum.COMMON,
    "charisma": 10,
    "happiness": 80,
    "level": 5,
}


@pytest_asyncio.fixture(name="radio_dweller")
async def radio_dweller_fixture(async_session, vault, radio_room) -> Dweller:
    return await _make_dweller(async_session, vault, radio_room, **DJ)


@pytest_asyncio.fixture(name="deleted_dweller")
async def deleted_dweller_fixture(async_session, vault) -> Dweller:
    # Soft-deleted past the 7-day window, with AI assets and a RARE rarity: recycling must restore the
    # original identity instead of minting a blank dweller.
    dweller = await _make_dweller(async_session, vault, **GHOST)
    dweller.is_deleted = True
    dweller.deleted_at = datetime.now(UTC) - timedelta(days=10)
    async_session.add(dweller)
    await async_session.commit()
    await async_session.refresh(dweller)
    return dweller


async def test_calculate_recruitment_rate_no_radio(async_session, vault) -> None:
    assert await RadioService.calculate_recruitment_rate(async_session, vault, []) == 0.0


async def test_calculate_recruitment_rate_batches_room_dwellers(
    async_session, vault, radio_room, radio_dweller
) -> None:
    second_room = await _make_radio_room(async_session, vault, "Radio Studio Two", x=3)
    second_dweller = await _make_dweller(async_session, vault, second_room, **COHOST)
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


async def test_check_for_recruitment_no_radio(async_session, vault) -> None:
    assert await RadioService.check_for_recruitment(async_session, vault.id) is None


async def test_check_for_recruitment_rolls_the_rate(async_session, vault, radio_room) -> None:
    # Pin rare_chance=0 so the rare roll (0.0 < 0.04 default) cannot flip the fresh dweller to RARE.
    with patch("random.random", return_value=0.0), patch.object(game_config.radio, "rare_chance", new=0.0):
        dweller = await RadioService.check_for_recruitment(async_session, vault.id)
    assert dweller is not None
    assert (dweller.vault_id, dweller.rarity) == (vault.id, RarityEnum.COMMON)
    with patch("random.random", return_value=1.0):
        assert await RadioService.check_for_recruitment(async_session, vault.id) is None


async def test_check_for_recruitment_skips_full_vault_before_the_roll(async_session, vault, radio_room) -> None:
    await _commit(async_session, vault, population_max=0)
    rng = MagicMock()
    dweller = await RadioService.check_for_recruitment(async_session, vault.id, rng=rng)
    assert dweller is None
    rng.random.assert_not_called()
    await async_session.refresh(vault)
    assert vault.radio_mode == "happiness"
    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 0
    notifications = await notification_crud.get_user_notifications(async_session, vault.user_id)
    assert notifications[0].notification_type == NotificationType.RADIO_AUTO_SWITCHED_TO_HAPPINESS


async def test_recruit_dweller_returns_tuple(async_session, vault) -> None:
    result = await RadioService.recruit_dweller(async_session, vault.id)
    assert isinstance(result, tuple)
    assert len(result) == 2
    dweller, recycled = result
    assert isinstance(dweller, Dweller)
    assert isinstance(recycled, bool)


@pytest.mark.parametrize("race", [RaceOption.HUMAN, RaceOption.SUPER_MUTANT])
async def test_recruit_dweller_fresh_when_pool_empty(async_session, vault, race) -> None:
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
    assert (dweller.vault_id, dweller.rarity) == (vault.id, RarityEnum.COMMON)
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
    async_session,
    vault,
    radio_dweller,
    deleted_dweller,
    scenario_key,
    majority,
    minority,
) -> None:
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
    assert (recruit.gender, recruit.rarity) == (majority, RarityEnum.RARE)
    assert recruit.id != deleted_dweller.id
    with patch("random.random", return_value=0.0), patch("random.randrange", return_value=8):
        recruit, recycled = await RadioService.manual_recruit(async_session, vault.id, caps_cost=0)
    assert recycled
    assert (recruit.id, recruit.gender) == (deleted_dweller.id, minority)


async def test_failed_ratio_recruit_preserves_caps_and_emits_no_success(
    async_session, db_connection, vault, radio_dweller
) -> None:
    await _commit(async_session, vault, scenario_key="vault_69_test", bottle_caps=1000)
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


async def test_manual_recruit_success(async_session, vault, radio_room, radio_dweller) -> None:
    await _commit(async_session, vault, bottle_caps=COST + 500)
    initial_caps = vault.bottle_caps
    dweller, _ = await RadioService.manual_recruit(async_session, vault.id)
    assert dweller is not None
    assert dweller.vault_id == vault.id
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps - COST


@pytest.mark.parametrize(
    ("caps", "population_max", "match"), [(COST - 1, None, "Insufficient caps"), (COST + 500, 1, "population capacity")]
)
async def test_manual_recruit_rejects_without_spending_caps(
    async_session, vault, radio_room, radio_dweller, caps, population_max, match
) -> None:
    fields = {"bottle_caps": caps} | ({} if population_max is None else {"population_max": population_max})
    await _commit(async_session, vault, **fields)
    initial_caps = vault.bottle_caps
    with pytest.raises(ValueError, match=match):
        await RadioService.manual_recruit(async_session, vault.id)
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps
    if population_max is not None:
        assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 1


async def test_manual_recruit_no_radio(async_session, vault) -> None:
    with pytest.raises(ValueError, match="No radio room available"):
        await RadioService.manual_recruit(async_session, vault.id)


async def test_get_recruitment_stats_track_the_radio_room(async_session, vault) -> None:
    stats = await RadioService.get_recruitment_stats(async_session, vault.id)
    assert stats["has_radio"] is False
    assert (stats["recruitment_rate"], stats["radio_rooms_count"]) == (0.0, 0)
    await _make_radio_room(async_session, vault)
    stats = await RadioService.get_recruitment_stats(async_session, vault.id)
    assert stats["has_radio"] is True
    assert stats["recruitment_rate"] > 0.0
    assert stats["rate_per_hour"] > 0.0
    assert stats["estimated_hours_per_recruit"] > 0.0
    assert (stats["radio_rooms_count"], stats["manual_cost_caps"]) == (1, COST)


async def test_recruit_dweller_recycles_the_pooled_identity(async_session, vault, deleted_dweller) -> None:
    deleted_dweller_id = deleted_dweller.id
    original_race = deleted_dweller.visual_attributes.get("race")
    dweller, recycled = await _recruit(async_session, vault)
    assert recycled is True
    assert (dweller.id, dweller.vault_id) == (deleted_dweller_id, vault.id)
    assert dweller.is_deleted is False
    assert (dweller.rarity, dweller.bio) == (RarityEnum.RARE, GHOST_BIO)
    assert (dweller.image_url, dweller.thumbnail_url) == (GHOST_IMAGE, GHOST_THUMB)
    # Recycling restores the original race; it is never re-rolled.
    assert dweller.visual_attributes.get("race") == original_race


async def test_recruit_dweller_recycled_resets_stats(async_session, vault, deleted_dweller) -> None:
    partner = await _make_dweller(async_session, vault)
    deleted_dweller.level = 12
    deleted_dweller.experience = 500
    deleted_dweller.radiation = 75
    deleted_dweller.partner_id = partner.id
    async_session.add(deleted_dweller)
    await async_session.commit()
    dweller, recycled = await _recruit(async_session, vault)
    assert recycled is True
    assert (dweller.level, dweller.experience) == (1, 0)
    assert dweller.radiation == 0
    assert dweller.partner_id is None


@pytest.mark.parametrize(("recycle", "roll"), [(False, 0.0), (True, 0.99)])
async def test_recruit_dweller_falls_back_to_a_fresh_dweller(
    async_session, vault, deleted_dweller, recycle, roll
) -> None:
    # rare_chance=0 pins the rarity roll to COMMON (default 0.04 would give RARE at random=0.0).
    with (
        patch.object(game_config.radio, "recycle_enabled", new=recycle),
        patch.object(game_config.radio, "rare_chance", new=0.0),
    ):
        dweller, recycled = await _recruit(async_session, vault, roll=roll)
    assert recycled is False
    assert dweller.id != deleted_dweller.id
    assert dweller.rarity == RarityEnum.COMMON


async def test_recruit_dweller_rare_chance_rolls_rare(async_session, vault) -> None:
    # 0.5 < 1.0 → RARE; 0.5 < 0.0 is False → COMMON. Both rolls use the same mocked value.
    with patch.object(game_config.radio, "rare_chance", new=1.0):
        dweller, recycled = await _recruit(async_session, vault, roll=0.5)
    assert recycled is False
    assert dweller.rarity == RarityEnum.RARE
    with patch.object(game_config.radio, "rare_chance", new=0.0):
        dweller, recycled = await _recruit(async_session, vault, roll=0.5)
    assert recycled is False
    assert dweller.rarity == RarityEnum.COMMON


async def test_recruit_dweller_fresh_recruit_inherits_race_weights(async_session, vault) -> None:
    with patch.object(game_config.radio, "recycle_enabled", new=False):
        dweller, recycled = await _recruit(async_session, vault, roll=0.99)
    assert recycled is False
    race = dweller.visual_attributes.get("race")
    faction = dweller.visual_attributes.get("faction")
    assert race in {r.value for r in RaceOption}
    assert faction in faction_restrictions[RaceOption(race)]


async def test_recruit_dweller_skips_recycling_when_override_provided(async_session, vault, deleted_dweller) -> None:
    override = DwellerCreateCommonOverride(first_name="Custom", last_name="Name")
    dweller, recycled = await _recruit(async_session, vault, override=override)
    assert recycled is False
    assert (dweller.first_name, dweller.last_name) == ("Custom", "Name")
    assert dweller.id != deleted_dweller.id


async def test_recruit_dweller_falls_back_on_resource_conflict(async_session, vault, deleted_dweller) -> None:
    with patch.object(
        dweller_recycling_service,
        "recycle_dweller_for_vault",
        new_callable=AsyncMock,
        side_effect=ResourceConflictException(detail="already restored"),
    ):
        dweller, recycled = await _recruit(async_session, vault)
    assert recycled is False
    assert dweller is not None
    assert dweller.vault_id == vault.id


async def test_recruit_dweller_does_not_recycle_recently_deleted(async_session, vault) -> None:
    recent = await _make_dweller(async_session, vault, first_name="Fresh", last_name="Delete")
    recent.is_deleted = True
    recent.deleted_at = datetime.now(UTC) - timedelta(days=1)  # below the 7-day threshold
    async_session.add(recent)
    await async_session.commit()
    dweller, recycled = await _recruit(async_session, vault)
    assert recycled is False
    assert dweller.id != recent.id
