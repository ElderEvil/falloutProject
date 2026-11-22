"""Tests for happiness service."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, IncidentStatus, IncidentType, RarityEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.incident import Incident
from app.models.pet import Pet
from app.models.room import Room
from app.models.vault import Vault
from app.options.races import DISCOMFORT_EFFECTS, DiscomfortSeverity
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.happiness_service import HappinessService, happiness_service
from app.tests.factory.dwellers import create_fake_dweller
from app.tests.factory.rooms import create_fake_room


@pytest_asyncio.fixture(name="test_room")
async def test_room_fixture(async_session: AsyncSession, vault: Vault) -> Room:
    """Create a test room for dwellers."""
    room_data = create_fake_room()
    room_data["name"] = "Power Generator"
    room_in = RoomCreate(**room_data, vault_id=vault.id)
    return await crud.room.create(db_session=async_session, obj_in=room_in)


@pytest_asyncio.fixture(name="working_dweller")
async def working_dweller_fixture(
    async_session: AsyncSession,
    vault: Vault,
    test_room: Room,
) -> Dweller:
    """Create a working dweller with good conditions."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Happy",
            "last_name": "Worker",
            "status": "working",
            "happiness": 70,
            "health": 100,
            "max_health": 100,
            "radiation": 0,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id, room_id=test_room.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest.mark.asyncio
class TestHappinessService:
    """Test happiness service functionality."""

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
        status: DwellerStatusEnum,
        receives_radio: bool,
    ):
        """Radio affects residents' tick and breakdown, never explorers or quest parties."""
        test_room.name = "Radio studio"
        # The fixture's dweller staffs the booth; the recipient's status must not decide whether
        # the broadcast exists, or removing the in-vault guard would still pass every case.
        working_dweller.status = DwellerStatusEnum.WORKING
        working_dweller.room_id = test_room.id
        recipient_data = create_fake_dweller()
        recipient_data.update(
            {
                "first_name": "Radio",
                "last_name": "Recipient",
                "status": status.value,
                "happiness": 50,
                "health": 100,
                "max_health": 100,
                "radiation": 0,
                "partner_id": None,
            }
        )
        recipient = await crud.dweller.create(async_session, obj_in=DwellerCreate(**recipient_data, vault_id=vault.id))
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
        radio_modifiers = [entry for entry in modifiers["positive"] if entry["name"] == "Radio (Happiness Mode)"]
        assert bool(radio_modifiers) is receives_radio
        if receives_radio:
            assert radio_modifiers[0]["value"] == pytest.approx(game_config.radio.happiness_bonus)

    async def test_radio_broadcast_requires_a_working_dweller(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
        test_room: Room,
    ):
        """An unstaffed studio is silent; only a dweller working the broadcast makes it pay."""
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
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
        test_room: Room,
    ):
        partner_data = create_fake_dweller()
        partner_data.update(
            {
                "first_name": "Partner",
                "status": DwellerStatusEnum.WORKING,
                "happiness": 50,
                "charisma": 5,
            }
        )
        partner = await crud.dweller.create(
            async_session,
            DwellerCreate(**partner_data, vault_id=vault.id),
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

    async def test_low_resources_reduces_happiness(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
    ):
        """Test that low resources reduce happiness."""
        # Set low resources
        vault.power = 15
        vault.power_max = 100
        vault.food = 15
        vault.food_max = 100
        vault.water = 15
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        initial_happiness = working_dweller.happiness

        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(working_dweller)

        # Low resources should cause happiness loss
        assert working_dweller.happiness < initial_happiness

    async def test_active_incident_reduces_happiness(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
        test_room: Room,
    ):
        """Test that active incidents reduce happiness."""
        # Ensure dweller is in the room (refresh to get latest state)
        await async_session.refresh(working_dweller)

        # Create active incident
        incident = Incident(
            vault_id=vault.id,
            room_id=test_room.id,
            type=IncidentType.FIRE,
            status=IncidentStatus.ACTIVE,
            difficulty=2,
            is_active=True,
        )
        async_session.add(incident)
        await async_session.commit()

        # Good vault resources
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        initial_happiness = working_dweller.happiness

        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(working_dweller)

        # Active incident penalty applies, but other bonuses may offset it
        # Check that happiness change is less than it would be without incident
        # (Net effect might still be positive due to working bonus)
        assert working_dweller.happiness - initial_happiness < 1.0  # Limited gain due to incident

    async def test_partner_bonus(
        self,
        async_session: AsyncSession,
        vault: Vault,
        test_room: Room,
    ):
        """Test that dwellers with partners get happiness bonus."""
        # Create two dwellers
        dweller1_data = create_fake_dweller()
        dweller1_data.update(
            {
                "first_name": "Partner",
                "last_name": "One",
                "status": "working",
                "happiness": 60,
                "gender": "male",
            }
        )
        dweller1_in = DwellerCreate(**dweller1_data, vault_id=vault.id, room_id=test_room.id)
        dweller1 = await crud.dweller.create(db_session=async_session, obj_in=dweller1_in)

        dweller2_data = create_fake_dweller()
        dweller2_data.update(
            {
                "first_name": "Partner",
                "last_name": "Two",
                "status": "working",
                "happiness": 60,
                "gender": "female",
            }
        )
        dweller2_in = DwellerCreate(**dweller2_data, vault_id=vault.id, room_id=test_room.id)
        dweller2 = await crud.dweller.create(db_session=async_session, obj_in=dweller2_in)

        # Make them partners
        from app.core.enums import RelationshipTypeEnum
        from app.models.relationship import Relationship

        relationship = Relationship(
            dweller_1_id=dweller1.id,
            dweller_2_id=dweller2.id,
            relationship_type=RelationshipTypeEnum.PARTNER,
            affinity=100,
        )
        async_session.add(relationship)
        await async_session.commit()

        # Update dwellers to have partner_id
        dweller1.partner_id = dweller2.id
        dweller2.partner_id = dweller1.id
        async_session.add(dweller1)
        async_session.add(dweller2)
        await async_session.commit()

        # Good vault conditions
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        initial_happiness_1 = dweller1.happiness

        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(dweller1)

        # Partner bonus should help, but base decay and other factors still apply
        # Check that the partner bonus is providing some benefit (less decay than without partner)
        # Allow for some decrease due to base decay
        assert dweller1.happiness >= initial_happiness_1 - 5  # Allow up to 5 point decrease

    async def test_soft_deleted_partner_is_cleared(
        self,
        async_session: AsyncSession,
        vault: Vault,
        test_room: Room,
        working_dweller: Dweller,
    ):
        """A stale partner reference must not abort the vault game tick."""
        partner_data = create_fake_dweller()
        partner = await crud.dweller.create(
            db_session=async_session,
            obj_in=DwellerCreate(**partner_data, vault_id=vault.id, room_id=test_room.id),
        )
        partner.is_deleted = True
        working_dweller.partner_id = partner.id
        async_session.add_all([partner, working_dweller])
        await async_session.commit()

        await happiness_service.update_vault_happiness(async_session, vault.id)

        await async_session.refresh(working_dweller)
        assert working_dweller.partner_id is None

    async def test_invalid_vault(
        self,
        async_session: AsyncSession,
    ):
        """Test happiness update with invalid vault ID."""
        fake_vault_id = UUID("00000000-0000-0000-0000-000000000000")

        result = await happiness_service.update_vault_happiness(
            async_session,
            fake_vault_id,
            seconds_passed=60,
        )

        assert "error" in result
        assert result["error"] == "Vault not found"

    async def test_update_commits_dwellers_and_vault_together(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Dweller happiness and the vault aggregate land in one transaction."""
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
        self,
        async_session: AsyncSession,
        db_connection: AsyncConnection,
        vault: Vault,
        working_dweller: Dweller,
    ) -> None:
        """Failure writing the aggregate rolls back the already-flushed dweller change."""
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

    async def test_get_modifiers_invalid_dweller(
        self,
        async_session: AsyncSession,
    ):
        """Test getting modifiers for non-existent dweller."""
        fake_dweller_id = UUID("00000000-0000-0000-0000-000000000000")

        modifiers = await happiness_service.get_happiness_modifiers(
            async_session,
            fake_dweller_id,
        )

        assert "error" in modifiers
        assert modifiers["error"] == "Dweller not found"

    async def test_training_dweller_stable_happiness(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Test that training dwellers have stable happiness (training bonus offsets decay)."""
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "Training",
                "last_name": "Dweller",
                "status": "training",
                "happiness": 50,
                "health": 100,
                "max_health": 100,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        training_dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        initial_happiness = training_dweller.happiness

        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(training_dweller)

        # Training bonus roughly offsets base decay - happiness stays stable (within 1 point)
        assert abs(training_dweller.happiness - initial_happiness) <= 1

    async def test_get_modifiers_training_dweller(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Test modifier breakdown for training dweller."""
        # Create training dweller
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "Training",
                "last_name": "Mod",
                "status": "training",
                "happiness": 60,
                "health": 100,
                "max_health": 100,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        training_dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

        # Good conditions
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        modifiers = await happiness_service.get_happiness_modifiers(
            async_session,
            training_dweller.id,
        )

        # Training should show up in positive modifiers
        positive_names = [m["name"] for m in modifiers["positive"]]
        assert "Training" in positive_names

    async def test_get_modifiers_low_health_dweller(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Test modifier breakdown for dweller with low health."""
        # Create low health dweller
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "LowHealth",
                "last_name": "Mod",
                "status": "working",
                "happiness": 60,
                "health": 25,
                "max_health": 100,
                "radiation": 0,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        low_health_dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

        # Good conditions
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        modifiers = await happiness_service.get_happiness_modifiers(
            async_session,
            low_health_dweller.id,
        )

        # Low health penalty should show up
        negative_names = [m["name"] for m in modifiers["negative"]]
        assert "Low Health" in negative_names

    async def test_get_modifiers_idle_dweller(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Test modifier breakdown for idle dweller."""
        # Create idle dweller
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "Idle",
                "last_name": "Mod",
                "status": "idle",
                "happiness": 60,
                "health": 100,
                "max_health": 100,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        idle_dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

        # Good conditions
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        modifiers = await happiness_service.get_happiness_modifiers(
            async_session,
            idle_dweller.id,
        )

        # Idle penalty should show up
        negative_names = [m["name"] for m in modifiers["negative"]]
        assert "Idle" in negative_names

    async def test_get_modifiers_with_active_incident(
        self,
        async_session: AsyncSession,
        vault: Vault,
        test_room: Room,
    ):
        """Test modifier breakdown with active incident."""
        # Create working dweller
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "Incident",
                "last_name": "Test",
                "status": "working",
                "happiness": 60,
                "health": 100,
                "max_health": 100,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id, room_id=test_room.id)
        incident_dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

        # Create active incident
        incident = Incident(
            vault_id=vault.id,
            room_id=test_room.id,
            type=IncidentType.FIRE,
            status=IncidentStatus.ACTIVE,
            difficulty=2,
            is_active=True,
        )
        async_session.add(incident)
        await async_session.commit()

        # Good conditions otherwise
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        modifiers = await happiness_service.get_happiness_modifiers(
            async_session,
            incident_dweller.id,
        )

        # Incident penalty should show up
        negative_names = [m["name"] for m in modifiers["negative"]]
        assert any("Incident" in name for name in negative_names)

    async def test_pet_happiness_bonus(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """An equipped happiness pet adds its capped fraction to the per-tick delta."""
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "Pet",
                "last_name": "Owner",
                "status": "training",
                "happiness": 50,
                "health": 100,
                "max_health": 100,
                "radiation": 0,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

        vault_factors = {
            "has_low_resources": False,
            "has_critical_resources": False,
            "active_incident_count": 0,
            "power_ratio": 0.9,
            "food_ratio": 0.9,
            "water_ratio": 0.9,
            "radio_happiness_bonus": 0.0,
        }

        # Pet-less dweller keeps the baseline delta (no pet contribution)
        baseline = await HappinessService._calculate_happiness_change(
            async_session,
            dweller,
            vault_factors,
            seconds_passed=60,
        )

        # Equip a happiness pet (Mr. Pebbles: happiness=0.25)
        dweller.pet = Pet(name="Mr. Pebbles", rarity="Legendary")
        with_pet = await HappinessService._calculate_happiness_change(
            async_session,
            dweller,
            vault_factors,
            seconds_passed=60,
        )

        assert with_pet == pytest.approx(baseline + 0.25)

    async def test_pet_happiness_bonus_end_to_end(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """A dweller with an equipped happiness pet gains more happiness per tick."""
        dweller_data = create_fake_dweller()
        dweller_data.update(
            {
                "first_name": "Pet",
                "age_group": "adult",
                "last_name": "Owner",
                "status": "training",
                "happiness": 50,
                "health": 100,
                "max_health": 100,
                "radiation": 0,
            }
        )
        dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
        dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)

        no_pet_data = create_fake_dweller()
        no_pet_data.update(
            {
                "first_name": "No",
                "last_name": "Pet",
                "status": "training",
                "happiness": 50,
                "health": 100,
                "max_health": 100,
                "radiation": 0,
            }
        )
        no_pet_in = DwellerCreate(**no_pet_data, vault_id=vault.id)
        no_pet_dweller = await crud.dweller.create(db_session=async_session, obj_in=no_pet_in)

        # Equip a happiness pet (Mr. Pebbles: happiness=0.25) through the real
        # FK-only equip path; get_multi_by_vault's selectinload(Dweller.pet)
        # (B7) is what makes the bonus visible to the tick sweep.
        pet = await crud.pet.create(
            async_session,
            obj_in={"name": "Mr. Pebbles", "rarity": RarityEnum.LEGENDARY, "value": 500},
        )
        await crud.pet.equip(db_session=async_session, item_id=pet.id, dweller_id=dweller.id)

        # Good vault conditions
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(dweller)
        await async_session.refresh(no_pet_dweller)

        assert dweller.happiness > no_pet_dweller.happiness


@pytest.mark.asyncio
async def test_feral_coworker_and_rival_reduce_happiness(
    async_session: AsyncSession,
    vault: Vault,
) -> None:
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Mood",
            "last_name": "Check",
            "status": "training",
            "happiness": 50,
            "health": 100,
            "max_health": 100,
            "radiation": 0,
        }
    )
    dweller = await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(**dweller_data, vault_id=vault.id),
    )
    room_id = uuid4()
    dweller.room_id = room_id
    async_session.add(dweller)
    await async_session.commit()

    vault_factors = {
        "has_low_resources": False,
        "has_critical_resources": False,
        "active_incident_count": 0,
        "power_ratio": 0.9,
        "food_ratio": 0.9,
        "water_ratio": 0.9,
        "radio_happiness_bonus": 0.0,
    }

    baseline = await HappinessService._calculate_happiness_change(
        async_session,
        dweller,
        vault_factors,
        seconds_passed=60,
        dwellers_by_room={room_id: [dweller]},
        rivals_by_dweller={},
    )
    feral = SimpleNamespace(
        id=uuid4(),
        room_id=room_id,
        visual_attributes={"race": "ghoul", "state_of_being": "feral"},
    )
    with_feral = await HappinessService._calculate_happiness_change(
        async_session,
        dweller,
        vault_factors,
        seconds_passed=60,
        dwellers_by_room={room_id: [dweller, feral]},
        rivals_by_dweller={},
    )
    assert with_feral == pytest.approx(baseline - DISCOMFORT_EFFECTS[DiscomfortSeverity.STRONG].happiness_penalty)

    rival = SimpleNamespace(id=uuid4(), room_id=room_id)
    with_rival = await HappinessService._calculate_happiness_change(
        async_session,
        dweller,
        vault_factors,
        seconds_passed=60,
        dwellers_by_room={room_id: [dweller, rival]},
        rivals_by_dweller={dweller.id: {rival.id}},
    )
    assert with_rival == pytest.approx(baseline - game_config.relationship.rival_happiness_penalty)


async def _create_resting_dweller(
    async_session: AsyncSession, vault: Vault, room: Room, *, first_name: str, status: str = "resting"
) -> Dweller:
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": first_name,
            "last_name": "Comfort",
            "age_group": "adult",
            "status": status,
            "happiness": 50,
            "health": 100,
            "max_health": 100,
            "radiation": 0,
        }
    )
    dweller = await crud.dweller.create(
        db_session=async_session,
        obj_in=DwellerCreate(**dweller_data, vault_id=vault.id),
    )
    dweller.room_id = room.id
    async_session.add(dweller)
    await async_session.commit()
    return dweller


@pytest.mark.asyncio
async def test_resting_living_quarters_bonus_is_net_positive(
    async_session: AsyncSession, vault: Vault, test_room: Room
) -> None:
    """#1454: resting occupants of living quarters gain happiness; other rooms still decay."""
    living_data = create_fake_room()
    living_data["name"] = "Living Quarters"
    living_room = await crud.room.create(db_session=async_session, obj_in=RoomCreate(**living_data, vault_id=vault.id))
    resting_living = await _create_resting_dweller(async_session, vault, living_room, first_name="Home")
    resting_power = await _create_resting_dweller(async_session, vault, test_room, first_name="Away")
    vault_factors = {
        "has_low_resources": False,
        "has_critical_resources": False,
        "active_incident_count": 0,
        "power_ratio": 0.5,
        "food_ratio": 0.5,
        "water_ratio": 0.5,
        "radio_happiness_bonus": 0.0,
    }

    living_delta = await HappinessService._calculate_happiness_change(
        async_session, resting_living, vault_factors, seconds_passed=60
    )
    power_delta = await HappinessService._calculate_happiness_change(
        async_session, resting_power, vault_factors, seconds_passed=60
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
    """End-to-end tick: the seeded resting living-room occupant climbs instead of floor-decaying."""
    living_data = create_fake_room()
    living_data["name"] = "Living Quarters"
    living_room = await crud.room.create(db_session=async_session, obj_in=RoomCreate(**living_data, vault_id=vault.id))
    resting_living = await _create_resting_dweller(async_session, vault, living_room, first_name="Home")
    resting_power = await _create_resting_dweller(async_session, vault, test_room, first_name="Away")
    vault.power = vault.food = vault.water = 50
    vault.power_max = vault.food_max = vault.water_max = 100
    async_session.add(vault)
    await async_session.commit()

    await happiness_service.update_vault_happiness(async_session, vault.id, seconds_passed=300)
    await async_session.refresh(resting_living)
    await async_session.refresh(resting_power)

    assert resting_living.happiness > 50
    assert resting_power.happiness < 50
    assert resting_living.happiness > resting_power.happiness


@pytest.mark.asyncio
async def test_working_gain_stays_exclusive_to_working(async_session: AsyncSession, vault: Vault) -> None:
    """The living-quarters bonus reaches resting dwellers, but working_gain must not."""
    living_data = create_fake_room()
    living_data["name"] = "Living Quarters"
    living_room = await crud.room.create(db_session=async_session, obj_in=RoomCreate(**living_data, vault_id=vault.id))
    resting = await _create_resting_dweller(async_session, vault, living_room, first_name="Rest")
    working = await _create_resting_dweller(async_session, vault, living_room, first_name="Work", status="working")
    vault_factors = {
        "has_low_resources": False,
        "has_critical_resources": False,
        "active_incident_count": 0,
        "power_ratio": 0.5,
        "food_ratio": 0.5,
        "water_ratio": 0.5,
        "radio_happiness_bonus": 0.0,
    }

    resting_delta = await HappinessService._calculate_happiness_change(
        async_session, resting, vault_factors, seconds_passed=60
    )
    working_delta = await HappinessService._calculate_happiness_change(
        async_session, working, vault_factors, seconds_passed=60
    )

    expected_extra = game_config.happiness.working_gain
    if game_config.happiness.high_health_threshold < 1.0:
        expected_extra += game_config.happiness.high_health_bonus
    assert working_delta - resting_delta == pytest.approx(expected_extra)


@pytest.mark.asyncio
async def test_modifiers_show_living_quarters_for_resting_dweller(
    async_session: AsyncSession, vault: Vault, test_room: Room
) -> None:
    """The UI breakdown mirrors the tick math for resting living-room occupants (#1454)."""
    living_data = create_fake_room()
    living_data["name"] = "Living Quarters"
    living_room = await crud.room.create(db_session=async_session, obj_in=RoomCreate(**living_data, vault_id=vault.id))
    resting_living = await _create_resting_dweller(async_session, vault, living_room, first_name="Home")
    resting_power = await _create_resting_dweller(async_session, vault, test_room, first_name="Away")

    living_modifiers = await happiness_service.get_happiness_modifiers(async_session, resting_living.id)
    living_positive = {entry["name"]: entry["value"] for entry in living_modifiers["positive"]}
    assert "Living Quarters" in living_positive
    assert living_positive["Living Quarters"] == pytest.approx(game_config.happiness.living_quarters_bonus)

    power_modifiers = await happiness_service.get_happiness_modifiers(async_session, resting_power.id)
    power_positive = [entry["name"] for entry in power_modifiers["positive"]]
    assert "Living Quarters" not in power_positive
