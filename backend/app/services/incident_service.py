"""Incident service for managing combat events and vault disasters."""

import logging
import random

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.incident import incident_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.room import Room
from app.models.vault import Vault

logger = logging.getLogger(__name__)

# Spawn configuration
INCIDENT_SPAWN_CHANCE_PER_HOUR = 0.05  # 5% chance per hour
MIN_VAULT_POPULATION_FOR_INCIDENTS = 5  # Need at least 5 dwellers

# Combat configuration
BASE_RAIDER_POWER = 10  # Power per difficulty level
DWELLER_STRENGTH_WEIGHT = 0.4
DWELLER_ENDURANCE_WEIGHT = 0.3
DWELLER_AGILITY_WEIGHT = 0.3
LEVEL_BONUS_MULTIPLIER = 2

# Spread configuration
SPREAD_INTERVAL_SECONDS = 60
MAX_SPREAD_COUNT = 3

# Loot configuration
LOOT_CAPS_MIN = 50
LOOT_CAPS_MAX_PER_DIFFICULTY = 100


class IncidentService:
    """Service for managing vault incidents and combat."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def should_spawn_incident(self, vault: Vault, seconds_passed: int) -> bool:
        """
        Determine if an incident should spawn based on vault state and time.

        Args:
            vault: The vault to check
            seconds_passed: Seconds since last tick

        Returns:
            bool: True if incident should spawn
        """
        # Need minimum population
        if vault.dweller_count < MIN_VAULT_POPULATION_FOR_INCIDENTS:
            return False

        # Calculate spawn chance based on time passed
        hours_passed = seconds_passed / 3600
        spawn_chance = INCIDENT_SPAWN_CHANCE_PER_HOUR * hours_passed

        # Random roll
        return random.random() < spawn_chance

    async def spawn_incident(
        self, db_session: AsyncSession, vault_id: UUID4, incident_type: IncidentType | None = None
    ) -> Incident | None:
        """
        Spawn a new incident in a random occupied room.

        Args:
            db_session: Database session
            vault_id: ID of the vault
            incident_type: Type of incident (random if None)

        Returns:
            Incident or None if no suitable room found
        """
        # Get all rooms with dwellers
        rooms_query = (
            select(Room)
            .join(Dweller, Room.id == Dweller.room_id)
            .where((Room.vault_id == vault_id) & (Dweller.room_id.is_not(None)))
            .distinct()
        )
        rooms_result = await db_session.execute(rooms_query)
        occupied_rooms = list(rooms_result.scalars().all())

        if not occupied_rooms:
            self.logger.warning(f"No occupied rooms found for incident spawn in vault {vault_id}")  # noqa: G004
            return None

        # Pick random room
        target_room = random.choice(occupied_rooms)

        # Pick random incident type if not specified
        if not incident_type:
            incident_type = random.choice(
                [IncidentType.RAIDER_ATTACK, IncidentType.RADROACH_INFESTATION, IncidentType.FIRE]
            )

        # Determine difficulty (1-10, weighted toward medium)
        difficulty = random.choices(
            range(1, 11),
            weights=[5, 10, 15, 20, 20, 15, 10, 3, 1, 1],
            k=1,  # Weighted toward 4-5
        )[0]

        # Create incident
        incident = await incident_crud.create(
            db_session,
            vault_id=vault_id,
            room_id=target_room.id,
            incident_type=incident_type,
            difficulty=difficulty,
            duration=SPREAD_INTERVAL_SECONDS,
        )

        self.logger.info(
            f"Spawned {incident_type} (difficulty {difficulty}) in room {target_room.name} of vault {vault_id}"  # noqa: G004
        )

        return incident

    async def process_incident(
        self, db_session: AsyncSession, incident: Incident, seconds_passed: int
    ) -> dict[str, int | float]:
        """
        Process an active incident (apply damage, check victory conditions).

        Args:
            db_session: Database session
            incident: The incident to process
            seconds_passed: Time since last tick

        Returns:
            dict with combat results
        """
        if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
            return {"skipped": True}

        # Get dwellers in affected room
        dwellers_query = select(Dweller).where(
            (Dweller.room_id == incident.room_id) & (Dweller.health > 0)  # Only alive dwellers
        )
        dwellers_result = await db_session.execute(dwellers_query)
        dwellers = list(dwellers_result.scalars().all())

        if not dwellers:
            # No dwellers to fight - incident spreads
            if incident.elapsed_time() >= incident.duration and incident.spread_count < MAX_SPREAD_COUNT:
                await self._spread_incident(db_session, incident)
            return {"no_defenders": True, "damage": 0}

        # Calculate combat power
        dweller_power = self._calculate_dweller_combat_power(dwellers)
        raider_power = self._calculate_raider_power(incident.difficulty)

        # Apply damage over time
        damage_to_dwellers = self._calculate_damage_to_dwellers(raider_power, len(dwellers), seconds_passed)
        damage_to_raiders = self._calculate_damage_to_raiders(dweller_power, seconds_passed)

        # Apply damage to dwellers
        damaged_count = 0
        for dweller in dwellers:
            damage_per_dweller = damage_to_dwellers / len(dwellers)
            new_health = max(0, dweller.health - int(damage_per_dweller))

            if new_health != dweller.health:
                await db_session.execute(select(Dweller).where(Dweller.id == dweller.id))  # Refresh to avoid stale data
                dweller.health = new_health
                db_session.add(dweller)
                damaged_count += 1

        # Track total damage dealt by raiders
        incident.damage_dealt += int(damage_to_dwellers)

        # Track enemies defeated (simulated)
        enemies_this_tick = int(damage_to_raiders / raider_power) if raider_power > 0 else 0
        incident.enemies_defeated += enemies_this_tick

        # Check victory condition (defeated enough raiders based on difficulty)
        expected_raider_count = incident.difficulty * 2  # Each difficulty = 2 raiders
        if incident.enemies_defeated >= expected_raider_count:
            # Victory! Generate loot and resolve
            incident.loot = self._generate_loot(incident.difficulty)
            incident.resolve(success=True)

            # Award caps to vault
            caps_earned = incident.loot.get("caps", 0)
            await vault_crud.update(
                db_session,
                incident.vault_id,
                {"bottle_caps": (await vault_crud.get(db_session, incident.vault_id)).bottle_caps + caps_earned},
            )

            self.logger.info(
                f"Incident {incident.id} resolved successfully! Loot: {incident.loot}"  # noqa: G004
            )

        db_session.add(incident)
        await db_session.commit()

        return {
            "damage_to_dwellers": damage_to_dwellers,
            "damage_to_raiders": damage_to_raiders,
            "dwellers_damaged": damaged_count,
            "enemies_defeated": enemies_this_tick,
        }

    async def resolve_incident_manually(
        self,
        db_session: AsyncSession,
        incident_id: UUID4,
        success: bool = True,  # noqa: FBT001, FBT002
    ) -> dict:
        """
        Manually resolve an incident (player intervention).

        Args:
            db_session: Database session
            incident_id: ID of incident to resolve
            success: Whether resolution was successful

        Returns:
            dict with loot and resolution info
        """
        incident = await incident_crud.get(db_session, incident_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found")  # noqa: EM102, TRY003

        if incident.status not in [IncidentStatus.ACTIVE, IncidentStatus.SPREADING]:
            raise ValueError(f"Incident {incident_id} is not active")  # noqa: EM102, TRY003

        # Generate loot if successful
        loot = {}
        caps_earned = 0
        if success:
            loot = self._generate_loot(incident.difficulty)
            caps_earned = loot.get("caps", 0)

            # Award caps to vault
            vault = await vault_crud.get(db_session, incident.vault_id)
            await vault_crud.update(db_session, incident.vault_id, {"bottle_caps": vault.bottle_caps + caps_earned})

        incident.loot = loot
        incident.resolve(success=success)
        db_session.add(incident)
        await db_session.commit()

        self.logger.info(
            f"Incident {incident_id} manually resolved ({'success' if success else 'failure'}). Loot: {loot}"  # noqa: G004
        )

        return {
            "message": "Incident resolved successfully" if success else "Incident failed",
            "incident_id": str(incident_id),
            "loot": loot,
            "caps_earned": caps_earned,
            "items_earned": loot.get("items", []),
        }

    async def _spread_incident(self, db_session: AsyncSession, incident: Incident) -> None:
        """Spread incident to an adjacent room."""
        # Get adjacent rooms (simplified: just pick another random occupied room)
        rooms_query = (
            select(Room)
            .join(Dweller, Room.id == Dweller.room_id)
            .where((Room.vault_id == incident.vault_id) & (Room.id != incident.room_id))
            .distinct()
        )
        rooms_result = await db_session.execute(rooms_query)
        adjacent_rooms = list(rooms_result.scalars().all())

        if adjacent_rooms:
            new_room = random.choice(adjacent_rooms)
            incident.spread_to_room(str(new_room.id))
            incident.difficulty += 1  # Increase difficulty when spreading
            self.logger.warning(
                f"Incident {incident.id} spread to room {new_room.name} (new difficulty: {incident.difficulty})"  # noqa: G004
            )

    def _calculate_dweller_combat_power(self, dwellers: list[Dweller]) -> float:
        """Calculate total combat power of dwellers."""
        total_power = 0.0
        for dweller in dwellers:
            # SPECIAL contribution
            stat_power = (
                dweller.strength * DWELLER_STRENGTH_WEIGHT
                + dweller.endurance * DWELLER_ENDURANCE_WEIGHT
                + dweller.agility * DWELLER_AGILITY_WEIGHT
            )

            # Weapon damage (if equipped)
            weapon_damage = 0
            if dweller.weapon:
                weapon_damage = (dweller.weapon.damage_min + dweller.weapon.damage_max) / 2

            # Level bonus
            level_bonus = dweller.level * LEVEL_BONUS_MULTIPLIER

            total_power += stat_power + weapon_damage + level_bonus

        return total_power

    def _calculate_raider_power(self, difficulty: int) -> float:
        """Calculate raider power based on difficulty."""
        return difficulty * BASE_RAIDER_POWER

    def _calculate_damage_to_dwellers(self, raider_power: float, dweller_count: int, seconds: int) -> float:  # noqa: ARG002
        """Calculate damage dealt to dwellers per tick."""
        # Damage reduced by number of dwellers (distributed)
        damage_per_second = raider_power / 10  # Raiders deal 10% of their power per second
        return damage_per_second * seconds

    def _calculate_damage_to_raiders(self, dweller_power: float, seconds: int) -> float:
        """Calculate damage dealt to raiders per tick."""
        damage_per_second = dweller_power / 5  # Dwellers deal 20% of their power per second
        return damage_per_second * seconds

    def _generate_loot(self, difficulty: int) -> dict:
        """Generate loot rewards based on difficulty."""
        caps = random.randint(
            LOOT_CAPS_MIN + (difficulty - 1) * LOOT_CAPS_MAX_PER_DIFFICULTY // 2,
            LOOT_CAPS_MIN + difficulty * LOOT_CAPS_MAX_PER_DIFFICULTY,
        )

        items = []
        # Higher difficulty = better loot
        if difficulty >= 7:
            items.append({"type": "weapon", "rarity": "rare", "name": "Heavy Raider Rifle"})
        elif difficulty >= 4:
            items.append({"type": "weapon", "rarity": "uncommon", "name": "Raider Pistol"})
        else:
            items.append({"type": "junk", "name": "Scrap Metal", "quantity": random.randint(1, 3)})

        return {"caps": caps, "items": items}


# Global instance
incident_service = IncidentService()
