from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, IncidentStatus, IncidentType, RarityEnum, RelationshipTypeEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.incident import Incident
from app.models.pet import Pet
from app.models.relationship import Relationship
from app.models.room import Room
from app.models.vault import Vault
from app.options.races import DISCOMFORT_EFFECTS, DiscomfortSeverity
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.happiness_service import HappinessService, happiness_service
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.rooms import create_fake_room

FACTORS = {
    "has_low_resources": False,
    "has_critical_resources": False,
    "active_incident_count": 0,
    "power_ratio": 0.9,
    "food_ratio": 0.9,
    "water_ratio": 0.9,
    "radio_happiness_bonus": 0.0,
}
HALF_RESOURCES = FACTORS | {"power_ratio": 0.5, "food_ratio": 0.5, "water_ratio": 0.5}


async def _dweller(session: AsyncSession, vault: Vault, *, room: Room | None = None, **attrs) -> Dweller:
    data = create_fake_dweller() | attrs
    obj = DwellerCreate(**data, vault_id=vault.id, room_id=room.id if room else None)
    return await crud.dweller.create(db_session=session, obj_in=obj)


async def _set_resources(session: AsyncSession, vault: Vault, level: int = 90) -> None:
    vault.power = vault.food = vault.water = level
    vault.power_max = vault.food_max = vault.water_max = 100
    session.add(vault)
    await session.commit()


async def _room(session: AsyncSession, vault: Vault, name: str) -> Room:
    data = create_fake_room() | {"name": name}
    return await crud.room.create(db_session=session, obj_in=RoomCreate(**data, vault_id=vault.id))


async def _healthy(session: AsyncSession, vault: Vault, *, room: Room | None = None, **attrs) -> Dweller:
    """A full-health dweller: isolates happiness assertions from the low-health penalty."""
    return await _dweller(session, vault, room=room, health=100, max_health=100, radiation=0, **attrs)


async def _fire(session: AsyncSession, vault: Vault, room: Room) -> None:
    session.add(
        Incident(
            vault_id=vault.id,
            room_id=room.id,
            type=IncidentType.FIRE,
            status=IncidentStatus.ACTIVE,
            difficulty=2,
            is_active=True,
        )
    )
    await session.commit()


@pytest_asyncio.fixture(name="test_room")
async def test_room_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    return await _room(async_session, vault, "Power Generator")


@pytest_asyncio.fixture(name="working_dweller")
async def working_dweller_fixture(async_session: AsyncSession, vault: Vault, test_room: Room) -> Dweller:
    return await _healthy(
        async_session, vault, room=test_room, first_name="Happy", last_name="Worker", status="working", happiness=70
    )


@pytest.mark.asyncio
class TestHappinessService:
    @pytest.mark.parametrize(
        ("status", "receives_radio"),
        [
            (DwellerStatusEnum.EXPLORING, False),
            (DwellerStatusEnum.QUESTING, False),
            (DwellerStatusEnum.WORKING, True),
            (DwellerStatusEnum.TRAINING, True),
        ],
    )
    async def test_radio_happiness_only_reaches_dwellers_in_vault(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
        test_room: Room,
        status,
        receives_radio,
    ):
        test_room.name = "Radio studio"
        # The fixture dweller staffs the booth; the recipient's status must not decide whether the
        # broadcast exists, or removing the in-vault guard would still pass every case.
        working_dweller.status = DwellerStatusEnum.WORKING
        working_dweller.room_id = test_room.id
        recipient = await _healthy(
            async_session,
            vault,
            first_name="Radio",
            last_name="Recipient",
            status=status.value,
            happiness=50,
            partner_id=None,
        )
        assert recipient.is_in_vault is receives_radio
        vault.radio_mode = "recruitment"
        async_session.add_all([test_room, working_dweller, vault])
        await async_session.commit()
        await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=120)
        await async_session.refresh(recipient)
        without_radio = recipient.happiness
        recipient.happiness = 50
        vault.radio_mode = "happiness"
        async_session.add_all([recipient, vault])
        await async_session.commit()
        await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=120)
        await async_session.refresh(recipient)
        expected_bonus = game_config.radio.happiness_bonus * 2 if receives_radio else 0
        assert recipient.happiness - without_radio == pytest.approx(expected_bonus)
        modifiers = await happiness_service.get_happiness_modifiers(async_session, recipient.id)
        radio_modifiers = [e for e in modifiers["positive"] if e["name"] == "Radio (Happiness Mode)"]
        assert bool(radio_modifiers) is receives_radio
        if receives_radio:
            assert radio_modifiers[0]["value"] == pytest.approx(game_config.radio.happiness_bonus)

    async def test_radio_broadcast_requires_a_working_dweller(
        self, async_session: AsyncSession, vault: Vault, working_dweller: Dweller, test_room: Room
    ):
        from app.services.radio_service import RadioService

        test_room.name = "Radio studio"
        working_dweller.room_id = None
        working_dweller.status = DwellerStatusEnum.IDLE
        vault.radio_mode = "happiness"
        async_session.add_all([test_room, working_dweller, vault])
        await async_session.commit()
        rooms = await RadioService.get_radio_rooms(async_session, vault.id)
        assert rooms
        assert await RadioService.calculate_happiness_bonus(async_session, vault, rooms) == pytest.approx(0.0)
        working_dweller.room_id = test_room.id
        working_dweller.status = DwellerStatusEnum.WORKING
        async_session.add(working_dweller)
        await async_session.commit()
        assert await RadioService.calculate_happiness_bonus(async_session, vault, rooms) == pytest.approx(
            game_config.radio.happiness_bonus
        )
        working_dweller.status = DwellerStatusEnum.TRAINING
        async_session.add(working_dweller)
        await async_session.commit()
        assert await RadioService.calculate_happiness_bonus(async_session, vault, rooms) == pytest.approx(0.0)
        vault.radio_mode = "recruitment"
        async_session.add(vault)
        await async_session.commit()
        assert await RadioService.calculate_happiness_bonus(async_session, vault, rooms) == pytest.approx(0.0)

    async def test_update_vault_happiness_batches_room_and_partner_lookups(
        self, async_session: AsyncSession, vault: Vault, working_dweller: Dweller, test_room: Room
    ):
        partner = await _dweller(
            async_session, vault, first_name="Partner", status=DwellerStatusEnum.WORKING, happiness=50, charisma=5
        )
        partner.room_id = test_room.id
        working_dweller.partner_id = partner.id
        partner.partner_id = working_dweller.id
        async_session.add_all([partner, working_dweller])
        await async_session.commit()
        with (
            patch("app.services.happiness_service.room_crud.get", new_callable=AsyncMock) as room_get,
            patch("app.services.happiness_service.dweller_crud.get", new_callable=AsyncMock) as dweller_get,
        ):
            stats = await happiness_service.update_vault_happiness(async_session, vault.id)
        room_get.assert_not_awaited()
        dweller_get.assert_not_awaited()
        assert stats["dwellers_processed"] >= 2

    async def test_low_resources_reduces_happiness(self, async_session: AsyncSession, vault: Vault, working_dweller):
        await _set_resources(async_session, vault, level=15)
        initial_happiness = working_dweller.happiness
        await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=60)
        await async_session.refresh(working_dweller)
        assert working_dweller.happiness < initial_happiness

    async def test_active_incident_reduces_happiness(
        self, async_session: AsyncSession, vault: Vault, working_dweller: Dweller, test_room: Room
    ):
        await async_session.refresh(working_dweller)
        await _fire(async_session, vault, test_room)
        await _set_resources(async_session, vault)
        initial_happiness = working_dweller.happiness
        await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=60)
        await async_session.refresh(working_dweller)
        # The incident penalty applies but other bonuses may offset it, so only the net cap is pinned.
        assert working_dweller.happiness - initial_happiness < 1.0

    async def test_partner_bonus(self, async_session: AsyncSession, vault: Vault, test_room: Room):
        dweller1 = await _dweller(
            async_session,
            vault,
            room=test_room,
            first_name="Partner",
            last_name="One",
            status="working",
            happiness=60,
            gender="male",
        )
        dweller2 = await _dweller(
            async_session,
            vault,
            room=test_room,
            first_name="Partner",
            last_name="Two",
            status="working",
            happiness=60,
            gender="female",
        )
        async_session.add(
            Relationship(
                dweller_1_id=dweller1.id,
                dweller_2_id=dweller2.id,
                relationship_type=RelationshipTypeEnum.PARTNER,
                affinity=100,
            )
        )
        await async_session.commit()
        dweller1.partner_id = dweller2.id
        dweller2.partner_id = dweller1.id
        async_session.add_all([dweller1, dweller2])
        await async_session.commit()
        await _set_resources(async_session, vault)
        initial_happiness_1 = dweller1.happiness
        await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=60)
        await async_session.refresh(dweller1)
        # The partner bonus offsets base decay; some decay is still allowed.
        assert dweller1.happiness >= initial_happiness_1 - 5

    async def test_soft_deleted_partner_is_cleared(
        self, async_session: AsyncSession, vault: Vault, test_room: Room, working_dweller: Dweller
    ):
        partner = await _dweller(async_session, vault, room=test_room)
        partner.is_deleted = True
        working_dweller.partner_id = partner.id
        async_session.add_all([partner, working_dweller])
        await async_session.commit()
        await happiness_service.update_vault_happiness(async_session, vault.id)
        await async_session.refresh(working_dweller)
        assert working_dweller.partner_id is None

    async def test_invalid_vault(self, async_session: AsyncSession):
        result = await happiness_service.update_vault_happiness(
            async_session, UUID("00000000-0000-0000-0000-000000000000"), seconds_passed=60
        )
        assert "error" in result
        assert result["error"] == "Vault not found"

    async def test_update_commits_dwellers_and_vault_together(
        self, async_session: AsyncSession, vault: Vault, working_dweller: Dweller, monkeypatch: pytest.MonkeyPatch
    ):
        original_happiness = working_dweller.happiness
        commits = 0
        original_commit = async_session.commit

        async def counting_commit() -> None:
            nonlocal commits
            commits += 1
            await original_commit()

        monkeypatch.setattr(async_session, "commit", counting_commit)
        await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=60)
        assert commits == 1
        await async_session.refresh(working_dweller)
        await async_session.refresh(vault)
        assert working_dweller.happiness != original_happiness
        assert vault.happiness == int(working_dweller.happiness)

    async def test_update_failure_preserves_dweller_and_vault_happiness(
        self, async_session: AsyncSession, db_connection: AsyncConnection, vault: Vault, working_dweller: Dweller
    ) -> None:
        # The vault fixture randomises happiness; pin it so the aggregate always dirties the row.
        vault.happiness = 100
        async_session.add(vault)
        await async_session.commit()
        previous = working_dweller.happiness, vault.happiness

        def reject_vault_write(_connection, _cursor, statement, _parameters, _context, _executemany):
            if statement.startswith("UPDATE vault "):
                raise RuntimeError("injected vault write failure")

        event.listen(db_connection.sync_connection, "before_cursor_execute", reject_vault_write)
        try:
            with pytest.raises(RuntimeError, match="injected vault write failure"):
                await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=60)
        finally:
            event.remove(db_connection.sync_connection, "before_cursor_execute", reject_vault_write)
        await async_session.rollback()
        await async_session.refresh(working_dweller)
        await async_session.refresh(vault)
        assert (working_dweller.happiness, vault.happiness) == previous

    async def test_get_modifiers_invalid_dweller(self, async_session: AsyncSession):
        modifiers = await happiness_service.get_happiness_modifiers(
            async_session, UUID("00000000-0000-0000-0000-000000000000")
        )
        assert "error" in modifiers
        assert modifiers["error"] == "Dweller not found"

    async def test_training_dweller_stable_happiness(self, async_session: AsyncSession, vault: Vault):
        trainee = await _healthy(
            async_session, vault, first_name="Training", last_name="Dweller", status="training", happiness=50
        )
        await _set_resources(async_session, vault)
        initial_happiness = trainee.happiness
        await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=60)
        await async_session.refresh(trainee)
        # Training bonus roughly offsets base decay.
        assert abs(trainee.happiness - initial_happiness) <= 1

    @pytest.mark.parametrize(
        ("bucket", "name", "attrs", "incident"),
        [
            ("positive", "Training", {"status": "training"}, False),
            ("negative", "Low Health", {"status": "working", "health": 25}, False),
            ("negative", "Idle", {"status": "idle"}, False),
            ("negative", "Incident", {"status": "working"}, True),
        ],
    )
    async def test_get_modifiers_reports_dweller_state(
        self, async_session: AsyncSession, vault: Vault, test_room: Room, bucket, name, attrs, incident
    ):
        data = {"happiness": 60, "health": 100, "max_health": 100, "radiation": 0} | attrs
        dweller = await _dweller(async_session, vault, room=test_room if incident else None, **data)
        if incident:
            await _fire(async_session, vault, test_room)
        await _set_resources(async_session, vault)
        modifiers = await happiness_service.get_happiness_modifiers(async_session, dweller.id)
        names = [m["name"] for m in modifiers[bucket]]
        assert any(name in entry for entry in names) if incident else name in names

    async def test_pet_happiness_bonus(self, async_session: AsyncSession, vault: Vault):
        dweller = await _healthy(
            async_session, vault, first_name="Pet", last_name="Owner", status="training", happiness=50
        )
        baseline = await HappinessService._calculate_happiness_change(
            async_session, dweller, FACTORS, seconds_passed=60
        )
        # Equip a happiness pet (Mr. Pebbles: happiness=0.25).
        dweller.pet = Pet(name="Mr. Pebbles", rarity="Legendary")
        with_pet = await HappinessService._calculate_happiness_change(
            async_session, dweller, FACTORS, seconds_passed=60
        )
        assert with_pet == pytest.approx(baseline + 0.25)

    async def test_pet_happiness_bonus_end_to_end(self, async_session: AsyncSession, vault: Vault):
        dweller = await _healthy(
            async_session,
            vault,
            first_name="Pet",
            age_group="adult",
            last_name="Owner",
            status="training",
            happiness=50,
        )
        no_pet_dweller = await _healthy(
            async_session, vault, first_name="No", last_name="Pet", status="training", happiness=50
        )
        # Equip through the real FK-only equip path; get_multi_by_vault's selectinload(Dweller.pet)
        # is what makes the bonus visible to the tick sweep.
        pet = await crud.pet.create(
            async_session, obj_in={"name": "Mr. Pebbles", "rarity": RarityEnum.LEGENDARY, "value": 500}
        )
        await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)
        await _set_resources(async_session, vault)
        await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=60)
        await async_session.refresh(dweller)
        await async_session.refresh(no_pet_dweller)
        assert dweller.happiness > no_pet_dweller.happiness


@pytest.mark.asyncio
async def test_feral_coworker_and_rival_reduce_happiness(async_session: AsyncSession, vault: Vault) -> None:
    dweller = await _healthy(
        async_session, vault, first_name="Mood", last_name="Check", status="training", happiness=50
    )
    room_id = uuid4()
    dweller.room_id = room_id
    async_session.add(dweller)
    await async_session.commit()
    baseline = await HappinessService._calculate_happiness_change(
        async_session, dweller, FACTORS, seconds_passed=60, dwellers_by_room={room_id: [dweller]}, rivals_by_dweller={}
    )
    feral = SimpleNamespace(id=uuid4(), room_id=room_id, visual_attributes={"race": "ghoul", "state_of_being": "feral"})
    with_feral = await HappinessService._calculate_happiness_change(
        async_session,
        dweller,
        FACTORS,
        seconds_passed=60,
        dwellers_by_room={room_id: [dweller, feral]},
        rivals_by_dweller={},
    )
    assert with_feral == pytest.approx(baseline - DISCOMFORT_EFFECTS[DiscomfortSeverity.STRONG].happiness_penalty)
    rival = SimpleNamespace(id=uuid4(), room_id=room_id)
    with_rival = await HappinessService._calculate_happiness_change(
        async_session,
        dweller,
        FACTORS,
        seconds_passed=60,
        dwellers_by_room={room_id: [dweller, rival]},
        rivals_by_dweller={dweller.id: {rival.id}},
    )
    assert with_rival == pytest.approx(baseline - game_config.relationship.rival_happiness_penalty)


async def _create_resting_dweller(
    async_session: AsyncSession, vault: Vault, room: Room, *, first_name: str, status: str = "resting"
) -> Dweller:
    dweller = await _healthy(
        async_session, vault, first_name=first_name, last_name="Comfort", age_group="adult", status=status, happiness=50
    )
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()
    return dweller


@pytest.mark.asyncio
async def test_resting_living_quarters_bonus_is_net_positive(
    async_session: AsyncSession, vault: Vault, test_room: Room
) -> None:
    living = await _create_resting_dweller(
        async_session, vault, await _room(async_session, vault, "Living Quarters"), first_name="Home"
    )
    away = await _create_resting_dweller(async_session, vault, test_room, first_name="Away")
    living_delta = await HappinessService._calculate_happiness_change(
        async_session, living, HALF_RESOURCES, seconds_passed=60
    )
    power_delta = await HappinessService._calculate_happiness_change(
        async_session, away, HALF_RESOURCES, seconds_passed=60
    )
    expected_living = (
        game_config.happiness.living_quarters_bonus
        - game_config.happiness.base_decay
        + game_config.happiness.no_incidents_bonus
    )
    expected_power = game_config.happiness.no_incidents_bonus - game_config.happiness.base_decay
    assert living_delta == pytest.approx(expected_living)
    assert power_delta == pytest.approx(expected_power)
    assert living_delta > 0
    assert power_delta < 0


@pytest.mark.asyncio
async def test_resting_living_room_dweller_gains_happiness_in_tick(
    async_session: AsyncSession, vault: Vault, test_room: Room
) -> None:
    living = await _create_resting_dweller(
        async_session, vault, await _room(async_session, vault, "Living Quarters"), first_name="Home"
    )
    away = await _create_resting_dweller(async_session, vault, test_room, first_name="Away")
    await _set_resources(async_session, vault, level=50)
    await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=300)
    await async_session.refresh(living)
    await async_session.refresh(away)
    assert living.happiness > 50
    assert away.happiness < 50
    assert living.happiness > away.happiness


@pytest.mark.asyncio
async def test_working_gain_stays_exclusive_to_working(async_session: AsyncSession, vault: Vault) -> None:
    living_room = await _room(async_session, vault, "Living Quarters")
    resting = await _create_resting_dweller(async_session, vault, living_room, first_name="Rest")
    working = await _create_resting_dweller(async_session, vault, living_room, first_name="Work", status="working")
    resting_delta = await HappinessService._calculate_happiness_change(
        async_session, resting, HALF_RESOURCES, seconds_passed=60
    )
    working_delta = await HappinessService._calculate_happiness_change(
        async_session, working, HALF_RESOURCES, seconds_passed=60
    )
    expected_extra = game_config.happiness.working_gain
    if game_config.happiness.high_health_threshold < 1.0:
        expected_extra += game_config.happiness.high_health_bonus
    assert working_delta - resting_delta == pytest.approx(expected_extra)


@pytest.mark.asyncio
async def test_modifiers_show_living_quarters_for_resting_dweller(
    async_session: AsyncSession, vault: Vault, test_room: Room
) -> None:
    living = await _create_resting_dweller(
        async_session, vault, await _room(async_session, vault, "Living Quarters"), first_name="Home"
    )
    away = await _create_resting_dweller(async_session, vault, test_room, first_name="Away")
    living_modifiers = await happiness_service.get_happiness_modifiers(async_session, living.id)
    living_positive = {entry["name"]: entry["value"] for entry in living_modifiers["positive"]}
    assert "Living Quarters" in living_positive
    assert living_positive["Living Quarters"] == pytest.approx(game_config.happiness.living_quarters_bonus)
    power_modifiers = await happiness_service.get_happiness_modifiers(async_session, away.id)
    power_positive = [entry["name"] for entry in power_modifiers["positive"]]
    assert "Living Quarters" not in power_positive
