from unittest.mock import AsyncMock, patch

import pytest

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
