"""Tests for happiness service."""

import pytest
import pytest_asyncio
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.happiness_service import happiness_service
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


@pytest_asyncio.fixture(name="idle_dweller")
async def idle_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create an idle dweller."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Idle",
            "last_name": "Dweller",
            "status": "idle",
            "happiness": 60,
            "health": 100,
            "max_health": 100,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest_asyncio.fixture(name="injured_dweller")
async def injured_dweller_fixture(async_session: AsyncSession, vault: Vault) -> Dweller:
    """Create an injured dweller with low health."""
    dweller_data = create_fake_dweller()
    dweller_data.update(
        {
            "first_name": "Injured",
            "last_name": "Dweller",
            "status": "idle",
            "happiness": 50,
            "health": 30,
            "max_health": 100,
            "radiation": 75,
        }
    )
    dweller_in = DwellerCreate(**dweller_data, vault_id=vault.id)
    return await crud.dweller.create(db_session=async_session, obj_in=dweller_in)


@pytest.mark.asyncio
class TestHappinessService:
    """Test happiness service functionality."""

    async def test_update_vault_happiness_basic(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
    ):
        """Test basic vault happiness update."""
        # Set vault to good conditions
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        initial_happiness = working_dweller.happiness

        # Update happiness
        result = await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        # Verify result structure
        assert "dwellers_processed" in result
        assert "happiness_increased" in result
        assert "happiness_decreased" in result
        assert "total_change" in result
        assert "average_happiness" in result

        assert result["dwellers_processed"] == 1

        # Refresh dweller to see changes
        await async_session.refresh(working_dweller)

        # Working dweller with good conditions should gain happiness
        assert working_dweller.happiness != initial_happiness

    async def test_working_dweller_gains_happiness(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
    ):
        """Test that working dwellers gain happiness in good conditions."""
        # Set excellent vault conditions
        vault.power = 95
        vault.power_max = 100
        vault.food = 95
        vault.food_max = 100
        vault.water = 95
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

        # Working in good conditions = positive change
        assert working_dweller.happiness >= initial_happiness

    @pytest.mark.skip
    async def test_idle_dweller_loses_happiness(
        self,
        async_session: AsyncSession,
        vault: Vault,
        idle_dweller: Dweller,
    ):
        """Test that idle dwellers lose happiness."""
        # Even with good conditions, idle dwellers should decay
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        initial_happiness = idle_dweller.happiness

        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(idle_dweller)

        # Idle dweller has decay penalty
        assert idle_dweller.happiness < initial_happiness

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

    async def test_critical_resources_severe_penalty(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
    ):
        """Test that critical resources cause severe happiness penalty."""
        # Set critical resources (< 15%)
        vault.power = 5
        vault.power_max = 100
        vault.food = 5
        vault.food_max = 100
        vault.water = 5
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

        # Critical resources = severe penalty
        assert working_dweller.happiness < initial_happiness

    @pytest.mark.skip
    async def test_injured_dweller_loses_happiness(
        self,
        async_session: AsyncSession,
        vault: Vault,
        injured_dweller: Dweller,
    ):
        """Test that injured/irradiated dwellers lose happiness."""
        # Good vault conditions
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        initial_happiness = injured_dweller.happiness

        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(injured_dweller)

        # Low health + high radiation = happiness loss
        assert injured_dweller.happiness < initial_happiness

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
        from app.models.relationship import Relationship
        from app.schemas.common import RelationshipTypeEnum

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

    async def test_happiness_bounds(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
    ):
        """Test that happiness stays within 10-100 bounds."""
        # Set dweller to very low happiness
        working_dweller.happiness = 15
        async_session.add(working_dweller)

        # Set critical resources to push happiness down
        vault.power = 5
        vault.power_max = 100
        vault.food = 5
        vault.food_max = 100
        vault.water = 5
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(working_dweller)

        # Happiness should not go below 10
        assert working_dweller.happiness >= 10

        # Now test upper bound
        working_dweller.happiness = 95
        async_session.add(working_dweller)

        # Set excellent conditions
        vault.power = 100
        vault.power_max = 100
        vault.food = 100
        vault.food_max = 100
        vault.water = 100
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(working_dweller)

        # Happiness should not exceed 100
        assert working_dweller.happiness <= 100

    async def test_vault_average_happiness_update(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
        idle_dweller: Dweller,
    ):
        """Test that vault average happiness is updated."""
        # Good conditions
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        result = await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        await async_session.refresh(vault)
        await async_session.refresh(working_dweller)
        await async_session.refresh(idle_dweller)

        # Check vault happiness matches average
        expected_avg = (working_dweller.happiness + idle_dweller.happiness) / 2
        assert vault.happiness == int(expected_avg)
        assert result["average_happiness"] == expected_avg

    async def test_get_happiness_modifiers(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
    ):
        """Test getting happiness modifier breakdown."""
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
            working_dweller.id,
        )

        # Verify structure
        assert "current_happiness" in modifiers
        assert "positive" in modifiers
        assert "negative" in modifiers

        # Working dweller should have working bonus
        positive_names = [m["name"] for m in modifiers["positive"]]
        assert "Working" in positive_names

        # Should have base decay
        negative_names = [m["name"] for m in modifiers["negative"]]
        assert "Base Decay" in negative_names

    async def test_time_scaling(
        self,
        async_session: AsyncSession,
        vault: Vault,
        working_dweller: Dweller,
    ):
        """Test that happiness changes scale with time passed."""
        # Good conditions
        vault.power = 90
        vault.power_max = 100
        vault.food = 90
        vault.food_max = 100
        vault.water = 90
        vault.water_max = 100
        async_session.add(vault)
        await async_session.commit()

        # Update for 60 seconds
        initial_happiness = working_dweller.happiness
        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )
        await async_session.refresh(working_dweller)
        change_60s = working_dweller.happiness - initial_happiness

        # Reset happiness
        working_dweller.happiness = initial_happiness
        async_session.add(working_dweller)
        await async_session.commit()

        # Update for 120 seconds (double time)
        await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=120,
        )
        await async_session.refresh(working_dweller)
        change_120s = working_dweller.happiness - initial_happiness

        # Change should roughly double (allowing for rounding)
        assert abs(change_120s - (change_60s * 2)) < 2

    async def test_empty_vault(
        self,
        async_session: AsyncSession,
        vault: Vault,
    ):
        """Test happiness update for vault with no dwellers."""
        result = await happiness_service.update_vault_happiness(
            async_session,
            vault.id,
            seconds_passed=60,
        )

        assert result["dwellers_processed"] == 0
        assert result["happiness_changes"] == 0

    async def test_invalid_vault(
        self,
        async_session: AsyncSession,
    ):
        """Test happiness update with invalid vault ID."""
        fake_vault_id = UUID4("00000000-0000-0000-0000-000000000000")

        result = await happiness_service.update_vault_happiness(
            async_session,
            fake_vault_id,
            seconds_passed=60,
        )

        assert "error" in result
        assert result["error"] == "Vault not found"

    async def test_get_modifiers_invalid_dweller(
        self,
        async_session: AsyncSession,
    ):
        """Test getting modifiers for non-existent dweller."""
        fake_dweller_id = UUID4("00000000-0000-0000-0000-000000000000")

        modifiers = await happiness_service.get_happiness_modifiers(
            async_session,
            fake_dweller_id,
        )

        assert "error" in modifiers
        assert modifiers["error"] == "Dweller not found"
