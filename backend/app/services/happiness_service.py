"""Service for managing dweller happiness system."""

import logging
from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config.game_balance import (
    BASE_HAPPINESS_DECAY,
    COMBAT_HAPPINESS_PENALTY,
    CRITICAL_RESOURCE_DECAY,
    CRITICAL_RESOURCE_THRESHOLD_HAPPINESS,
    HIGH_HEALTH_BONUS,
    HIGH_HEALTH_THRESHOLD,
    HIGH_VAULT_RESOURCES_BONUS,
    IDLE_HAPPINESS_DECAY,
    INCIDENT_HAPPINESS_PENALTY,
    LIVING_QUARTERS_HAPPINESS_BONUS,
    LOW_RESOURCE_THRESHOLD,
    NO_INCIDENTS_BONUS,
    PARTNER_HAPPINESS_BONUS,
    PARTNER_NEARBY_BONUS,
    RADIO_ROOM_HAPPINESS_BONUS,
    RESOURCE_SHORTAGE_DECAY,
    TRAINING_HAPPINESS_GAIN,
    WORKING_HAPPINESS_GAIN,
)
from app.models.dweller import Dweller
from app.models.incident import Incident
from app.models.room import Room
from app.models.vault import Vault

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class HappinessService:
    """Service for managing dweller happiness."""

    @staticmethod
    async def update_vault_happiness(
        db_session: AsyncSession,
        vault_id: UUID4,
        seconds_passed: int = 60,
    ) -> dict:
        """
        Update happiness for all dwellers in a vault based on conditions.

        Args:
            db_session: Database session
            vault_id: Vault ID
            seconds_passed: Seconds since last update

        Returns:
            Dictionary with update statistics
        """
        # Get vault
        vault = await db_session.get(Vault, vault_id)
        if not vault:
            return {"error": "Vault not found"}

        # Get all dwellers
        dwellers_query = select(Dweller).where(Dweller.vault_id == vault_id)
        dwellers = (await db_session.execute(dwellers_query)).scalars().all()

        if not dwellers:
            return {"dwellers_processed": 0, "happiness_changes": 0}

        # Get active incidents
        incidents_query = select(Incident).where((Incident.vault_id == vault_id) & (Incident.is_active == True))
        active_incidents = (await db_session.execute(incidents_query)).scalars().all()

        # Get radio rooms for happiness bonus calculation
        from app.services.radio_service import RadioService

        radio_rooms = await RadioService.get_radio_rooms(db_session, vault_id)

        # Calculate vault-wide factors
        vault_factors = await HappinessService._calculate_vault_factors(vault, active_incidents, radio_rooms)

        stats = {
            "dwellers_processed": 0,
            "happiness_increased": 0,
            "happiness_decreased": 0,
            "total_change": 0,
            "average_happiness": 0,
        }

        total_happiness_change = 0

        for dweller in dwellers:
            # Calculate happiness change for this dweller
            change = await HappinessService._calculate_happiness_change(
                db_session,
                dweller,
                vault_factors,
                seconds_passed,
            )

            # Apply change
            old_happiness = dweller.happiness
            dweller.happiness = max(10, min(100, dweller.happiness + change))
            actual_change = dweller.happiness - old_happiness

            # Update stats
            stats["dwellers_processed"] += 1
            if actual_change > 0:
                stats["happiness_increased"] += 1
            elif actual_change < 0:
                stats["happiness_decreased"] += 1

            total_happiness_change += actual_change

        # Commit changes
        await db_session.commit()

        # Calculate average happiness
        if dwellers:
            stats["average_happiness"] = sum(d.happiness for d in dwellers) / len(dwellers)
            stats["total_change"] = total_happiness_change

            # Update vault happiness (average of all dwellers)
            vault.happiness = int(stats["average_happiness"])
            await db_session.commit()

        logger.info(
            "Vault %s happiness update: %d dwellers, avg happiness: %.1f, total change: %+.1f",
            vault_id,
            stats["dwellers_processed"],
            stats["average_happiness"],
            stats["total_change"],
        )

        return stats

    @staticmethod
    async def _calculate_vault_factors(vault: Vault, active_incidents: list[Incident], radio_rooms: list[Room]) -> dict:
        """
        Calculate vault-wide factors affecting happiness.

        Args:
            vault: Vault object
            active_incidents: List of active incidents
            radio_rooms: List of radio rooms

        Returns:
            Dictionary of factors
        """
        # Resource status
        power_ratio = vault.power / vault.power_max if vault.power_max > 0 else 0
        food_ratio = vault.food / vault.food_max if vault.food_max > 0 else 0
        water_ratio = vault.water / vault.water_max if vault.water_max > 0 else 0

        has_low_resources = (
            power_ratio < LOW_RESOURCE_THRESHOLD
            or food_ratio < LOW_RESOURCE_THRESHOLD
            or water_ratio < LOW_RESOURCE_THRESHOLD
        )

        has_critical_resources = (
            power_ratio < CRITICAL_RESOURCE_THRESHOLD_HAPPINESS
            or food_ratio < CRITICAL_RESOURCE_THRESHOLD_HAPPINESS
            or water_ratio < CRITICAL_RESOURCE_THRESHOLD_HAPPINESS
        )

        # Calculate radio happiness bonus
        radio_happiness_bonus = 0.0
        if vault.radio_mode == "happiness" and radio_rooms:
            from app.config.game_balance import RADIO_HAPPINESS_BONUS

            # Sum speedup multipliers from all radio rooms
            total_speedup = sum(room.speedup_multiplier for room in radio_rooms)
            radio_happiness_bonus = RADIO_HAPPINESS_BONUS * total_speedup

        return {
            "has_low_resources": has_low_resources,
            "has_critical_resources": has_critical_resources,
            "active_incident_count": len(active_incidents),
            "power_ratio": power_ratio,
            "food_ratio": food_ratio,
            "water_ratio": water_ratio,
            "radio_happiness_bonus": radio_happiness_bonus,
        }

    @staticmethod
    async def _calculate_happiness_change(  # noqa: C901, PLR0912
        db_session: AsyncSession,
        dweller: Dweller,
        vault_factors: dict,
        seconds_passed: int,
    ) -> float:
        """
        Calculate happiness change for a single dweller.

        Args:
            db_session: Database session
            dweller: Dweller object
            vault_factors: Vault-wide factors
            seconds_passed: Seconds since last update

        Returns:
            Happiness change amount
        """
        # Normalize to 60-second ticks
        tick_multiplier = seconds_passed / 60.0

        # Start with base decay
        change = -BASE_HAPPINESS_DECAY * tick_multiplier

        # === NEGATIVE FACTORS ===

        # Resource shortages
        if vault_factors["has_critical_resources"]:
            change -= CRITICAL_RESOURCE_DECAY * tick_multiplier
        elif vault_factors["has_low_resources"]:
            change -= RESOURCE_SHORTAGE_DECAY * tick_multiplier

        # Active incidents
        if vault_factors["active_incident_count"] > 0:
            change -= INCIDENT_HAPPINESS_PENALTY * vault_factors["active_incident_count"] * tick_multiplier

        # Idle dwellers
        if dweller.status == "idle":
            change -= IDLE_HAPPINESS_DECAY * tick_multiplier

        # Low health penalty
        health_ratio = dweller.health / dweller.max_health if dweller.max_health > 0 else 0
        if health_ratio < 0.3:  # Below 30% health
            change -= 2.0 * tick_multiplier
        elif health_ratio < 0.5:  # Below 50% health
            change -= 1.0 * tick_multiplier

        # Radiation penalty
        if dweller.radiation > 50:
            change -= 1.0 * tick_multiplier

        # === POSITIVE FACTORS ===

        # Working dwellers gain happiness
        if dweller.status == "working" and dweller.room_id:
            change += WORKING_HAPPINESS_GAIN * tick_multiplier

            # Bonus for high health while working
            if health_ratio > HIGH_HEALTH_THRESHOLD:
                change += HIGH_HEALTH_BONUS * tick_multiplier

            # Room-specific bonuses
            # Get room to check category/name for specific bonuses
            room = await db_session.get(Room, dweller.room_id)
            if room:
                room_name_lower = (room.name or "").lower()
                # Living quarters bonus (romance, privacy, comfort)
                if "living" in room_name_lower or "quarters" in room_name_lower:
                    change += LIVING_QUARTERS_HAPPINESS_BONUS * tick_multiplier
                # Radio room bonus (entertainment, music)
                elif "radio" in room_name_lower:
                    change += RADIO_ROOM_HAPPINESS_BONUS * tick_multiplier

        # Training gives happiness (learning, self-improvement, purpose)
        if dweller.status == "training":
            change += TRAINING_HAPPINESS_GAIN * tick_multiplier

        # Combat reduces happiness (stress, fear, danger)
        if dweller.status == "combat":
            change -= COMBAT_HAPPINESS_PENALTY * tick_multiplier

        # Partner bonus
        if dweller.partner_id:
            # Check if partner exists and is alive
            partner = await db_session.get(Dweller, dweller.partner_id)
            if partner:
                # Base partner bonus
                change += PARTNER_HAPPINESS_BONUS * tick_multiplier / 60.0  # Normalize bonus

                # Extra bonus if in same room
                if dweller.room_id and dweller.room_id == partner.room_id:
                    change += PARTNER_NEARBY_BONUS * tick_multiplier

        # High vault resources bonus
        if (
            vault_factors["power_ratio"] > 0.8
            and vault_factors["food_ratio"] > 0.8
            and vault_factors["water_ratio"] > 0.8
        ):
            change += HIGH_VAULT_RESOURCES_BONUS * tick_multiplier

        # No incidents bonus
        if vault_factors["active_incident_count"] == 0:
            change += NO_INCIDENTS_BONUS * tick_multiplier

        # Radio happiness bonus (when in happiness mode)
        if vault_factors["radio_happiness_bonus"] > 0:
            change += vault_factors["radio_happiness_bonus"] * tick_multiplier

        return round(change, 2)

    @staticmethod
    async def get_happiness_modifiers(  # noqa: C901, PLR0912
        db_session: AsyncSession,
        dweller_id: UUID4,
    ) -> dict:
        """
        Get detailed breakdown of happiness modifiers for a dweller.

        Args:
            db_session: Database session
            dweller_id: Dweller ID

        Returns:
            Dictionary with modifier breakdown
        """
        dweller = await db_session.get(Dweller, dweller_id)
        if not dweller:
            return {"error": "Dweller not found"}

        # Get vault
        vault = await db_session.get(Vault, dweller.vault_id)
        if not vault:
            return {"error": "Vault not found"}

        # Get active incidents
        incidents_query = select(Incident).where((Incident.vault_id == dweller.vault_id) & (Incident.is_active == True))
        active_incidents = (await db_session.execute(incidents_query)).scalars().all()

        # Get radio rooms
        from app.services.radio_service import RadioService

        radio_rooms = await RadioService.get_radio_rooms(db_session, dweller.vault_id)

        vault_factors = await HappinessService._calculate_vault_factors(vault, active_incidents, radio_rooms)

        modifiers = {
            "current_happiness": dweller.happiness,
            "positive": [],
            "negative": [],
        }

        # Analyze factors
        if dweller.status == "working":
            modifiers["positive"].append({"name": "Working", "value": WORKING_HAPPINESS_GAIN})

        if dweller.status == "training":
            modifiers["positive"].append({"name": "Training", "value": TRAINING_HAPPINESS_GAIN})

        if dweller.status == "combat":
            modifiers["negative"].append({"name": "Combat", "value": -COMBAT_HAPPINESS_PENALTY})

        if dweller.partner_id:
            modifiers["positive"].append({"name": "Has Partner", "value": PARTNER_HAPPINESS_BONUS / 60.0})

        health_ratio = dweller.health / dweller.max_health if dweller.max_health > 0 else 0
        if health_ratio > HIGH_HEALTH_THRESHOLD:
            modifiers["positive"].append({"name": "High Health", "value": HIGH_HEALTH_BONUS})
        elif health_ratio < 0.5:
            modifiers["negative"].append({"name": "Low Health", "value": -1.0 if health_ratio > 0.3 else -2.0})

        if vault_factors["has_critical_resources"]:
            modifiers["negative"].append({"name": "Critical Resources", "value": -CRITICAL_RESOURCE_DECAY})
        elif vault_factors["has_low_resources"]:
            modifiers["negative"].append({"name": "Low Resources", "value": -RESOURCE_SHORTAGE_DECAY})

        if vault_factors["active_incident_count"] > 0:
            modifiers["negative"].append(
                {
                    "name": f"Active Incidents ({vault_factors['active_incident_count']})",
                    "value": -INCIDENT_HAPPINESS_PENALTY * vault_factors["active_incident_count"],
                }
            )

        if dweller.status == "idle":
            modifiers["negative"].append({"name": "Idle", "value": -IDLE_HAPPINESS_DECAY})

        if dweller.radiation > 50:
            modifiers["negative"].append({"name": "Radiation", "value": -1.0})

        modifiers["negative"].append({"name": "Base Decay", "value": -BASE_HAPPINESS_DECAY})

        # Radio happiness bonus
        if vault_factors["radio_happiness_bonus"] > 0:
            modifiers["positive"].append(
                {
                    "name": "Radio (Happiness Mode)",
                    "value": vault_factors["radio_happiness_bonus"],
                }
            )

        return modifiers


happiness_service = HappinessService()
