"""Enhanced resource management system for vault resources."""

import logging
from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Dweller, Room, Vault
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.vault import VaultUpdate

logger = logging.getLogger(__name__)

# Resource rates per second
POWER_CONSUMPTION_RATE = 0.5 / 60  # Per room size per tier per second
FOOD_CONSUMPTION_PER_DWELLER = 0.36 / 60  # Per dweller per second
WATER_CONSUMPTION_PER_DWELLER = 0.36 / 60  # Per dweller per second

# Production rates
BASE_PRODUCTION_RATE = 0.1  # Base production per SPECIAL point per second
TIER_MULTIPLIER = {1: 1.0, 2: 1.5, 3: 2.0}  # Production multiplier by room tier

# Thresholds
LOW_RESOURCE_THRESHOLD = 0.2  # 20% of max
CRITICAL_RESOURCE_THRESHOLD = 0.05  # 5% of max


class ResourceManager:
    """Manages vault resource production, consumption, and state."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def process_vault_resources(
        self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int
    ) -> tuple[VaultUpdate, dict]:
        """
        Process resource changes for a vault over the given time period.

        Returns:
            tuple: (VaultUpdate with new resource levels, dict with warnings/events)
        """
        vault, rooms, dweller_count, rooms_with_dwellers = await self._get_vault_data(db_session, vault_id)

        # Calculate net resource changes
        resource_update, events = await self._calculate_net_resource_change(
            vault, rooms, dweller_count, rooms_with_dwellers, seconds_passed
        )

        return resource_update, events

    async def _calculate_net_resource_change(
        self,
        vault: Vault,
        rooms: Sequence[Room],
        dweller_count: int,
        rooms_with_dwellers: list[tuple[Room, list[Dweller]]],
        seconds_passed: int,
    ) -> tuple[VaultUpdate, dict]:
        """
        Calculate net resource change considering production, consumption, and efficiency.

        Returns:
            tuple: (VaultUpdate, dict with events/warnings)
        """
        events = {"warnings": [], "production": {}, "consumption": {}}

        # Calculate consumption
        consumption = self._calculate_consumption(rooms, dweller_count, seconds_passed)
        events["consumption"] = consumption

        # Calculate production
        production = self._calculate_production(rooms_with_dwellers, seconds_passed, vault.power)
        events["production"] = production

        # Calculate new resource levels
        new_resources = self._apply_resource_changes(vault, consumption, production)

        # Check for warnings
        warnings = self._check_resource_warnings(vault, new_resources)
        events["warnings"] = warnings

        # Log resource changes
        self._log_resource_changes(vault, new_resources)

        return (
            VaultUpdate(
                power=round(new_resources["power"]),
                food=round(new_resources["food"]),
                water=round(new_resources["water"]),
            ),
            events,
        )

    def _calculate_consumption(
        self, rooms: Sequence[Room], dweller_count: int, seconds_passed: int
    ) -> dict[str, float]:
        """Calculate resource consumption for power, food, and water."""
        power_consumption = sum(
            POWER_CONSUMPTION_RATE * room.size * room.tier * seconds_passed for room in rooms if room.size
        )
        food_consumption = dweller_count * FOOD_CONSUMPTION_PER_DWELLER * seconds_passed
        water_consumption = dweller_count * WATER_CONSUMPTION_PER_DWELLER * seconds_passed

        return {
            "power": round(power_consumption, 2),
            "food": round(food_consumption, 2),
            "water": round(water_consumption, 2),
        }

    def _calculate_production(
        self, rooms_with_dwellers: list[tuple[Room, list[Dweller]]], seconds_passed: int, current_power: int
    ) -> dict[str, float]:
        """Calculate resource production from all production rooms."""
        production_totals = {"power": 0.0, "food": 0.0, "water": 0.0}

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
            self._apply_room_production(room.ability, production, production_totals)

        return {k: round(v, 2) for k, v in production_totals.items()}

    def _calculate_room_production(self, room: Room, dwellers: list[Dweller], seconds_passed: int) -> float:
        """Calculate production for a single room based on dweller stats and room tier."""
        ability_sum = sum(getattr(dweller, room.ability.lower(), 0) for dweller in dwellers)
        tier_mult = TIER_MULTIPLIER.get(room.tier, 1.0)
        production = room.output * ability_sum * BASE_PRODUCTION_RATE * tier_mult * seconds_passed

        self.logger.info(
            f"Room {room.name} producing: output={room.output}, ability_sum={ability_sum}, "
            f"production={production:.2f} (tier={room.tier}, dwellers={len(dwellers)})"
        )

        return production

    @staticmethod
    def _apply_room_production(ability: SPECIALEnum, production: float, totals: dict[str, float]) -> None:
        """Apply production to the appropriate resource type based on room ability."""
        match ability:
            case SPECIALEnum.STRENGTH:  # Power plants
                totals["power"] += production
            case SPECIALEnum.AGILITY:  # Gardens/Diners
                totals["food"] += production
            case SPECIALEnum.PERCEPTION:  # Water treatment
                totals["water"] += production
            case SPECIALEnum.ENDURANCE:  # Special rooms that produce all
                for resource in totals:
                    totals[resource] += production / 3

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

    @staticmethod
    def _check_resource_warnings(vault: Vault, new_resources: dict[str, float]) -> list[dict[str, str]]:
        """Check for low or critical resource warnings."""
        warnings = []

        resource_checks = [
            ("power", vault.power_max, "Power"),
            ("food", vault.food_max, "Food"),
            ("water", vault.water_max, "Water"),
        ]

        for resource, max_value, label in resource_checks:
            if new_resources[resource] < max_value * CRITICAL_RESOURCE_THRESHOLD:
                warnings.append({"type": f"critical_{resource}", "message": f"{label} critically low!"})
            elif new_resources[resource] < max_value * LOW_RESOURCE_THRESHOLD:
                warnings.append({"type": f"low_{resource}", "message": f"{label} running low"})

        return warnings

    def _log_resource_changes(self, vault: Vault, new_resources: dict[str, float]) -> None:
        """Log resource changes for debugging."""
        self.logger.debug(
            f"Vault {vault.id}: Power {vault.power:.0f} -> {new_resources['power']:.0f}, "
            f"Food {vault.food:.0f} -> {new_resources['food']:.0f}, "
            f"Water {vault.water:.0f} -> {new_resources['water']:.0f}"
        )

    @staticmethod
    async def _get_vault_data(db_session: AsyncSession, vault_id: UUID4):
        """
        Fetch vault data with optimized queries.

        Returns:
            tuple: (vault, rooms, dweller_count, rooms_with_dwellers)
        """
        # Get vault
        vault_query = select(Vault).where(Vault.id == vault_id)
        vault = (await db_session.execute(vault_query)).scalars().first()

        if not vault:
            raise ValueError(f"Vault {vault_id} not found")

        # Get all rooms
        rooms_query = select(Room).where(Room.vault_id == vault_id)
        rooms = (await db_session.execute(rooms_query)).scalars().all()

        # Count dwellers
        dweller_count = (
            await db_session.execute(select(func.count(Dweller.id)).where(Dweller.vault_id == vault_id))
        ).scalar()

        # Get rooms with assigned dwellers
        rooms_with_dwellers_query = (
            select(Room, Dweller).join(Dweller, Room.id == Dweller.room_id).where(Room.vault_id == vault_id)
        )
        rooms_with_dwellers_result = (await db_session.execute(rooms_with_dwellers_query)).all()

        # Group dwellers by room
        rooms_with_dwellers_dict = {}
        for room, dweller in rooms_with_dwellers_result:
            if room.id not in rooms_with_dwellers_dict:
                rooms_with_dwellers_dict[room.id] = (room, [])
            rooms_with_dwellers_dict[room.id][1].append(dweller)

        return vault, rooms, dweller_count or 0, list(rooms_with_dwellers_dict.values())

    async def check_resource_availability(self, vault: Vault) -> dict[str, bool]:
        """
        Check if vault has sufficient resources for basic operations.

        Returns:
            dict: Resource availability status
        """
        return {
            "power": vault.power > 0,
            "food": vault.food > 0,
            "water": vault.water > 0,
            "any_critical": (
                vault.power < vault.power_max * CRITICAL_RESOURCE_THRESHOLD
                or vault.food < vault.food_max * CRITICAL_RESOURCE_THRESHOLD
                or vault.water < vault.water_max * CRITICAL_RESOURCE_THRESHOLD
            ),
        }
