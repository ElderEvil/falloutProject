"""Map bio registration: bio places, the home marker, and failure notification.

Best-effort by design: a failed registration is logged and reported through the
notification bell rather than raised, because bio generation must not fail on
map bookkeeping. Public operations are called through ``MapService`` in
``app.services.map_service``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pydantic import UUID4  # ruff: ignore[typing-only-third-party-import]

from app.core.enums import (
    DwellerLocationRelationEnum,
    LocationTypeEnum,
    NotificationPriority,
    NotificationType,
    RarityEnum,
)
from app.core.game_config import game_config
from app.crud.vault import vault as vault_crud
from app.crud.vault_slot import vault_slot as vault_slot_crud
from app.crud.world_location import world_location as wl_crud
from app.services.notification_service import notification_service
from app.utils.places import GENERIC_ORIGIN_SKIP, normalize_place_name
from app.utils.vault_slots import slot_coords

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller
    from app.models.vault import Vault
    from app.models.world_location import WorldLocation

logger = logging.getLogger(__name__)


class _MapDwellerLike(Protocol):
    """Structural protocol for dweller objects used by map registration methods."""

    id: UUID4
    vault_id: UUID4
    rarity: RarityEnum


@dataclass(frozen=True)
class _MapDwellerSnapshot:
    """Map registration values preserved across a session rollback."""

    id: UUID4
    vault_id: UUID4
    rarity: RarityEnum


def _should_skip(name: str) -> bool:
    """Return True when *name* is generic / empty and should be dropped."""
    if not name:
        return True
    return normalize_place_name(name) in GENERIC_ORIGIN_SKIP


async def ensure_home_marker(db_session: AsyncSession, vault: Vault) -> WorldLocation:
    """Home-vault marker at the vault's slot placement + per-vault HOME_VAULT state."""
    slot = await vault_slot_crud.get_by_vault(db_session, vault.id)
    coord_x, coord_y = slot_coords(slot.slot_index) if slot is not None else (50.0, 50.0)
    home = await wl_crud.get_or_create_home_marker(db_session, vault, coord_x=coord_x, coord_y=coord_y)
    await wl_crud.ensure_home_state(
        db_session,
        vault.id,
        home.id,
        description=f"Your vault — Vault {vault.number:03}",
    )
    return home


async def link_home_origin(db_session: AsyncSession, dweller: Dweller, vault: Vault) -> None:
    """Ensure the home marker exists and link *dweller* to it as ORIGIN — best-effort."""
    try:
        home = await ensure_home_marker(db_session, vault)
        await wl_crud.link_dweller(db_session, dweller.id, home.id, DwellerLocationRelationEnum.ORIGIN)
    except Exception:
        logger.exception("link_home_origin failed: dweller=%s vault=%s", dweller.id, vault.id)


async def register_bio_places(
    db_session: AsyncSession,
    dweller: _MapDwellerLike,
    origin_place: str,
    visited_places: list[str],
    explicit_origin: str | None = None,
    *,
    commit: bool = True,
) -> bool:
    """Upsert bio origin + rarity-scaled visited location rows — best-effort.

    *effective origin* = *explicit_origin* when truthy, else *origin_place*.
    If the effective origin normalises to a generic skip token we suppress it.
    Every visited name (max 64 chars, skip-list applied) is upserted, capped
    at ``game_config.bio.max_visited`` for the dweller's rarity. The cap is
    uniform: curated templates obey it too (they author the best N places,
    not every mention).

    A failed attempt rolls back its savepoint before retrying. With commit=False,
    the caller owns persistence and must notify failure after its own commit.

    Returns ``True`` when the registration succeeded (or nothing needed to be
    done), and ``False`` when it failed after the internal retry.
    """
    map_dweller = _MapDwellerSnapshot(
        id=dweller.id,
        vault_id=dweller.vault_id,
        rarity=dweller.rarity,
    )
    for attempt in range(2):
        try:
            async with db_session.begin_nested():
                await _register_bio_places_once(
                    db_session,
                    map_dweller,
                    origin_place,
                    visited_places,
                    explicit_origin,
                )
        except Exception:
            if attempt == 0:
                logger.warning(
                    "register_bio_places retrying after failure: dweller=%s vault=%s origin=%r",
                    map_dweller.id,
                    map_dweller.vault_id,
                    origin_place,
                    exc_info=True,
                )
                continue

            logger.exception(
                "register_bio_places failed after retry: dweller=%s vault=%s origin=%r",
                map_dweller.id,
                map_dweller.vault_id,
                origin_place,
            )
        else:
            if commit:
                try:
                    await db_session.commit()
                except Exception:
                    await db_session.rollback()
                    logger.exception(
                        "register_bio_places could not commit: dweller=%s vault=%s origin=%r",
                        map_dweller.id,
                        map_dweller.vault_id,
                        origin_place,
                    )
                    await notify_bio_registration_failure(db_session, map_dweller)
                    return False
            return True

    if commit:
        await notify_bio_registration_failure(db_session, map_dweller)
    return False


async def _register_bio_places_once(
    db_session: AsyncSession,
    dweller: _MapDwellerSnapshot,
    origin_place: str,
    visited_places: list[str],
    explicit_origin: str | None,
) -> None:
    """Register bio places once; callers handle best-effort recovery."""
    effective_origin = explicit_origin or origin_place

    # --- origin ---
    if not _should_skip(effective_origin):
        origin_location = await wl_crud.get_or_create_location(
            db_session,
            effective_origin[:64],
            commit=False,
        )
        await wl_crud.get_or_create_state(
            db_session,
            dweller.vault_id,
            origin_location.id,
            LocationTypeEnum.ORIGIN,
            commit=False,
        )
        await wl_crud.link_dweller(
            db_session, dweller.id, origin_location.id, DwellerLocationRelationEnum.ORIGIN, commit=False
        )

    # --- visited (rarity-scaled cap, de-dupe against origin, apply skip-list) ---
    origin_normalized = normalize_place_name(effective_origin)
    visited = 0
    max_visited = game_config.bio.max_visited(dweller.rarity.value)
    for raw_name in visited_places:
        if visited >= max_visited:
            break
        if not raw_name or _should_skip(raw_name):
            continue
        name = raw_name[:64]
        n_name = normalize_place_name(name)
        # do not create a visited entry that collides with the origin row
        if n_name == origin_normalized:
            continue
        loc = await wl_crud.get_or_create_location(
            db_session,
            name,
            commit=False,
        )
        await wl_crud.get_or_create_state(
            db_session,
            dweller.vault_id,
            loc.id,
            LocationTypeEnum.VISITED,
            commit=False,
        )
        await wl_crud.link_dweller(db_session, dweller.id, loc.id, DwellerLocationRelationEnum.VISITED, commit=False)
        visited += 1


async def notify_bio_registration_failure(
    db_session: AsyncSession,
    dweller: _MapDwellerLike | _MapDwellerSnapshot,
) -> None:
    """Persist an actionable notification when map registration exhausts its retry."""
    try:
        vault = await vault_crud.get_or_none(db_session, dweller.vault_id, include_deleted=True)
        if vault is None:
            logger.error("Cannot notify map registration failure: vault=%s not found", dweller.vault_id)
            return

        await notification_service.create_and_send(
            db_session,
            user_id=vault.user_id,
            vault_id=vault.id,
            from_dweller_id=dweller.id,
            notification_type=NotificationType.MAP_REGISTRATION_FAILED,
            priority=NotificationPriority.HIGH,
            title="Map registration needs attention",
            message="A dweller's known locations could not be added to the map. Please try again later.",
        )
    except Exception:
        logger.exception(
            "Could not persist map registration failure notification: dweller=%s vault=%s",
            dweller.id,
            dweller.vault_id,
        )
