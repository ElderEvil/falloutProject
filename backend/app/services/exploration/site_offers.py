"""Trail-relative site offers and the per-vault/site expedition gate."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import ExpeditionRunStatus
from app.crud.world_snapshot import world_snapshot as world_snapshot_crud
from app.models.exploration import Exploration
from app.schemas.expedition import SiteDefinition
from app.services.map.world_generation import WORLD_ID
from app.utils import world_terrain

ANTI_FARM_DAYS = 7


@dataclass(frozen=True)
class SiteBlockState:
    """Per-vault+site expedition gate: block reason plus remaining anti-farm seconds."""

    reason: Literal["open", "cooldown"] | None = None
    cooldown_remaining_seconds: int = 0
    cleared: bool = False


@dataclass(frozen=True)
class JourneyOfferContext:
    """Trail-relative inputs that decide which sites a spatial journey offers."""

    trail: list[tuple[float, float]]
    radius: float
    consumed_site_ids: frozenset[str]


async def journey_offer_context(db_session: AsyncSession, exploration: Exploration) -> JourneyOfferContext | None:
    """Trail offer inputs for a spatial run, or None when terrain/version is unavailable."""
    if exploration.heading_degrees is None or exploration.world_version is None:
        return None
    snapshot = await world_snapshot_crud.get_version(
        db_session, world_id=WORLD_ID, generator_version=exploration.world_version
    )
    if snapshot is None:
        return None
    consumed = await crud.expedition_run.get_consumed_site_ids_for_exploration(
        db_session, exploration_id=exploration.id
    )
    return JourneyOfferContext(
        trail=[(float(step["x"]), float(step["y"])) for step in (exploration.trail or [])],
        radius=world_terrain.reveal_radius_registry(snapshot, world_terrain.SITE_REVEAL_TILES),
        consumed_site_ids=frozenset(consumed),
    )


def site_is_offered(site: SiteDefinition, context: JourneyOfferContext) -> bool:
    """True when a spatial journey offers *site*: near its trail and not yet consumed."""
    return site.id not in context.consumed_site_ids and world_terrain.path_passes_near(
        context.trail, (site.coord_x, site.coord_y), context.radius
    )


def uses_single_scene(site: SiteDefinition, *, spatial: bool) -> bool:
    """Use encounter content for spatial visits and sites without legacy rooms."""
    return site.encounter is not None and (spatial or not site.rooms)


async def site_block_state(
    db_session: AsyncSession, vault_id: UUID4, site_id: str, *, include_open: bool = True
) -> SiteBlockState:
    """Return the vault/site expedition gate with the remaining anti-farm window."""
    if (
        include_open
        and await crud.expedition_run.get_open_for_vault_site(db_session, vault_id=vault_id, site_id=site_id)
        is not None
    ):
        return SiteBlockState(reason="open")
    recent = await crud.expedition_run.get_recent_terminal(
        db_session,
        vault_id=vault_id,
        site_id=site_id,
        since=datetime.utcnow() - timedelta(days=ANTI_FARM_DAYS),
    )
    if recent is None:
        return SiteBlockState()
    cleared = recent.status == ExpeditionRunStatus.CLEARED
    if recent.finished_at is None:
        return SiteBlockState(reason="cooldown", cleared=cleared)
    window_end = recent.finished_at + timedelta(days=ANTI_FARM_DAYS)
    remaining = max(0, int((window_end - datetime.utcnow()).total_seconds()))
    return SiteBlockState(reason="cooldown", cooldown_remaining_seconds=remaining, cleared=cleared)


async def site_block_reason(
    db_session: AsyncSession, vault_id: UUID4, site_id: str, *, include_open: bool = True
) -> Literal["open", "cooldown"] | None:
    """Return the vault/site gate that prevents a new entry or finale payout."""
    return (await site_block_state(db_session, vault_id, site_id, include_open=include_open)).reason
