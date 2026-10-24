"""Enhanced resource management system for vault resources."""

import logging
import math
from collections.abc import Mapping, Sequence
from datetime import timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RoomTypeEnum, SPECIALEnum
from app.core.event_bus import GameEvent, event_bus
from app.core.game_config import game_config
from app.crud.resource import resource as resource_crud
from app.models import Dweller, Room, Storage, Vault
from app.models.game_state import GameState
from app.options.identity_modifiers import effective_stat, identity_modifiers_for
from app.schemas.vault import (
    PrimaryResourceAmounts,
    ResourceProduction,
    ResourceTickEvents,
    VaultUpdate,
)
from app.utils.resource_warnings import get_resource_warnings

logger = logging.getLogger(__name__)

# Medical room production mapping (room name lowercase → product type)
MEDICAL_ROOM_PRODUCTION: dict[str, str] = {
    "medbay": "stimpack",
    "science lab": "radaway",
}


def compute_medical_capacity(rooms: Sequence[Room]) -> dict[str, int]:
    """Compute max stimpack/radaway capacity from Medbay/Science Lab rooms."""
    capacities: dict[str, int] = {"stimpack": 0, "radaway": 0}
    for room in rooms:
        product = MEDICAL_ROOM_PRODUCTION.get(room.name.lower())
        if product and room.capacity is not None:
            capacities[product] += room.capacity
    return capacities


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

        resource_update, events = self.calculate_resource_window(
            resource_data.vault,
            resource_data.rooms,
            resource_data.dweller_count,
            resource_data.rooms_with_dwellers,
            seconds_passed,
            state=resource_data.game_state,
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
                applied = self.apply_room_payout(
                    resource_data.vault,
                    storage,
                    capacity,
                    medical_production,
                )
                for resource_type in ("stimpack", "radaway"):
                    if medical_production[resource_type] == 0:
                        previous = getattr(storage, resource_type)
                        capped = min(previous, capacity.get(resource_type, 0))
                        setattr(storage, resource_type, capped)
                        applied[resource_type] = capped - previous
                    setattr(events.production, resource_type, applied[resource_type])
                resource_crud.save_storage(db_session, storage)

        if events.objective_production is not None:
            events.objective_production.stimpack = events.production.stimpack
            events.objective_production.radaway = events.production.radaway
        return resource_update, events

    def calculate_resource_window(
        self,
        vault: Vault,
        rooms: Sequence[Room],
        dweller_count: float,
        rooms_with_dwellers: list[tuple[Room, list[Dweller]]],
        seconds_passed: int,
        *,
        state: GameState | None = None,
    ) -> tuple[VaultUpdate, ResourceTickEvents]:
        """Calculate net resource change considering production, consumption, and efficiency.

        Returns:
            tuple: Updated resource levels and typed tick events.
        """
        # Minute-sized steps use recovered power immediately on the following step.
        # Keep fractions outside the integer wire values, across worker restarts too.
        remainders = dict(state.resource_remainders) if state else {}
        stocks = {key: float(getattr(vault, key)) + remainders.get(key, 0.0) for key in ("power", "food", "water")}
        consumption = dict.fromkeys(stocks, 0.0)
        production = dict.fromkeys((*stocks, "stimpack", "radaway"), 0.0)
        elapsed = 0
        while elapsed < seconds_passed:
            step = min(60, seconds_passed - elapsed)
            used = self._calculate_consumption(rooms, dweller_count, step)
            made = self._calculate_production(rooms_with_dwellers, step, stocks["power"])
            offline = (
                state is not None
                and (state.last_tick_time + timedelta(seconds=elapsed) - state.last_activity_time).total_seconds() > 600
            )
            for key, stock in stocks.items():
                maximum = getattr(vault, f"{key}_max")
                floor = min(stock, math.ceil(maximum * game_config.resource.offline_reserve_fraction)) if offline else 0
                stocks[key] = max(floor, min(maximum, stock + made[key] - used[key]))
                consumption[key] += used[key]
            for key in production:
                production[key] += made[key]
            elapsed += step
        new_resources = stocks
        if state is not None:
            remainders.update({key: value - round(value) for key, value in stocks.items()})
        objective_production = dict(production)
        for key in stocks:
            counted = production[key] + remainders.get(f"produced_{key}", 0.0)
            objective_production[key] = math.floor(counted + 1e-9)
            remainders[f"produced_{key}"] = max(0.0, counted - objective_production[key])
        if state is not None:
            state.resource_remainders = remainders
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
                objective_production=ResourceProduction(**objective_production),
                consumption=PrimaryResourceAmounts(**consumption),
            ),
        )

    def _calculate_consumption(
        self, rooms: Sequence[Room], dweller_count: float, seconds_passed: int
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

    def calculate_room_production(self, room: Room, dwellers: list[Dweller], seconds_passed: int) -> dict[str, float]:
        """Return this room's raw production split across resource keys."""
        totals = dict.fromkeys(("power", "food", "water", "stimpack", "radaway"), 0.0)
        if room.ability is None:
            return totals

        production = self._calculate_room_production(room, dwellers, seconds_passed)
        self._apply_room_production(room.name, room.ability, production, totals)
        return totals

    def apply_room_payout(
        self,
        vault: Vault,
        storage: Storage | None,
        medical_capacity: dict[str, int],
        totals: Mapping[str, float | int],
        *,
        dry_run: bool = False,
    ) -> dict[str, int]:
        """Add a room payout to vault/storage stocks, clamped to capacity.

        Returns the integer amount that actually landed in each resource. With
        ``dry_run`` the amounts are computed against the same capacity rules but
        the mapped stocks are left untouched, so a quote cannot dirty them.
        """
        applied = dict.fromkeys(("power", "food", "water", "stimpack", "radaway"), 0)
        for resource_type in ("power", "food", "water"):
            requested = max(0, round(totals.get(resource_type, 0.0)))
            if requested == 0:
                continue
            previous = getattr(vault, resource_type)
            updated = min(previous + requested, getattr(vault, f"{resource_type}_max"))
            applied[resource_type] = updated - previous
            if not dry_run:
                setattr(vault, resource_type, updated)

        if storage is not None:
            for resource_type in ("stimpack", "radaway"):
                requested = max(0, round(totals.get(resource_type, 0.0)))
                if requested == 0:
                    continue
                previous = getattr(storage, resource_type)
                updated = min(previous + requested, medical_capacity.get(resource_type, 0))
                applied[resource_type] = updated - previous
                if not dry_run:
                    setattr(storage, resource_type, updated)

        return applied

    def _calculate_production(
        self, rooms_with_dwellers: list[tuple[Room, list[Dweller]]], seconds_passed: int, current_power: float
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

            production = self.calculate_room_production(room, dwellers, seconds_passed)
            for resource_type, amount in production.items():
                production_totals[resource_type] += amount

        return production_totals

    def _calculate_room_production(self, room: Room, dwellers: list[Dweller], seconds_passed: int) -> float:
        """Calculate production from the room's workers.

        Youth posted to a production room are junior workers: they assist at the
        ``junior_worker_output_multiplier`` rate while their apprenticeship trains the
        room's SPECIAL, so a room with a child/teen produces more than adults alone.
        """
        ability = room.ability
        if ability is None:
            return 0.0

        output = room.output
        if output is None:
            return 0.0

        junior_mult = game_config.resource.junior_worker_output_multiplier

        def contribution(dweller: Dweller) -> float:
            # Each worker contributes their own stats scaled by their own faction perk: a
            # production bonus is personal, so it must not inflate neutral coworkers.
            base = effective_stat(dweller, ability.lower()) * (1 + identity_modifiers_for(dweller).production_pct)
            return base if dweller.apprentice_stat is None else base * junior_mult

        ability_sum = sum(contribution(dweller) for dweller in dwellers)
        tier_mult = game_config.resource.get_tier_multiplier(room.tier)
        rate = game_config.resource.base_production_rate
        if MEDICAL_ROOM_PRODUCTION.get(room.name.lower()):
            rate = game_config.resource.medical_production_rate
        production = output * ability_sum * rate * tier_mult * seconds_passed

        juniors = sum(1 for dweller in dwellers if dweller.apprentice_stat is not None)
        self.logger.debug(
            f"Room {room.name} producing: output={room.output}, ability_sum={ability_sum}, "
            f"production={production:.2f} (tier={room.tier}, adults={len(dwellers) - juniors}, juniors={juniors})"
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

    def _log_resource_changes(self, vault: Vault, new_resources: dict[str, float]) -> None:
        """Log resource changes for debugging."""
        self.logger.debug(
            f"Vault {vault.id}: Power {vault.power:.0f} -> {new_resources['power']:.0f}, "
            f"Food {vault.food:.0f} -> {new_resources['food']:.0f}, "
            f"Water {vault.water:.0f} -> {new_resources['water']:.0f}"
        )

    @staticmethod
    async def emit_production_events(vault_id: UUID4, events: ResourceTickEvents) -> None:
        """Emit one batched objective event after the resource transaction has committed.

        One event per vault (not per resource) removes one handler session, vault
        lock, and objectives query per additional resource.
        """
        production = events.objective_production or events.production
        resources: dict[str, int] = {}
        for resource_type, amount in production.model_dump().items():
            int_amount = int(amount)
            if int_amount > 0:
                resources[resource_type] = int_amount

        if resources:
            await event_bus.emit(
                GameEvent.RESOURCE_COLLECTED,
                vault_id,
                {"resources": resources, "source": "production"},
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
