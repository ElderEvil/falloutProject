"""Death service for handling dweller death, revival, and life/death statistics."""

import logging
from datetime import UTC, datetime, timedelta

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.dweller import dweller as dweller_crud
from app.crud.user_profile import profile_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.schemas.common import DeathCauseEnum, DwellerStatusEnum
from app.schemas.dweller import DwellerUpdate
from app.utils.exceptions import ContentNoChangeException, InsufficientResourcesException, ResourceNotFoundException

logger = logging.getLogger(__name__)


class DeathService:
    """Service for handling dweller death and revival mechanics."""

    async def mark_as_dead(
        self,
        db_session: AsyncSession,
        dweller: Dweller,
        cause: DeathCauseEnum,
        epitaph: str | None = None,
    ) -> Dweller:
        """
        Mark a dweller as dead.

        :param db_session: Database session
        :param dweller: Dweller to mark as dead
        :param cause: Cause of death
        :param epitaph: Optional memorial message
        :returns: Updated dweller
        :raises ContentNoChangeException: If dweller is already dead
        """
        if dweller.is_dead:
            raise ContentNoChangeException(detail="Dweller is already dead")

        # Generate default epitaph if not provided
        if not epitaph:
            epitaph = self._generate_epitaph(dweller, cause)

        # Update dweller death state
        updated_dweller = await dweller_crud.update(
            db_session,
            dweller.id,
            DwellerUpdate(
                is_dead=True,
                death_timestamp=datetime.now(UTC),
                death_cause=cause,
                epitaph=epitaph,
                status=DwellerStatusEnum.DEAD,
                health=0,
                room_id=None,  # Remove from room
            ),
        )

        # Increment death statistics
        await self._increment_death_stats(db_session, dweller.vault_id, cause)

        logger.info(
            "Dweller %s (%s %s) died from %s",
            dweller.id,
            dweller.first_name,
            dweller.last_name or "",
            cause.value,
        )

        return updated_dweller

    async def revive_dweller(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        user_id: UUID4,
    ) -> Dweller:
        """
        Revive a dead dweller by paying the revival cost.

        :param db_session: Database session
        :param dweller_id: ID of the dweller to revive
        :param user_id: ID of the user attempting revival
        :returns: Revived dweller
        :raises ResourceNotFoundException: If dweller not found
        :raises ContentNoChangeException: If dweller is not dead or permanently dead
        :raises InsufficientResourcesException: If not enough caps
        """
        dweller = await dweller_crud.get(db_session, dweller_id)

        if not dweller.is_dead:
            raise ContentNoChangeException(detail="Dweller is not dead")

        if dweller.is_permanently_dead:
            raise ContentNoChangeException(detail="Dweller is permanently dead and cannot be revived")

        # Get vault and check caps
        vault = await vault_crud.get(db_session, dweller.vault_id)
        if vault.user_id != user_id:
            raise ResourceNotFoundException(Dweller, identifier=dweller_id)

        revival_cost = self.get_revival_cost(dweller.level)
        if vault.bottle_caps < revival_cost:
            raise InsufficientResourcesException(
                resource_name="caps",
                resource_amount=revival_cost - vault.bottle_caps,
            )

        # Deduct caps
        from app.crud.vault import vault as vault_crud_instance

        await vault_crud_instance.update(
            db_session,
            vault.id,
            {"bottle_caps": vault.bottle_caps - revival_cost},
        )

        # Calculate health after revival
        revival_health = int(dweller.max_health * game_config.death.revival_health_percent)

        # Revive dweller
        revived_dweller = await dweller_crud.update(
            db_session,
            dweller.id,
            DwellerUpdate(
                is_dead=False,
                death_timestamp=None,
                death_cause=None,
                is_permanently_dead=False,
                status=DwellerStatusEnum.IDLE,
                health=revival_health,
            ),
        )

        logger.info(
            "Dweller %s (%s %s) revived for %d caps",
            dweller.id,
            dweller.first_name,
            dweller.last_name or "",
            revival_cost,
        )

        return revived_dweller

    def get_revival_cost(self, level: int) -> int:
        """
        Calculate the revival cost for a dweller based on their level.

        Tiered pricing:
        - Levels 1-5: level x 50 (50-250 caps)
        - Levels 6-10: level x 75 (450-750 caps)
        - Levels 11+: level x 100 (1100-2000 caps, capped)

        :param level: Dweller level
        :returns: Revival cost in caps
        """
        return game_config.death.calculate_revival_cost(level)

    def get_days_until_permanent(self, dweller: Dweller) -> int | None:
        """
        Calculate days until dweller's death becomes permanent.

        :param dweller: Dead dweller to check
        :returns: Days remaining, or None if not dead or already permanent
        """
        if not dweller.is_dead or dweller.is_permanently_dead or not dweller.death_timestamp:
            return None

        permanent_date = dweller.death_timestamp + timedelta(days=game_config.death.permanent_death_days)
        now = datetime.now(UTC)

        if now >= permanent_date:
            return 0

        return (permanent_date - now).days

    async def check_and_mark_permanent_deaths(self, db_session: AsyncSession) -> int:
        """
        Check all dead dwellers and mark those past the threshold as permanently dead.

        This should be called by a scheduled task (cron job).

        :param db_session: Database session
        :returns: Number of dwellers marked as permanently dead
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=game_config.death.permanent_death_days)

        # Find dead dwellers past the threshold
        query = (
            select(Dweller)
            .where(Dweller.is_dead == True)
            .where(Dweller.is_permanently_dead == False)
            .where(Dweller.death_timestamp <= cutoff_date)
        )

        result = await db_session.execute(query)
        dwellers_to_mark = result.scalars().all()

        count = 0
        for dweller in dwellers_to_mark:
            await dweller_crud.update(
                db_session,
                dweller.id,
                DwellerUpdate(is_permanently_dead=True),
            )
            logger.info(
                "Dweller %s (%s %s) marked as permanently dead",
                dweller.id,
                dweller.first_name,
                dweller.last_name or "",
            )
            count += 1

        return count

    async def get_death_statistics(self, db_session: AsyncSession, user_id: UUID4) -> dict:
        """
        Get life/death statistics for a user.

        :param db_session: Database session
        :param user_id: User ID
        :returns: Dictionary with death statistics
        """
        profile = await profile_crud.get_by_user_id(db_session, user_id)
        if not profile:
            return {
                "total_dwellers_born": 0,
                "total_dwellers_died": 0,
                "deaths_by_cause": {
                    "health": 0,
                    "radiation": 0,
                    "incident": 0,
                    "exploration": 0,
                    "combat": 0,
                },
                "revivable_count": 0,
                "permanently_dead_count": 0,
            }

        # Get revivable and permanent counts
        revivable_count, permanent_count = await self._get_dead_dweller_counts(db_session, user_id)

        return {
            "total_dwellers_born": profile.total_dwellers_born,
            "total_dwellers_died": profile.total_dwellers_died,
            "deaths_by_cause": {
                "health": profile.deaths_by_health,
                "radiation": profile.deaths_by_radiation,
                "incident": profile.deaths_by_incident,
                "exploration": profile.deaths_by_exploration,
                "combat": profile.deaths_by_combat,
            },
            "revivable_count": revivable_count,
            "permanently_dead_count": permanent_count,
        }

    async def _get_dead_dweller_counts(self, db_session: AsyncSession, user_id: UUID4) -> tuple[int, int]:
        """Get counts of revivable and permanently dead dwellers for a user."""
        from app.models.vault import Vault

        # Get user's vaults
        vault_query = select(Vault.id).where(Vault.user_id == user_id)
        vault_result = await db_session.execute(vault_query)
        vault_ids = [row[0] for row in vault_result.all()]

        if not vault_ids:
            return 0, 0

        # Count revivable (dead but not permanent)
        revivable_query = (
            select(Dweller)
            .where(Dweller.vault_id.in_(vault_ids))
            .where(Dweller.is_dead == True)
            .where(Dweller.is_permanently_dead == False)
        )
        revivable_result = await db_session.execute(revivable_query)
        revivable_count = len(revivable_result.scalars().all())

        # Count permanently dead
        permanent_query = (
            select(Dweller).where(Dweller.vault_id.in_(vault_ids)).where(Dweller.is_permanently_dead == True)
        )
        permanent_result = await db_session.execute(permanent_query)
        permanent_count = len(permanent_result.scalars().all())

        return revivable_count, permanent_count

    async def _increment_death_stats(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        cause: DeathCauseEnum,
    ) -> None:
        """Increment death statistics for the vault owner."""
        vault = await vault_crud.get(db_session, vault_id)
        if not vault or not vault.user_id:
            return

        # Map cause to stat field
        cause_to_field = {
            DeathCauseEnum.HEALTH: "deaths_by_health",
            DeathCauseEnum.RADIATION: "deaths_by_radiation",
            DeathCauseEnum.INCIDENT: "deaths_by_incident",
            DeathCauseEnum.EXPLORATION: "deaths_by_exploration",
            DeathCauseEnum.COMBAT: "deaths_by_combat",
        }

        stat_field = cause_to_field.get(cause)
        if stat_field:
            await profile_crud.increment_statistic(db_session, vault.user_id, stat_field)
            await profile_crud.increment_statistic(db_session, vault.user_id, "total_dwellers_died")

    def _generate_epitaph(self, dweller: Dweller, cause: DeathCauseEnum) -> str:
        """Generate a default epitaph based on death cause."""
        name = f"{dweller.first_name} {dweller.last_name or ''}".strip()

        epitaphs = {
            DeathCauseEnum.HEALTH: f"{name} succumbed to their wounds. Rest in peace.",
            DeathCauseEnum.RADIATION: f"{name} was claimed by the wasteland's radiation. Never forgotten.",
            DeathCauseEnum.INCIDENT: f"{name} fell defending the vault. A true hero.",
            DeathCauseEnum.EXPLORATION: f"{name} was lost in the wasteland. Their sacrifice is remembered.",
            DeathCauseEnum.COMBAT: f"{name} died bravely in combat. Glory to the fallen.",
        }

        return epitaphs.get(cause, f"In memory of {name}.")


# Singleton instance
death_service = DeathService()
