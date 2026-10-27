"""Dev/QA service for provisioning a playable interactive expedition-site scenario."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import UUID4  # ruff: ignore[typing-only-third-party-import]

from app import crud
from app.core.config import settings
from app.core.enums import AgeGroupEnum, ContentProvenanceEnum, GenderEnum, RarityEnum
from app.core.game_config import game_config
from app.crud.vault_slot import vault_slot
from app.models.exploration import ExpeditionRunStatus, ExplorationStatus
from app.schemas.dweller import DwellerCreate
from app.schemas.vault import VaultNumber
from app.services import catalog_service as data_loader
from app.services.dweller_service import dweller_service
from app.services.exploration.expedition import ALL_SITES_SCENARIO_EVENT, expedition_service
from app.services.exploration_service import exploration_service
from app.services.leveling_service import leveling_service
from app.services.vault_service import vault_service

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller
    from app.models.exploration import Exploration
    from app.models.vault import Vault
    from app.schemas.expedition import AvailableSiteView, SiteDefinition


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
    discovered_site_id: str | None = None


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
        duration_hours: int = 1,
        preclear_site_id: str | None = None,
        special: int = 5,
        discovered_site_id: str | None = None,
        dweller_id: UUID4 | None = None,
        vault_number: int | None = None,
        all_sites: bool = False,
    ) -> ExpeditionScenarioResult:
        """Provision a vault with one dweller on an active exploration.

        When ``vault_id`` is omitted a new boosted vault is created for the
        superuser (or ``user_email`` when given). ``duration_hours`` is clamped
        to the exploration model's 1-24 hour range. ``preclear_site_id`` inserts
        a completed run so the 7-day anti-farm gate hides the site from the
        picker, demonstrating the lock. ``special`` sets every SPECIAL stat
        (1-10); 5 keeps site checks differentiated (95/85/75) while still
        winning most fights, 1 tests defeat/death, 7+ trivialises checks.

        ``all_sites`` leaves a legacy (non-spatial) active journey where every
        level-eligible site is offered, so one Scout can play all sites one by
        one. ``vault_number`` selects the number for a newly created vault.
        """
        duration_hours = max(1, min(24, duration_hours))
        dweller_level = max(1, min(50, dweller_level))
        existing_dweller = await crud.dweller.get(db_session, dweller_id) if dweller_id is not None else None
        if existing_dweller is not None:
            if existing_dweller.vault_id is None or (vault_id is not None and existing_dweller.vault_id != vault_id):
                raise ValueError("The selected dweller does not belong to the target vault")
            vault_id = existing_dweller.vault_id
            dweller_level = existing_dweller.level
        if preclear_site_id is not None and data_loader.get_expedition_site(preclear_site_id) is None:
            raise ValueError(f"Unknown expedition site: {preclear_site_id!r}")
        discovered_site = data_loader.get_expedition_site(discovered_site_id) if discovered_site_id else None
        if discovered_site_id is not None:
            if discovered_site is None:
                raise ValueError(f"Unknown expedition site: {discovered_site_id!r}")
            if dweller_level < discovered_site.min_dweller_level:
                raise ValueError(f"{discovered_site.name} needs dweller level {discovered_site.min_dweller_level}")
            if discovered_site_id == preclear_site_id:
                raise ValueError("The discovered site cannot also be pre-cleared")

        vault, created_vault, owner_email = await self._resolve_vault(
            db_session, vault_id=vault_id, user_email=user_email, vault_number=vault_number
        )
        if discovered_site is not None and await vault_slot.get_by_vault(db_session, vault.id) is None:
            await vault_slot.claim_next(db_session=db_session, vault_id=vault.id)
        dweller = existing_dweller or await self._create_scenario_dweller(db_session, vault, special=special)
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
        precleared = await self._preclear_site(db_session, exploration, vault, preclear_site_id)
        if all_sites:
            await self._make_all_sites_active_transaction(db_session, exploration)
        elif discovered_site is not None:
            self._stage_discovery(exploration, discovered_site)
            db_session.add(exploration)
            await db_session.commit()
            await expedition_service.discover_sites(db_session, exploration.id)
        available_sites = await expedition_service.list_available_sites(db_session, exploration.id)
        return ExpeditionScenarioResult(
            vault=vault,
            dweller=dweller,
            exploration=exploration,
            available_sites=available_sites,
            precleared_site_id=precleared,
            created_vault=created_vault,
            owner_email=owner_email,
            discovered_site_id=discovered_site_id,
        )

    @staticmethod
    async def _make_all_sites_active_transaction(db_session: AsyncSession, exploration: Exploration) -> None:
        """Turn the scenario into a legacy active journey so every site is offered.

        Spatial journeys only offer sites near the traveled trail. Clearing the
        spatial fields makes ``list_available_sites`` use the legacy catalog, so
        one Scout can enter every level-eligible site one by one.
        """
        now = _now()
        exploration.heading_degrees = None
        exploration.world_version = None
        exploration.origin_x = None
        exploration.origin_y = None
        exploration.pos_x = None
        exploration.pos_y = None
        exploration.position_as_of = None
        exploration.trail = []
        exploration.start_time = now - timedelta(hours=min(1, exploration.duration / 2))
        exploration.status = ExplorationStatus.ACTIVE
        exploration.return_started_at = None
        exploration.return_completes_at = None
        exploration.end_time = None
        exploration.paused_at = None
        exploration.events = [
            *exploration.events,
            {
                "type": "scenario",
                "event": ALL_SITES_SCENARIO_EVENT,
                "description": "QA scenario: all sites unlocked for this journey.",
                "timestamp": now.isoformat(),
            },
        ]
        db_session.add(exploration)
        await db_session.commit()

    @staticmethod
    def _stage_discovery(exploration: Exploration, site: SiteDefinition) -> None:
        """Stage a fast-forwarded QA trail at the site and start the return leg.

        Setup is deliberately multi-stage: vault/scout/departure remain durable
        if fast-forwarding or report delivery fails. This stage changes only the
        exploration row; setup commits it before discover_sites owns its separate
        atomic report transaction.
        """
        origin_x, origin_y = exploration.origin_x, exploration.origin_y
        if origin_x is None or origin_y is None:
            raise ValueError("A discovered-site scenario requires a vault map placement")
        now = _now()
        travel_hours = math.dist((origin_x, origin_y), (site.coord_x, site.coord_y)) * (
            game_config.exploration.dispatch.travel_hours_per_unit
        )
        exploration.heading_degrees = math.degrees(math.atan2(site.coord_x - origin_x, origin_y - site.coord_y)) % 360
        exploration.start_time = now - timedelta(hours=travel_hours)
        exploration.pos_x, exploration.pos_y = site.coord_x, site.coord_y
        exploration.position_as_of = now
        exploration.trail = [
            {"x": origin_x, "y": origin_y, "t": exploration.start_time.isoformat()},
            {"x": site.coord_x, "y": site.coord_y, "t": now.isoformat()},
        ]
        exploration.start_return()

    @staticmethod
    async def _resolve_vault(
        db_session: AsyncSession,
        *,
        vault_id: UUID4 | None,
        user_email: str | None,
        vault_number: int | None = None,
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
            obj_in=VaultNumber(number=vault_number or random.randint(1, 999), boosted=True),
            user_id=owner.id,
            is_boosted=True,
        )
        return vault, True, owner.email

    @staticmethod
    async def _create_scenario_dweller(db_session: AsyncSession, vault: Vault, *, special: int = 5) -> Dweller:
        """Create the scenario dweller with every SPECIAL stat set to ``special`` (1-10)."""
        value = max(1, min(10, special))
        return await dweller_service.create_dweller(
            db_session,
            DwellerCreate(
                first_name="Scout",
                last_name="Scenario",
                gender=GenderEnum.MALE,
                rarity=RarityEnum.COMMON,
                age_group=AgeGroupEnum.ADULT,
                birth_date=_now(),
                vault_id=vault.id,
                strength=value,
                perception=value,
                endurance=value,
                charisma=value,
                intelligence=value,
                agility=value,
                luck=value,
            ),
            content_provenance=ContentProvenanceEnum.GENERATED,
        )

    @staticmethod
    async def _preclear_site(
        db_session: AsyncSession,
        exploration: Exploration,
        vault: Vault,
        preclear_site_id: str | None,
    ) -> str | None:
        """Insert a completed run so the anti-farm gate hides the site, or None."""
        if preclear_site_id is None:
            return None
        run = await crud.expedition_run.create_run(
            db_session,
            exploration_id=exploration.id,
            vault_id=vault.id,
            site_id=preclear_site_id,
        )
        run.status = ExpeditionRunStatus.CLEARED
        run.finished_at = _now()
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
                        if exploration.is_in_progress()
                        else []
                    ),
                    open_run_site_id=open_run.site_id if open_run is not None else None,
                )
            )
        return ExpeditionScenarioStatus(explorations=entries)


expedition_scenario_service = ExpeditionScenarioService()
