"""Enhanced resource management system for vault resources."""

import logging
from collections.abc import Sequence

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import MEDICAL_ROOM_PRODUCTION, compute_medical_capacity, game_config
from app.crud.resource import resource as resource_crud
from app.models import Dweller, Room, Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.vault import (
    PrimaryResourceAmounts,
    ResourceProduction,
    ResourceTickEvents,
    VaultUpdate,
)
from app.services.event_bus import GameEvent, event_bus
from app.utils.resource_warnings import get_resource_warnings

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages vault resource production, consumption, and state."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def process_vault_resources(
        self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int
    ) -> tuple[VaultUpdate, ResourceTickEvents]:
        """Process resource changes for a vault over the given time period.

        Returns:
            tuple: Updated resource levels and typed tick events.
        """
        resource_data = await resource_crud.get_vault_resource_data(db_session, vault_id)

        resource_update, events = await self._calculate_net_resource_change(
            resource_data.vault,
            resource_data.rooms,
            resource_data.dweller_count,
            resource_data.rooms_with_dwellers,
            seconds_passed,
        )

        # Write medical production to Storage (separate from VaultUpdate)
        # Medical events must reflect the integer, capacity-limited amount that
        # actually reaches storage, rather than the fractional calculated output.
        production = events.production
        medical_production = {
            "stimpack": round(production.stimpack),
            "radaway": round(production.radaway),
        }
        events.production.stimpack = 0
        events.production.radaway = 0
        if resource_data.storage is not None:
            capacity = compute_medical_capacity(resource_data.rooms)
            if any(medical_production.values()):
                storage = resource_data.storage
                for resource_type, produced_amount in medical_production.items():
                    previous_amount = getattr(storage, resource_type)
                    stored_amount = min(previous_amount + produced_amount, capacity.get(resource_type, 0))
                    setattr(storage, resource_type, stored_amount)
                    setattr(events.production, resource_type, stored_amount - previous_amount)
                resource_crud.save_storage(db_session, storage)

        return resource_update, events

    async def _calculate_net_resource_change(
        self,
        vault: Vault,
        rooms: Sequence[Room],
        dweller_count: int,
        rooms_with_dwellers: list[tuple[Room, list[Dweller]]],
        seconds_passed: int,
    ) -> tuple[VaultUpdate, ResourceTickEvents]:
        """Calculate net resource change considering production, consumption, and efficiency.

        Returns:
            tuple: Updated resource levels and typed tick events.
        """
        consumption = self._calculate_consumption(rooms, dweller_count, seconds_passed)
        production = self._calculate_production(rooms_with_dwellers, seconds_passed, vault.power)
        new_resources = self._apply_resource_changes(vault, consumption, production)
        warnings = get_resource_warnings(vault, new_resources)

        self._log_resource_changes(vault, new_resources)

        return (
            VaultUpdate(
                power=round(new_resources["power"]),
                food=round(new_resources["food"]),
                water=round(new_resources["water"]),
            ),
            ResourceTickEvents(
                warnings=warnings,
                production=ResourceProduction(**production),
                consumption=PrimaryResourceAmounts(**consumption),
            ),
        )

    def _calculate_consumption(
        self, rooms: Sequence[Room], dweller_count: int, seconds_passed: int
    ) -> dict[str, float]:
        """Calculate resource consumption for power, food, and water."""
        power_consumption = sum(
            game_config.resource.power_consumption_rate * room.size * room.tier * seconds_passed
            for room in rooms
            if room.size
        )
        food_consumption = dweller_count * game_config.resource.food_consumption_per_dweller * seconds_passed
        water_consumption = dweller_count * game_config.resource.water_consumption_per_dweller * seconds_passed

        return {
            "power": round(power_consumption, 2),
            "food": round(food_consumption, 2),
            "water": round(water_consumption, 2),
        }

    def _calculate_production(
        self, rooms_with_dwellers: list[tuple[Room, list[Dweller]]], seconds_passed: int, current_power: int
    ) -> dict[str, float]:
        """Calculate resource production from all production rooms."""
        production_totals = {"power": 0.0, "food": 0.0, "water": 0.0, "stimpack": 0.0, "radaway": 0.0}

        for room, dwellers in rooms_with_dwellers:
            if room.category != RoomTypeEnum.PRODUCTION or not room.ability or not room.output:
                self.logger.debug(
                    f"Skipping room {room.name}: category={room.category}, ability={room.ability}, output={room.output}"
                )
                continue

            # Power outage effect: Only power generators work when power is 0
            if current_power <= 0 and room.ability != SPECIALEnum.STRENGTH:
                continue

            production = self._calculate_room_production(room, dwellers, seconds_passed)
            self._apply_room_production(room.name, room.ability, production, production_totals)

        return {k: round(v, 2) for k, v in production_totals.items()}

    def _calculate_room_production(self, room: Room, dwellers: list[Dweller], seconds_passed: int) -> float:
        """Calculate production from workers; apprentices train in a dedicated room slot."""
        ability = room.ability
        if ability is None:
            return 0.0

        workers = [dweller for dweller in dwellers if dweller.apprentice_stat is None]
        ability_sum = sum(getattr(dweller, ability.lower(), 0) for dweller in workers)
        tier_mult = game_config.resource.get_tier_multiplier(room.tier)
        rate = game_config.resource.base_production_rate
        if MEDICAL_ROOM_PRODUCTION.get(room.name.lower()):
            rate = game_config.resource.medical_production_rate
        production = room.output * ability_sum * rate * tier_mult * seconds_passed

        self.logger.info(
            f"Room {room.name} producing: output={room.output}, ability_sum={ability_sum}, "
            f"production={production:.2f} (tier={room.tier}, workers={len(workers)})"
        )

        return production

    @staticmethod
    def _apply_room_production(
        room_name: str, ability: SPECIALEnum, production: float, totals: dict[str, float]
    ) -> None:
        """Apply production to the appropriate resource type based on room ability."""
        match ability:
            case SPECIALEnum.STRENGTH:  # Power plants
                totals["power"] += production
            case SPECIALEnum.AGILITY:  # Gardens/Diners
                totals["food"] += production
            case SPECIALEnum.PERCEPTION:  # Water treatment
                totals["water"] += production
            case SPECIALEnum.INTELLIGENCE:  # Medbay and Science Lab
                product = MEDICAL_ROOM_PRODUCTION.get(room_name.lower())
                if product:
                    totals[product] += production
            case SPECIALEnum.ENDURANCE:
                base_resources = ["power", "food", "water"]
                per_share = production / len(base_resources)
                for resource in base_resources:
                    totals[resource] += per_share

    @staticmethod
    def _apply_resource_changes(
        vault: Vault, consumption: dict[str, float], production: dict[str, float]
    ) -> dict[str, float]:
        """Calculate new resource levels after applying consumption and production."""
        return {
            "power": max(0, min(vault.power - consumption["power"] + production["power"], vault.power_max)),
            "food": max(0, min(vault.food - consumption["food"] + production["food"], vault.food_max)),
            "water": max(0, min(vault.water - consumption["water"] + production["water"], vault.water_max)),
        }

    def _log_resource_changes(self, vault: Vault, new_resources: dict[str, float]) -> None:
        """Log resource changes for debugging."""
        self.logger.debug(
            f"Vault {vault.id}: Power {vault.power:.0f} -> {new_resources['power']:.0f}, "
            f"Food {vault.food:.0f} -> {new_resources['food']:.0f}, "
            f"Water {vault.water:.0f} -> {new_resources['water']:.0f}"
        )

    @staticmethod
    async def emit_production_events(vault_id: UUID4, events: ResourceTickEvents) -> None:
        """Emit objective events after the resource transaction has committed."""
        for resource_type, amount in events.production.model_dump().items():
            int_amount = int(amount)
            if int_amount > 0:
                await event_bus.emit(
                    GameEvent.RESOURCE_COLLECTED,
                    vault_id,
                    {"resource_type": resource_type, "amount": int_amount},
                )

    async def check_resource_availability(self, vault: Vault) -> dict[str, bool]:
        """Check if vault has sufficient resources for basic operations.

        Returns:
            dict: Resource availability status
        """
        return {
            "power": vault.power > 0,
            "food": vault.food > 0,
            "water": vault.water > 0,
            "any_critical": (
                vault.power < vault.power_max * game_config.resource.critical_threshold
                or vault.food < vault.food_max * game_config.resource.critical_threshold
                or vault.water < vault.water_max * game_config.resource.critical_threshold
            ),
        }
