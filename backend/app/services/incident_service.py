"""Incident service for managing combat events and vault disasters."""

import logging
import random

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import game_balance
from app.crud.incident import incident_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.incident import Incident, IncidentStatus, IncidentType
from app.models.room import Room

logger = logging.getLogger(__name__)


class IncidentService:
    """Service for managing vault incidents and combat."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def should_spawn_incident(self, db_session: AsyncSession, vault_id: UUID4, seconds_passed: int) -> bool:
        """
        Determine if an incident should spawn based on vault state and time.

        Args:
            db_session: Database session
            vault_id: The vault ID to check
            seconds_passed: Seconds since last tick

        Returns:
            bool: True if incident should spawn
        """
        # Need minimum population
        from app.models.dweller import Dweller

        dwellers_query = select(Dweller).where(Dweller.vault_id == vault_id)
        dwellers_result = await db_session.execute(dwellers_query)
        dweller_count = len(dwellers_result.scalars().all())

        if dweller_count < game_balance.MIN_VAULT_POPULATION_FOR_INCIDENTS:
            return False

        # Calculate spawn chance based on time passed
        hours_passed = seconds_passed / 3600
        spawn_chance = game_balance.INCIDENT_SPAWN_CHANCE_PER_HOUR * hours_passed

        # Random roll
        return random.random() < spawn_chance

    async def spawn_incident(
        self, db_session: AsyncSession, vault_id: UUID4, incident_type: IncidentType | None = None
    ) -> Incident | None:
        """
        Spawn a new incident in a random occupied room.
        Raiders and Deathclaws spawn at vault door (0,0) and spread inward.

        Args:
            db_session: Database session
            vault_id: ID of the vault
            incident_type: Type of incident (random if None)

        Returns:
            Incident or None if no suitable room found
        """
        # Pick random incident type if not specified
        if not incident_type:
            incident_type = random.choice(
                [IncidentType.RAIDER_ATTACK, IncidentType.RADROACH_INFESTATION, IncidentType.FIRE]
            )

        # Determine where to spawn based on incident type
        if incident_type.value in game_balance.VAULT_DOOR_INCIDENTS:
            # External attacks spawn at vault door (0,0) and spread inward
            vault_door_query = select(Room).where(
                (Room.vault_id == vault_id) & (Room.coordinate_x == 0) & (Room.coordinate_y == 0)
            )
            vault_door_result = await db_session.execute(vault_door_query)
            target_room = vault_door_result.scalar_one_or_none()

            if not target_room:
                self.logger.warning(f"No vault door found at (0,0) for {incident_type} in vault {vault_id}")
                return None
        else:
            # Other incidents spawn in random occupied rooms
            rooms_query = (
                select(Room)
                .join(Dweller, Room.id == Dweller.room_id)
                .where((Room.vault_id == vault_id) & (Dweller.room_id.is_not(None)))
                .distinct()
            )
            rooms_result = await db_session.execute(rooms_query)
            occupied_rooms = list(rooms_result.scalars().all())

            if not occupied_rooms:
                self.logger.warning(f"No occupied rooms found for incident spawn in vault {vault_id}")
                return None

            # Pick random room
            target_room = random.choice(occupied_rooms)

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
            duration=game_balance.INCIDENT_SPREAD_DURATION,
        )

        self.logger.info(
            f"Spawned {incident_type} (difficulty {difficulty}) in room {target_room.name} of vault {vault_id}"
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

        # Get dwellers in affected room with equipment preloaded (N+1 optimization)
        from sqlalchemy.orm import selectinload

        dwellers_query = (
            select(Dweller)
            .options(
                selectinload(Dweller.weapon),
                selectinload(Dweller.outfit),
            )
            .where((Dweller.room_id == incident.room_id) & (Dweller.health > 0))  # Only alive dwellers
        )
        dwellers_result = await db_session.execute(dwellers_query)
        dwellers = list(dwellers_result.scalars().all())

        if not dwellers:
            # No dwellers to fight - incident spreads
            if (
                incident.elapsed_time() >= incident.duration
                and incident.spread_count < game_balance.INCIDENT_MAX_SPREAD_COUNT
            ):
                await self._spread_incident(db_session, incident)
            return {"no_defenders": True, "damage": 0}

        # Calculate combat power
        dweller_power = self._calculate_dweller_combat_power(dwellers)
        raider_power = self._calculate_raider_power(incident.difficulty)

        # Apply damage over time
        damage_to_dwellers = self._calculate_damage_to_dwellers(raider_power, seconds_passed)
        damage_to_raiders = self._calculate_damage_to_raiders(dweller_power, seconds_passed)

        # Apply damage to dwellers
        damaged_count = 0
        for dweller in dwellers:
            damage_per_dweller = damage_to_dwellers / len(dwellers)
            new_health = max(0, dweller.health - int(damage_per_dweller))

            if new_health != dweller.health:
                # Direct update - SQLAlchemy session tracks the object, no need to refresh
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
        caps_earned = 0

        if incident.enemies_defeated >= expected_raider_count:
            # Victory! Generate loot and resolve
            incident.loot = self._generate_loot(incident.difficulty)
            incident.resolve(success=True)

            # Track caps for batch vault update (done at game loop level)
            caps_earned = incident.loot.get("caps", 0)

            # Award XP to participating dwellers
            await self._award_combat_xp(db_session, incident, dwellers)

            self.logger.info(f"Incident {incident.id} resolved successfully! Loot: {incident.loot}")

        db_session.add(incident)
        await db_session.commit()

        return {
            "damage_to_dwellers": damage_to_dwellers,
            "damage_to_raiders": damage_to_raiders,
            "dwellers_damaged": damaged_count,
            "enemies_defeated": enemies_this_tick,
            "caps_earned": caps_earned,  # Return for batch update
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

            # Award XP to dwellers in the room
            if incident.room_id:
                from sqlalchemy.orm import selectinload
                from sqlmodel import select

                from app.models.room import Room

                # Load room with dwellers relationship
                query = select(Room).where(Room.id == incident.room_id).options(selectinload(Room.dwellers))
                result = await db_session.execute(query)
                room = result.scalar_one_or_none()

                if room and room.dwellers:
                    await self._award_combat_xp(db_session, incident, room.dwellers)

        incident.loot = loot
        incident.resolve(success=success)
        db_session.add(incident)
        await db_session.commit()

        self.logger.info(
            f"Incident {incident_id} manually resolved ({'success' if success else 'failure'}). Loot: {loot}"
        )

        return {
            "message": "Incident resolved successfully" if success else "Incident failed",
            "incident_id": str(incident_id),
            "loot": loot,
            "caps_earned": caps_earned,
            "items_earned": loot.get("items", []),
        }

    async def _spread_incident(self, db_session: AsyncSession, incident: Incident) -> None:
        """Spread incident to an adjacent room with the same incident type."""
        # Get the current room to find its coordinates
        current_room_query = select(Room).where(Room.id == incident.room_id)
        current_room_result = await db_session.execute(current_room_query)
        current_room = current_room_result.scalar_one_or_none()

        if not current_room or current_room.coordinate_x is None or current_room.coordinate_y is None:
            return

        # Find adjacent rooms (within 1-2 coordinate units horizontally or vertically)
        adjacent_rooms_query = select(Room).where(
            (Room.vault_id == incident.vault_id)
            & (Room.id != incident.room_id)
            & (Room.coordinate_x.is_not(None))
            & (Room.coordinate_y.is_not(None))
            & (
                # Adjacent horizontally (same floor, next to each other)
                (
                    (Room.coordinate_y == current_room.coordinate_y)
                    & (Room.coordinate_x.between(current_room.coordinate_x - 2, current_room.coordinate_x + 2))
                )
                # Adjacent vertically (same column, one floor up/down)
                | (
                    (Room.coordinate_x == current_room.coordinate_x)
                    & (Room.coordinate_y.between(current_room.coordinate_y - 1, current_room.coordinate_y + 1))
                )
            )
        )
        adjacent_rooms_result = await db_session.execute(adjacent_rooms_query)
        adjacent_rooms = list(adjacent_rooms_result.scalars().all())

        if adjacent_rooms:
            # Pick a random adjacent room
            new_room = random.choice(adjacent_rooms)

            # Create a new incident in the adjacent room with the SAME type
            new_incident = await incident_crud.create(
                db_session,
                vault_id=incident.vault_id,
                room_id=new_room.id,
                incident_type=incident.type,  # Same type! (field is called 'type')
                difficulty=incident.difficulty + 1,  # Slightly harder
                duration=game_balance.INCIDENT_SPREAD_DURATION,
            )

            # Update original incident spread tracking
            incident.spread_to_room(str(new_room.id))
            db_session.add(incident)

            self.logger.warning(
                f"Incident {incident.type} spread from {current_room.name} to {new_room.name} "
                f"(difficulty {new_incident.difficulty})"
            )

    def _calculate_dweller_combat_power(self, dwellers: list[Dweller]) -> float:
        """Calculate total combat power of dwellers."""
        total_power = 0.0
        for dweller in dwellers:
            # SPECIAL contribution
            stat_power = (
                dweller.strength * game_balance.DWELLER_STRENGTH_WEIGHT
                + dweller.endurance * game_balance.DWELLER_ENDURANCE_WEIGHT
                + dweller.agility * game_balance.DWELLER_AGILITY_WEIGHT
            )

            # Weapon damage (if equipped)
            weapon_damage = 0
            if dweller.weapon:
                weapon_damage = (dweller.weapon.damage_min + dweller.weapon.damage_max) / 2

            # Level bonus
            level_bonus = dweller.level * game_balance.LEVEL_BONUS_MULTIPLIER

            total_power += stat_power + weapon_damage + level_bonus

        return total_power

    def _calculate_raider_power(self, difficulty: int) -> float:
        """Calculate raider power based on difficulty."""
        return difficulty * game_balance.BASE_RAIDER_POWER

    def _calculate_damage_to_dwellers(self, raider_power: float, seconds: int) -> float:
        """Calculate damage dealt to dwellers per tick."""
        # Damage reduced by number of dwellers (distributed)
        damage_per_second = raider_power / 10  # Raiders deal 10% of their power per second
        return damage_per_second * seconds

    def _calculate_damage_to_raiders(self, dweller_power: float, seconds: int) -> float:
        """Calculate damage dealt to raiders per tick."""
        damage_per_second = dweller_power / 5  # Dwellers deal 20% of their power per second
        return damage_per_second * seconds

    async def _award_combat_xp(self, db_session: AsyncSession, incident: "Incident", dwellers: list["Dweller"]) -> None:
        """
        Award experience to dwellers who participated in combat.

        Args:
            db_session: Database session
            incident: Resolved incident
            dwellers: List of dwellers who fought
        """
        from app.config.game_balance import COMBAT_PERFECT_BONUS_MULTIPLIER, COMBAT_XP_PER_DIFFICULTY
        from app.services.leveling_service import leveling_service

        if not dwellers:
            return

        # Base XP from difficulty
        base_xp = incident.difficulty * COMBAT_XP_PER_DIFFICULTY

        # Check for perfect combat (no damage taken)
        perfect_combat = incident.damage_dealt == 0

        if perfect_combat:
            base_xp = int(base_xp * COMBAT_PERFECT_BONUS_MULTIPLIER)

        # Distribute XP among participants
        xp_per_dweller = base_xp // len(dwellers)

        for dweller in dwellers:
            dweller.experience += xp_per_dweller
            db_session.add(dweller)

            # Check for level-up
            await leveling_service.check_level_up(db_session, dweller)

    def _generate_loot(self, difficulty: int) -> dict:
        """Generate loot rewards based on difficulty."""
        caps = random.randint(
            game_balance.LOOT_CAPS_MIN + (difficulty - 1) * game_balance.LOOT_CAPS_MAX_PER_DIFFICULTY // 2,
            game_balance.LOOT_CAPS_MIN + difficulty * game_balance.LOOT_CAPS_MAX_PER_DIFFICULTY,
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
