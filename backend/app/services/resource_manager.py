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

    async def _calculate_net_resource_change(  # noqa: C901, PLR0912
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

        # Initialize resource deltas
        power_delta = 0
        food_delta = 0
        water_delta = 0

        # === CONSUMPTION ===
        power_consumption = sum(
            POWER_CONSUMPTION_RATE * room.size * room.tier * seconds_passed for room in rooms if room.size
        )
        food_consumption = dweller_count * FOOD_CONSUMPTION_PER_DWELLER * seconds_passed
        water_consumption = dweller_count * WATER_CONSUMPTION_PER_DWELLER * seconds_passed

        power_delta -= power_consumption
        food_delta -= food_consumption
        water_delta -= water_consumption

        events["consumption"] = {
            "power": round(power_consumption, 2),
            "food": round(food_consumption, 2),
            "water": round(water_consumption, 2),
        }

        # === PRODUCTION ===
        production_totals = {"power": 0, "food": 0, "water": 0}

        for room, dwellers in rooms_with_dwellers:
            if room.category != RoomTypeEnum.PRODUCTION or not room.ability or not room.output:
                continue

            # Calculate production based on dweller stats and room tier
            ability_sum = sum(getattr(dweller, room.ability.lower(), 0) for dweller in dwellers)
            tier_mult = TIER_MULTIPLIER.get(room.tier, 1.0)
            production = room.output * ability_sum * BASE_PRODUCTION_RATE * tier_mult * seconds_passed

            # Apply production to appropriate resources
            match room.ability:
                case SPECIALEnum.STRENGTH:  # Power plants
                    production_totals["power"] += production
                case SPECIALEnum.AGILITY:  # Gardens/Diners
                    production_totals["food"] += production
                case SPECIALEnum.PERCEPTION:  # Water treatment
                    production_totals["water"] += production
                case SPECIALEnum.ENDURANCE:  # Special rooms that produce all
                    for resource in production_totals:
                        production_totals[resource] += production / 3
                case _:
                    pass

        # Apply production
        power_delta += production_totals["power"]
        food_delta += production_totals["food"]
        water_delta += production_totals["water"]

        events["production"] = {k: round(v, 2) for k, v in production_totals.items()}

        # === CALCULATE NEW VALUES ===
        new_power = max(0, min(vault.power + power_delta, vault.power_max))
        new_food = max(0, min(vault.food + food_delta, vault.food_max))
        new_water = max(0, min(vault.water + water_delta, vault.water_max))

        # === CHECK FOR WARNINGS ===
        if new_power < vault.power_max * CRITICAL_RESOURCE_THRESHOLD:
            events["warnings"].append({"type": "critical_power", "message": "Power critically low!"})
        elif new_power < vault.power_max * LOW_RESOURCE_THRESHOLD:
            events["warnings"].append({"type": "low_power", "message": "Power running low"})

        if new_food < vault.food_max * CRITICAL_RESOURCE_THRESHOLD:
            events["warnings"].append({"type": "critical_food", "message": "Food critically low!"})
        elif new_food < vault.food_max * LOW_RESOURCE_THRESHOLD:
            events["warnings"].append({"type": "low_food", "message": "Food running low"})

        if new_water < vault.water_max * CRITICAL_RESOURCE_THRESHOLD:
            events["warnings"].append({"type": "critical_water", "message": "Water critically low!"})
        elif new_water < vault.water_max * LOW_RESOURCE_THRESHOLD:
            events["warnings"].append({"type": "low_water", "message": "Water running low"})

        # Log resource changes
        self.logger.debug(
            f"Vault {vault.id}: Power {vault.power:.0f} -> {new_power:.0f}, "  # noqa: G004
            f"Food {vault.food:.0f} -> {new_food:.0f}, "
            f"Water {vault.water:.0f} -> {new_water:.0f}"
        )

        return (
            VaultUpdate(
                power=round(new_power),
                food=round(new_food),
                water=round(new_water),
            ),
            events,
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
            raise ValueError(f"Vault {vault_id} not found")  # noqa: EM102, TRY003

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
