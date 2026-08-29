from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.crud.resource import VaultResourceData
from app.models import Dweller, Storage
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.vault import ResourceLevelWarning, ResourceProduction, ResourceTickEvents
from app.services.resource_manager import ResourceManager
from app.utils.resource_warnings import get_resource_warnings


class TestResourceManager:
    def test_check_resource_warnings(self):
        vault = Vault(power_max=100, food_max=100, water_max=100)

        # Test normal levels
        resources = {"power": 50.0, "food": 50.0, "water": 50.0}
        warnings = get_resource_warnings(vault, resources)
        assert len(warnings) == 0

        # Test low power (19%)
        resources = {"power": 19.0, "food": 50.0, "water": 50.0}
        warnings = get_resource_warnings(vault, resources)
        assert len(warnings) == 1
        assert isinstance(warnings[0], ResourceLevelWarning)
        assert warnings[0].type == "low_power"

        # Test critical power (4%)
        resources = {"power": 4.0, "food": 50.0, "water": 50.0}
        warnings = get_resource_warnings(vault, resources)
        assert len(warnings) == 1
        assert warnings[0].type == "critical_power"

        # Test multiple warnings
        resources = {"power": 4.0, "food": 19.0, "water": 50.0}
        warnings = get_resource_warnings(vault, resources)
        assert len(warnings) == 2
        types = [warning.type for warning in warnings]
        assert "critical_power" in types
        assert "low_food" in types

    def test_apprentice_does_not_contribute_to_production(self):
        room = Room(
            name="Power",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            output=10.0,
            tier=1,
            size=1,
        )
        worker = Dweller(strength=10)
        apprentice = Dweller(strength=10, apprentice_stat=SPECIALEnum.STRENGTH)

        production = ResourceManager()._calculate_room_production(room, [worker, apprentice], seconds_passed=60)

        assert production == 600

    @pytest.mark.asyncio
    async def test_power_outage_production(self):
        manager = ResourceManager()

        # Create mock rooms
        power_room = Room(
            name="Power", category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.STRENGTH, output=10.0, tier=1, size=1
        )
        food_room = Room(
            name="Diner", category=RoomTypeEnum.PRODUCTION, ability=SPECIALEnum.AGILITY, output=10.0, tier=1, size=1
        )

        from app.models.dweller import Dweller

        strong_dweller = Dweller(strength=10)
        agile_dweller = Dweller(agility=10)

        rooms_with_dwellers = [(power_room, [strong_dweller]), (food_room, [agile_dweller])]

        # Scenario 1: Sufficient Power
        production_normal = manager._calculate_production(rooms_with_dwellers, seconds_passed=60, current_power=10)
        assert production_normal["power"] > 0
        assert production_normal["food"] > 0

        # Scenario 2: Power Outage
        production_outage = manager._calculate_production(rooms_with_dwellers, seconds_passed=60, current_power=0)
        assert production_outage["power"] > 0  # Power plants still work
        assert production_outage["food"] == 0  # Diners stop working

    @pytest.mark.asyncio
    async def test_emit_production_events_uses_positive_integer_amounts(self, vault: Vault):
        events = ResourceTickEvents(production=ResourceProduction(power=1.9, food=0, water=-1, stimpack=2))

        with patch("app.services.resource_manager.event_bus.emit", new_callable=AsyncMock) as emit:
            await ResourceManager.emit_production_events(vault.id, events)

        assert emit.await_count == 2
        assert emit.await_args_list[0].args[2] == {"resource_type": "power", "amount": 1}
        assert emit.await_args_list[1].args[2] == {"resource_type": "stimpack", "amount": 2}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("starting_stimpacks", "capacity", "output", "expected_delta"), [(4, 5, 33, 1), (5, 5, 100, 0)]
    )
    async def test_medical_events_match_persisted_storage_change(
        self, vault: Vault, starting_stimpacks: int, capacity: int, output: int, expected_delta: int
    ) -> None:
        """Medical collection events must match rounded, capacity-limited storage changes."""
        vault.power = 10
        storage = Storage(vault_id=vault.id, stimpack=starting_stimpacks)
        medbay = Room(
            name="Medbay",
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.INTELLIGENCE,
            output=output,
            capacity=capacity,
            tier=1,
            size=1,
        )
        resource_data = VaultResourceData(
            vault=vault,
            storage=storage,
            rooms=[medbay],
            dweller_count=0,
            rooms_with_dwellers=[(medbay, [Dweller(intelligence=1)])],
        )

        with (
            patch(
                "app.services.resource_manager.resource_crud.get_vault_resource_data",
                new_callable=AsyncMock,
                return_value=resource_data,
            ),
            patch("app.services.resource_manager.event_bus.emit", new_callable=AsyncMock) as emit,
        ):
            _, events = await ResourceManager().process_vault_resources(MagicMock(), vault.id, 60)
            await ResourceManager.emit_production_events(vault.id, events)

        medical_amounts = [
            call.args[2]["amount"] for call in emit.await_args_list if call.args[2]["resource_type"] == "stimpack"
        ]
        assert storage.stimpack == starting_stimpacks + expected_delta
        assert medical_amounts == ([expected_delta] if expected_delta else [])
