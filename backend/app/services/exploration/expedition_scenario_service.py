"""Dev/QA service for provisioning a playable interactive expedition-site scenario."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import UUID4  # ruff: ignore[typing-only-third-party-import]

from app import crud
from app.core.config import settings
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.models.exploration import ExpeditionRunStatus
from app.schemas.dweller import DwellerCreate
from app.schemas.vault import VaultNumber
from app.services.dweller_service import dweller_service
from app.services.exploration import data_loader
from app.services.exploration.expedition import expedition_service
from app.services.exploration_service import exploration_service
from app.services.leveling_service import leveling_service
from app.services.vault_service import vault_service

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller
    from app.models.exploration import Exploration
    from app.models.vault import Vault
    from app.schemas.expedition import AvailableSiteView


def _now() -> datetime:
    """Return a naive UTC timestamp consistent with persisted game timestamps."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class ExpeditionScenarioResult:
    """The vault, dweller, exploration, and site picker produced by setup."""

    vault: Vault
    dweller: Dweller
    exploration: Exploration
    available_sites: list[AvailableSiteView]
    precleared_site_id: str | None
    created_vault: bool
    owner_email: str | None = None


@dataclass
class ExpeditionScenarioExplorationStatus:
    """One in-progress exploration in a scenario vault."""

    exploration_id: UUID4
    dweller_name: str
    dweller_level: int
    status: str
    time_remaining_seconds: int
    available_sites: list[AvailableSiteView]
    open_run_site_id: str | None


@dataclass
class ExpeditionScenarioStatus:
    """A display-ready snapshot of every in-progress exploration in a vault."""

    explorations: list[ExpeditionScenarioExplorationStatus]


class ExpeditionScenarioService:
    """Opt-in builder for a ready-to-play interactive expedition-site scenario."""

    async def setup(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID4 | None = None,
        user_email: str | None = None,
        dweller_level: int = 5,
        duration_hours: int = 8,
        preclear_site_id: str | None = None,
    ) -> ExpeditionScenarioResult:
        """Provision a vault with one dweller on an active exploration.

        When ``vault_id`` is omitted a new boosted vault is created for the
        superuser (or ``user_email`` when given). ``duration_hours`` is clamped
        to the exploration model's 1-24 hour range. ``preclear_site_id`` inserts
        a completed run so the 7-day anti-farm gate hides the site from the
        picker, demonstrating the lock.
        """
        duration_hours = max(1, min(24, duration_hours))
        dweller_level = max(1, min(50, dweller_level))

        vault, created_vault, owner_email = await self._resolve_vault(
            db_session, vault_id=vault_id, user_email=user_email
        )
        dweller = await self._create_scenario_dweller(db_session, vault)
        levels = dweller_level - dweller.level
        if levels > 0:
            await leveling_service.level_up_dweller(db_session, dweller, levels=levels)
        exploration = await exploration_service.send_dweller(
            db_session,
            vault_id=vault.id,
            dweller_id=dweller.id,
            duration=duration_hours,
            stimpaks=0,
            radaways=0,
        )
        precleared = await self._preclear_site(db_session, exploration, vault, dweller, preclear_site_id)
        available_sites = await expedition_service.list_available_sites(db_session, exploration.id)
        return ExpeditionScenarioResult(
            vault=vault,
            dweller=dweller,
            exploration=exploration,
            available_sites=available_sites,
            precleared_site_id=precleared,
            created_vault=created_vault,
            owner_email=owner_email,
        )

    @staticmethod
    async def _resolve_vault(
        db_session: AsyncSession, *, vault_id: UUID4 | None, user_email: str | None
    ) -> tuple[Vault, bool, str | None]:
        """Return the target vault, whether this call created it, and its owner's email."""
        if vault_id is not None:
            vault = await crud.vault.get(db_session, vault_id)
            owner = await crud.user.get(db_session, vault.user_id) if vault.user_id else None
            return vault, False, owner.email if owner else None
        owner = await crud.user.get_by_email(db_session, email=user_email or settings.FIRST_SUPERUSER_EMAIL)
        if owner is None:
            raise ValueError("No superuser found — run 'uv run fo-cli createsuperuser --no-input' first")
        vault = await vault_service.initiate_vault(
            db_session,
            obj_in=VaultNumber(number=random.randint(1, 999), boosted=True),
            user_id=owner.id,
            is_boosted=True,
        )
        return vault, True, owner.email

    @staticmethod
    async def _create_scenario_dweller(db_session: AsyncSession, vault: Vault) -> Dweller:
        """Create the recognisable scenario dweller through the real service."""
        return await dweller_service.create_dweller(
            db_session,
            DwellerCreate(
                first_name="Scout",
                last_name="Scenario",
                gender=GenderEnum.MALE,
                rarity=RarityEnum.COMMON,
                is_adult=True,
                age_group=AgeGroupEnum.ADULT,
                birth_date=_now(),
                vault_id=vault.id,
            ),
        )

    @staticmethod
    async def _preclear_site(
        db_session: AsyncSession,
        exploration: Exploration,
        vault: Vault,
        dweller: Dweller,
        preclear_site_id: str | None,
    ) -> str | None:
        """Insert a completed run so the anti-farm gate hides the site, or None."""
        if preclear_site_id is None:
            return None
        site = data_loader.get_expedition_site(preclear_site_id)
        if site is None:
            raise ValueError(f"Unknown expedition site: {preclear_site_id!r}")
        run = await crud.expedition_run.create_run(
            db_session,
            exploration_id=exploration.id,
            vault_id=vault.id,
            dweller_id=dweller.id,
            site_id=preclear_site_id,
        )
        run.status = ExpeditionRunStatus.CLEARED
        run.cleared_at = _now()
        db_session.add(run)
        await db_session.commit()
        return preclear_site_id

    async def get_status(self, db_session: AsyncSession, vault_id: UUID4) -> ExpeditionScenarioStatus | None:
        """Return a read-only snapshot of the vault's in-progress explorations."""
        explorations = await crud.exploration.get_by_vault(db_session, vault_id=vault_id, active_only=True)
        if not explorations:
            return None
        entries: list[ExpeditionScenarioExplorationStatus] = []
        for exploration in explorations:
            dweller = await crud.dweller.get(db_session, exploration.dweller_id)
            open_run = await crud.expedition_run.get_open_for_exploration(db_session, exploration.id)
            entries.append(
                ExpeditionScenarioExplorationStatus(
                    exploration_id=exploration.id,
                    dweller_name=dweller.display_name,
                    dweller_level=dweller.level,
                    status=exploration.status.value,
                    time_remaining_seconds=exploration.time_remaining_seconds(),
                    available_sites=(
                        await expedition_service.list_available_sites(db_session, exploration.id)
                        if exploration.is_active()
                        else []
                    ),
                    open_run_site_id=open_run.site_id if open_run is not None else None,
                )
            )
        return ExpeditionScenarioStatus(explorations=entries)


expedition_scenario_service = ExpeditionScenarioService()
