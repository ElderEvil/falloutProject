"""Leveling service for handling dweller experience and level-ups."""

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.schemas.dweller import DwellerUpdate

logger = logging.getLogger(__name__)


class LevelingService:
    """Service for handling dweller leveling and experience progression."""

    @staticmethod
    def calculate_xp_required(level: int) -> int:
        """
        Calculate total XP required to reach a specific level.

        Uses exponential curve: BASE_XP * (level ^ EXPONENT)

        Examples:
            Level 1: 0 XP (starting level)
            Level 2: 100 XP
            Level 3: 283 XP
            Level 10: 3,162 XP
            Level 50: 353,553 XP

        Args:
            level: Target level (1-50)

        Returns:
            Total XP required to reach that level
        """
        if level <= 1:
            return 0
        return int(game_config.leveling.base_xp_requirement * (level**game_config.leveling.xp_curve_exponent))

    @staticmethod
    def calculate_xp_for_level_range(current_level: int, target_level: int) -> int:
        """
        Calculate XP needed to go from current_level to target_level.

        Args:
            current_level: Starting level
            target_level: Ending level

        Returns:
            XP difference between the two levels
        """
        if target_level <= current_level:
            return 0
        return LevelingService.calculate_xp_required(target_level) - LevelingService.calculate_xp_required(
            current_level
        )

    async def check_level_up(self, db_session: AsyncSession, dweller: Dweller) -> tuple[bool, int]:
        """
        Check if dweller has enough XP to level up.

        Args:
            db_session: Database session
            dweller: Dweller to check

        Returns:
            Tuple of (leveled_up: bool, levels_gained: int)
        """
        if dweller.level >= game_config.leveling.max_level:
            logger.debug(f"Dweller {dweller.id} already at max level {dweller.level}")
            return False, 0

        levels_gained = 0
        current_level = dweller.level

        # Check for multiple level-ups
        while current_level < game_config.leveling.max_level:
            next_level_xp = self.calculate_xp_required(current_level + 1)
            if dweller.experience >= next_level_xp:
                levels_gained += 1
                current_level += 1
            else:
                break

        if levels_gained > 0:
            logger.info(
                f"Dweller {dweller.id} eligible for {levels_gained} level-up(s) "
                f"(current: {dweller.level}, target: {current_level})"
            )
            await self.level_up_dweller(db_session, dweller, levels_gained)
            return True, levels_gained

        return False, 0

    async def level_up_dweller(self, db_session: AsyncSession, dweller: Dweller, levels: int = 1) -> Dweller:
        """
        Level up a dweller.

        Increases:
        - Level
        - Max health (hp_gain_per_level per level)
        - Current health (to match new max if below)

        Args:
            db_session: Database session
            dweller: Dweller to level up
            levels: Number of levels to gain (default 1)

        Returns:
            Updated dweller
        """
        if dweller.level >= game_config.leveling.max_level:
            logger.debug(f"Dweller {dweller.id} already at max level, skipping level-up")
            return dweller

        # Calculate new level (cap at max_level)
        new_level = min(dweller.level + levels, game_config.leveling.max_level)
        actual_levels = new_level - dweller.level

        # Calculate health increase
        health_increase = actual_levels * game_config.leveling.hp_gain_per_level
        new_max_health = dweller.max_health + health_increase

        # Always fully heal on level-up (rewarding mechanic)
        new_health = new_max_health

        # Update dweller
        from app.crud.dweller import dweller as dweller_crud

        logger.info(
            f"Leveling up dweller {dweller.id}: {dweller.level} → {new_level}, "
            f"health: {dweller.max_health} → {new_max_health}"
        )

        await dweller_crud.update(
            db_session,
            dweller.id,
            DwellerUpdate(level=new_level, max_health=new_max_health, health=new_health),
        )

        # Refresh to get updated values
        await db_session.refresh(dweller)

        return dweller


# Singleton instance
leveling_service = LevelingService()
