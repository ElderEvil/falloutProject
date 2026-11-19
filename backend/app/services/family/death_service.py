"""Death service for handling dweller death, revival, and life/death statistics."""

import logging
from datetime import timedelta
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import AvailabilityEnum, DeathCauseEnum, DwellerStatusEnum, LifecycleEnum, VaultModeEnum
from app.core.game_config import game_config
from app.crud.dweller import dweller as dweller_crud
from app.crud.user_profile import profile_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.user import User
from app.models.vault import Vault
from app.schemas.dweller import DwellerRead, DwellerReviveResponse, DwellerUpdate, RevivalCostResponse
from app.services.access_service import assert_vault_owner
from app.services.bio_service import bio_service, compile_bio
from app.services.notification_service import notification_service
from app.utils.dweller_lifecycle import is_dead, is_permanently_dead
from app.utils.exceptions import (
    ContentNoChangeException,
    InsufficientResourcesException,
    VaultOperationException,
    ensure_found,
)
from app.utils.time import utcnow

logger = logging.getLogger(__name__)


class DeathService:
    """Service for handling dweller death and revival mechanics."""

    async def mark_as_dead(
        self,
        db_session: AsyncSession,
        dweller: Dweller,
        cause: DeathCauseEnum,
        epitaph: str | None = None,
        commit: bool = True,
        permanent: bool = False,
    ) -> Dweller:
        """Mark a dweller as dead."""
        if dweller.is_dead:
            raise ContentNoChangeException(detail="Dweller is already dead")

        vault_id = self._require_vault_id(dweller)
        vault = await vault_crud.get(db_session, vault_id)

        if vault.vault_mode == VaultModeEnum.SURVIVAL.value:
            permanent = True

        # Generate default epitaph if not provided
        if not epitaph:
            epitaph = self._generate_epitaph(dweller, cause)

        # Naive datetime to match the database TIMESTAMP WITHOUT TIME ZONE (temporary; migrate to tz-aware later).
        now_naive = utcnow()
        bio_entries = bio_service.with_entry(
            dweller,
            "family",
            f"Died from {cause.value} at level {dweller.level}.",
            {"cause": cause.value},
        )

        try:
            updated_dweller = await dweller_crud.update(
                db_session,
                dweller.id,
                DwellerUpdate(
                    is_dead=True,
                    death_timestamp=now_naive,
                    death_cause=cause,
                    epitaph=epitaph,
                    status=DwellerStatusEnum.DEAD,
                    health=0,
                    happiness=0,
                    bio=compile_bio(bio_entries),
                    bio_entries=bio_entries,
                    room_id=None,  # Remove from room
                    is_permanently_dead=permanent,
                    lifecycle=LifecycleEnum.DEAD_PERMANENT if permanent else LifecycleEnum.DEAD_REVIVABLE,
                    availability=AvailabilityEnum.ARCHIVE if permanent else AvailabilityEnum.VAULT,
                ),
                commit=False,
            )

            # Death, both counters and the notification row share one transaction.
            await self._increment_death_stats(db_session, vault, cause, commit=False)
            await notification_service.notify_owner(
                db_session,
                vault_id,
                context=f"dweller_died vault={vault_id} dweller={dweller.id} cause={cause.value}",
                sender=lambda user_id: notification_service.notify_dweller_died(
                    db_session,
                    user_id=user_id,
                    vault_id=vault_id,
                    dweller_id=dweller.id,
                    dweller_name=dweller.display_name,
                    cause=cause.value,
                    meta_data={"cause": cause.value, "vault_id": str(vault_id)},
                    commit=False,
                ),
            )
            if commit:
                await db_session.commit()
        except Exception:
            if commit:
                await db_session.rollback()
                notification_service.discard_deferred_notifications(db_session)
            raise

        if commit:
            await notification_service.deliver_deferred_notifications(db_session)

        logger.info(
            "Dweller %s (%s) died of %s in vault %s",
            dweller.first_name,
            dweller.last_name or "",
            cause.value,
            vault_id,
        )

        return updated_dweller

    async def revive_dweller(
        self,
        db_session: AsyncSession,
        dweller_id: UUID,
        user: User,
    ) -> DwellerReviveResponse:
        """Revive a dead dweller by paying the revival cost.

        Ownership is enforced through the shared vault policy, so the API layer and
        this service cannot drift apart on who may revive.
        """
        dweller = await dweller_crud.get(db_session, dweller_id)

        dweller = ensure_found(dweller, Dweller, identifier=dweller_id)

        self._require_revivable(dweller)

        vault = await vault_crud.lock_for_update(db_session, self._require_vault_id(dweller))
        assert_vault_owner(vault, user)

        # Recheck revival eligibility under the lock: a concurrent revival may have committed since the pre-check and
        # the identity map still holds the stale dead row. Refresh so a duplicate request fails before any deduction.
        await db_session.refresh(dweller)
        self._require_revivable(dweller)

        revival_cost = self.get_revival_cost(dweller.level)
        if vault.bottle_caps < revival_cost:
            raise InsufficientResourcesException(
                resource_name="caps",
                resource_amount=revival_cost - vault.bottle_caps,
            )

        # Calculate health after revival
        revival_health = min(int(dweller.max_health * game_config.death.revival_health_percent), dweller.max_health)

        # This service owns the transaction: caps deduction and revival stage under the vault row lock and commit
        # together. Committing caps first would release the lock early and let a concurrent request read stale state;
        # a failed revival must roll the deduction back.
        remaining_caps = vault.bottle_caps - revival_cost
        try:
            await vault_crud.update(
                db_session,
                vault.id,
                {"bottle_caps": remaining_caps},
                commit=False,
            )
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
                    radiation=0,
                    lifecycle=LifecycleEnum.ALIVE,
                    availability=AvailabilityEnum.VAULT,
                ),
                commit=False,
            )
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

        logger.info(
            "Dweller %s (%s %s) revived for %d caps",
            dweller.id,
            dweller.first_name,
            dweller.last_name or "",
            revival_cost,
        )

        return DwellerReviveResponse(
            dweller=DwellerRead.model_validate(revived_dweller),
            caps_spent=revival_cost,
            remaining_caps=remaining_caps,
        )

    async def build_revival_quote(
        self,
        db_session: AsyncSession,
        dweller_id: UUID,
        user: User,
    ) -> RevivalCostResponse:
        """Quote the revival cost for a dead dweller, reusing the single cost path."""
        dweller = await dweller_crud.get(db_session, dweller_id)
        dweller = ensure_found(dweller, Dweller, identifier=dweller_id)

        self._require_revivable(dweller)

        vault = await vault_crud.get(db_session, self._require_vault_id(dweller))
        assert_vault_owner(vault, user)

        revival_cost = self.get_revival_cost(dweller.level)

        return RevivalCostResponse(
            dweller_id=dweller.id,
            dweller_name=dweller.display_name,
            level=dweller.level,
            revival_cost=revival_cost,
            days_until_permanent=self.get_days_until_permanent(dweller),
            can_afford=vault.bottle_caps >= revival_cost,
            vault_caps=vault.bottle_caps,
        )

    @staticmethod
    def _require_revivable(dweller: Dweller) -> None:
        if not is_dead(dweller):
            raise ContentNoChangeException(detail="Dweller is not dead")
        if is_permanently_dead(dweller):
            raise ContentNoChangeException(detail="Dweller is permanently dead and cannot be revived")

    @staticmethod
    def _require_vault_id(dweller: Dweller) -> UUID:
        """The dweller's active vault, required by death and revival; a departure never reaches here."""
        if dweller.vault_id is None:
            raise VaultOperationException(detail="Dweller is no longer in this vault")
        return dweller.vault_id

    def get_revival_cost(self, level: int) -> int:
        """Calculate the revival cost for a dweller based on their level.

        Tiered: levels 1-5 cost level x 50, 6-10 level x 75, 11+ level x 100 (capped at 2000 caps).
        """
        return game_config.death.calculate_revival_cost(level)

    def get_days_until_permanent(self, dweller: Dweller) -> int | None:
        """Calculate days until dweller's death becomes permanent."""
        if not is_dead(dweller) or is_permanently_dead(dweller) or not dweller.death_timestamp:
            return None

        permanent_date = dweller.death_timestamp + timedelta(days=game_config.death.permanent_death_days)
        now = utcnow()

        if now >= permanent_date:
            return 0

        return (permanent_date - now).days

    async def check_and_mark_permanent_deaths(self, db_session: AsyncSession) -> int:
        """Check all dead dwellers and mark those past the threshold as permanently dead.

        This should be called by a scheduled task (cron job).
        """
        cutoff_date = utcnow() - timedelta(days=game_config.death.permanent_death_days)

        # Find dead dwellers past the threshold
        dwellers_to_mark = await dweller_crud.get_permanently_dead_before(db_session, cutoff_date)

        count = 0
        for dweller in dwellers_to_mark:
            await dweller_crud.update(
                db_session,
                dweller.id,
                DwellerUpdate(
                    is_permanently_dead=True,
                    lifecycle=LifecycleEnum.DEAD_PERMANENT,
                    availability=AvailabilityEnum.ARCHIVE,
                ),
            )
            logger.info(
                "Dweller %s (%s %s) marked as permanently dead",
                dweller.id,
                dweller.first_name,
                dweller.last_name or "",
            )
            count += 1

        return count

    async def get_death_statistics(self, db_session: AsyncSession, user_id: UUID) -> dict:
        """Get life/death statistics for a user."""
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

    async def _get_dead_dweller_counts(self, db_session: AsyncSession, user_id: UUID) -> tuple[int, int]:
        """Get counts of revivable and permanently dead dwellers for a user."""
        vaults = await vault_crud.get_by_user_id(db_session=db_session, user_id=user_id)
        vault_ids = [vault.id for vault in vaults]

        if not vault_ids:
            return 0, 0

        return await dweller_crud.count_death_stats(db_session, vault_ids)

    async def _increment_death_stats(
        self,
        db_session: AsyncSession,
        vault: Vault,
        cause: DeathCauseEnum,
        commit: bool = True,
    ) -> None:
        """Increment death statistics for the vault owner."""
        if not vault.user_id:
            return

        # Map cause to stat field
        cause_to_field = {
            DeathCauseEnum.HEALTH: "deaths_by_health",
            DeathCauseEnum.RADIATION: "deaths_by_radiation",
            DeathCauseEnum.INCIDENT: "deaths_by_incident",
            DeathCauseEnum.EXPLORATION: "deaths_by_exploration",
            DeathCauseEnum.COMBAT: "deaths_by_combat",
            DeathCauseEnum.EXILE: "deaths_by_exploration",
        }

        stat_field = cause_to_field.get(cause)
        if stat_field:
            await profile_crud.increment_statistic(db_session, vault.user_id, stat_field, commit=commit)
            await profile_crud.increment_statistic(db_session, vault.user_id, "total_dwellers_died", commit=commit)

    def _generate_epitaph(self, dweller: Dweller, cause: DeathCauseEnum) -> str:
        """Generate a default epitaph based on death cause."""
        name = dweller.display_name

        epitaphs = {
            DeathCauseEnum.HEALTH: f"{name} succumbed to their wounds. Rest in peace.",
            DeathCauseEnum.RADIATION: f"{name} was claimed by the wasteland's radiation. Never forgotten.",
            DeathCauseEnum.INCIDENT: f"{name} fell defending the vault. A true hero.",
            DeathCauseEnum.EXPLORATION: f"{name} was lost in the wasteland. Their sacrifice is remembered.",
            DeathCauseEnum.COMBAT: f"{name} died bravely in combat. Glory to the fallen.",
            DeathCauseEnum.EXILE: f"{name} asked to go outside. The vault let them go, and they did not return.",
        }

        return epitaphs.get(cause, f"In memory of {name}.")


# Singleton instance
death_service = DeathService()
