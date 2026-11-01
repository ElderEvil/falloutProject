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
from app.core.enums import (
    AgeGroupEnum,
    ContentProvenanceEnum,
    ExpeditionRunStatus,
    ExplorationStatus,
    GenderEnum,
    RarityEnum,
)
from app.core.game_config import game_config
from app.crud.vault_slot import vault_slot
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


@dataclass
class ExpeditionScenarioMultiResult:
    """A vault seeded with several dwellers, each limited to one expedition site."""

    vault: Vault
    created_vault: bool
    owner_email: str | None
    entries: list[ExpeditionScenarioResult]


VAULT_ONE_DWELLERS = (
    ("Ada", "Voss", GenderEnum.FEMALE, (6, 5, 5, 6, 5, 4, 5)),
    ("Bram", "Cole", GenderEnum.MALE, (5, 4, 6, 5, 4, 6, 5)),
    ("Cora", "Reyes", GenderEnum.FEMALE, (4, 6, 5, 5, 6, 5, 4)),
    ("Dane", "Holt", GenderEnum.MALE, (6, 5, 5, 4, 4, 5, 6)),
    ("Elin", "Marsh", GenderEnum.FEMALE, (5, 6, 4, 5, 6, 5, 4)),
    ("Finn", "Barrett", GenderEnum.MALE, (5, 5, 6, 4, 5, 5, 5)),
    ("Gale", "Rook", GenderEnum.FEMALE, (5, 5, 5, 5, 5, 5, 6)),
    ("Hollis", "Vance", GenderEnum.MALE, (6, 4, 5, 5, 4, 6, 5)),
    ("Iris", "Bell", GenderEnum.FEMALE, (4, 5, 6, 6, 5, 4, 5)),
    ("Jasper", "Kane", GenderEnum.MALE, (5, 6, 4, 4, 6, 5, 5)),
    ("Mira", "Sato", GenderEnum.FEMALE, (5, 4, 5, 6, 6, 5, 4)),
    ("Nolan", "Cross", GenderEnum.MALE, (6, 5, 6, 4, 4, 5, 5)),
)


def default_multi_site_ids() -> list[str]:
    """Every authored non-scenario site, in catalog order."""
    return [site.id for site in data_loader.load_expedition_sites() if not site.scenario_only]


def uniform_stats(special: int) -> tuple[int, int, int, int, int, int, int]:
    """Every SPECIAL stat clamped to the allowed 1-10 range."""
    value = max(1, min(10, special))
    return (value, value, value, value, value, value, value)


def _outbound_duration(travel_hours: float, outbound_hours: int) -> int:
    """Journey length that still leaves ``outbound_hours`` before the outbound leg ends (24h cap)."""
    return max(1, min(24, math.ceil(2 * (travel_hours + outbound_hours))))


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
        single_scene_only: bool = True,
        scenario_site_id: str | None = None,
        choice_only: bool = False,
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
        one. ``single_scene_only`` hides multi-room sites from that journey;
        ``choice_only`` limits it to stat-check choice encounters.
        ``vault_number`` selects the number for a newly created vault.
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
        scenario_site = data_loader.get_expedition_site(scenario_site_id) if scenario_site_id else None
        if scenario_site_id is not None:
            if scenario_site is None:
                raise ValueError(f"Unknown expedition site: {scenario_site_id!r}")
            if dweller_level < scenario_site.min_dweller_level:
                raise ValueError(f"{scenario_site.name} needs dweller level {scenario_site.min_dweller_level}")
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
        dweller = existing_dweller or await self._create_scenario_dweller(
            db_session, vault, stats=uniform_stats(special)
        )
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
            await self._make_all_sites_active_transaction(
                db_session,
                exploration,
                single_scene_only=single_scene_only,
                scenario_site_id=scenario_site_id,
                choice_only=choice_only,
            )
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

    async def setup_multi(
        self,
        db_session: AsyncSession,
        *,
        vault_id: UUID4 | None = None,
        vault_number: int = 1,
        user_email: str | None = None,
        dwellers: int | None = None,
        dweller_level: int = 5,
        duration_hours: int = 24,
        special: int | None = None,
        site_ids: list[str] | None = None,
        recreate: bool = False,
        discover: bool = True,
        outbound_hours: int = 8,
    ) -> ExpeditionScenarioMultiResult:
        """Seed a vault with named dwellers, each scouting one expedition site.

        ``vault_number`` is used only when no ``vault_id`` is given. With
        ``recreate`` any existing vault with that number for the owner is
        soft-deleted first, so the scenario starts from a fresh boosted vault;
        otherwise the existing vault is reused. With ``discover`` each dweller's
        journey is fast-forwarded along a trail past its site, so the site is
        reported in the bell while the dweller keeps an ``outbound_hours``
        outbound window; otherwise the journey stays legacy and its picker is
        filtered to that one site.
        """
        site_ids = site_ids or default_multi_site_ids()
        if not site_ids:
            raise ValueError("At least one expedition site is required")
        dwellers = len(site_ids) if dwellers is None else dwellers
        if dwellers > len(site_ids):
            raise ValueError("Each dweller needs its own site; pass more site ids or fewer dwellers")
        dwellers = max(1, min(len(VAULT_ONE_DWELLERS), dwellers))
        dweller_level = max(1, min(50, dweller_level))
        duration_hours = max(1, min(24, duration_hours))
        for site_id in site_ids:
            site = data_loader.get_expedition_site(site_id)
            if site is None:
                raise ValueError(f"Unknown expedition site: {site_id!r}")
            if dweller_level < site.min_dweller_level:
                raise ValueError(f"{site.name} needs dweller level {site.min_dweller_level}")

        if vault_id is not None:
            vault, created_vault, owner_email = await self._resolve_vault(
                db_session, vault_id=vault_id, user_email=user_email
            )
        else:
            owner = await crud.user.get_by_email(db_session, email=user_email or settings.FIRST_SUPERUSER_EMAIL)
            if owner is None:
                raise ValueError("No superuser found — run 'uv run fo-cli createsuperuser --no-input' first")
            vaults = await crud.vault.get_by_user_id(db_session=db_session, user_id=owner.id)
            matching = [candidate for candidate in vaults if candidate.number == vault_number]
            if recreate:
                for candidate in matching:
                    await crud.vault.delete(db_session, candidate.id, soft=True)
                matching = []
            vault = matching[0] if matching else None
            created_vault = vault is None
            if vault is None:
                vault = await vault_service.initiate_vault(
                    db_session,
                    obj_in=VaultNumber(number=vault_number, boosted=True),
                    user_id=owner.id,
                    is_boosted=True,
                )
            owner_email = owner.email

        if discover and await vault_slot.get_by_vault(db_session, vault.id) is None:
            await vault_slot.claim_next(db_session=db_session, vault_id=vault.id)

        entries: list[ExpeditionScenarioResult] = []
        for index in range(dwellers):
            first_name, last_name, gender, profile_stats = VAULT_ONE_DWELLERS[index]
            stats = uniform_stats(special) if special is not None else profile_stats
            dweller = await self._create_scenario_dweller(
                db_session,
                vault,
                stats=stats,
                gender=gender,
                first_name=first_name,
                last_name=last_name,
            )
            levels = dweller_level - dweller.level
            if levels > 0:
                await leveling_service.level_up_dweller(db_session, dweller, levels=levels)
            site_id = site_ids[index % len(site_ids)]
            site = data_loader.get_expedition_site(site_id)
            if site is None:
                raise ValueError(f"Unknown expedition site: {site_id!r}")
            exploration = await exploration_service.send_dweller(
                db_session,
                vault_id=vault.id,
                dweller_id=dweller.id,
                duration=duration_hours,
                stimpaks=0,
                radaways=0,
            )
            if discover:
                travel_hours = self._stage_trail_to_site(exploration, site)
                exploration.duration = _outbound_duration(travel_hours, outbound_hours)
                db_session.add(exploration)
                await db_session.commit()
                await expedition_service.discover_sites(db_session, exploration.id)
            else:
                await self._make_all_sites_active_transaction(
                    db_session,
                    exploration,
                    single_scene_only=False,
                    scenario_site_id=site_id,
                    choice_only=False,
                )
            available_sites = await expedition_service.list_available_sites(db_session, exploration.id)
            if not available_sites:
                raise ValueError(f"{site_id} is not available for {dweller.display_name}")
            entries.append(
                ExpeditionScenarioResult(
                    vault=vault,
                    dweller=dweller,
                    exploration=exploration,
                    available_sites=available_sites,
                    precleared_site_id=None,
                    created_vault=created_vault,
                    owner_email=owner_email,
                    discovered_site_id=site.id if discover else None,
                )
            )
        return ExpeditionScenarioMultiResult(
            vault=vault,
            created_vault=created_vault,
            owner_email=owner_email,
            entries=entries,
        )

    @staticmethod
    async def _make_all_sites_active_transaction(
        db_session: AsyncSession,
        exploration: Exploration,
        *,
        single_scene_only: bool,
        scenario_site_id: str | None,
        choice_only: bool,
    ) -> None:
        """Turn the scenario into a legacy active journey so eligible sites are offered.

        Spatial journeys only offer sites near the traveled trail. Clearing the
        spatial fields makes ``list_available_sites`` use the legacy catalog, so
        one Scout can enter every eligible site one by one.
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
                "description": "QA scenario: eligible sites unlocked for this journey.",
                "single_scene_only": single_scene_only,
                "scenario_site_id": scenario_site_id,
                "choice_only": choice_only,
                "timestamp": now.isoformat(),
            },
        ]
        db_session.add(exploration)
        await db_session.commit()

    @staticmethod
    def _stage_trail_to_site(exploration: Exploration, site: SiteDefinition) -> float:
        """Fast-forward a trail from the vault origin to the site; returns travel hours.

        Setup is deliberately multi-stage: vault/scout/departure remain durable
        if fast-forwarding or report delivery fails. This stage changes only the
        exploration row; the caller commits it before discover_sites owns its
        separate atomic report transaction.
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
        return travel_hours

    @classmethod
    def _stage_discovery(cls, exploration: Exploration, site: SiteDefinition) -> None:
        """Stage a fast-forwarded QA trail at the site and start the return leg."""
        cls._stage_trail_to_site(exploration, site)
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
    async def _create_scenario_dweller(
        db_session: AsyncSession,
        vault: Vault,
        *,
        stats: tuple[int, int, int, int, int, int, int] = (5, 5, 5, 5, 5, 5, 5),
        gender: GenderEnum = GenderEnum.MALE,
        first_name: str = "Scout",
        last_name: str = "Scenario",
    ) -> Dweller:
        """Create a scenario dweller with the given SPECIAL stats."""
        strength, perception, endurance, charisma, intelligence, agility, luck = stats
        return await dweller_service.create_dweller(
            db_session,
            DwellerCreate(
                first_name=first_name,
                last_name=last_name,
                gender=gender,
                rarity=RarityEnum.COMMON,
                age_group=AgeGroupEnum.ADULT,
                birth_date=_now(),
                vault_id=vault.id,
                strength=strength,
                perception=perception,
                endurance=endurance,
                charisma=charisma,
                intelligence=intelligence,
                agility=agility,
                luck=luck,
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
