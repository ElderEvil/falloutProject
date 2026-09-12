"""Retroactive bio-place backfill service.

Extracts origin/visited place names from existing dweller bios and registers
them on the world map. This lives in its own service so ``MapService`` stays
focused on runtime registration and map assembly.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.crud.dweller import dweller as dweller_crud
from app.services.map_service import map_service
from app.services.place_seed_service import get_origin_places, get_visited_places

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


def _build_origin_regex(places: list[str]) -> re.Pattern[str]:
    """Build a compiled regex that matches any known origin place (case-insensitive, word-boundary)."""
    patterns = [r"\b" + re.escape(place) + r"\b" for place in places]
    return re.compile("|".join(patterns), re.IGNORECASE)


def _build_visited_regex(places: list[str]) -> re.Pattern[str]:
    """Build a compiled regex that matches any known visited place (case-insensitive, word-boundary)."""
    patterns = [r"\b" + re.escape(place.strip()) + r"\b" for place in places]
    return re.compile("|".join(patterns), re.IGNORECASE)


_ORIGIN_RE = _build_origin_regex(get_origin_places())
_VISITED_RE = _build_visited_regex(get_visited_places())


def extract_places_from_bio(bio: str | None) -> tuple[str | None, list[str]]:
    """Scan *bio* for known origin and visited place names.

    Returns ``(origin_place, visited_places)``:
    - *origin_place*: the first matched origin place (preserving original casing
      from the known origin list), or ``None``.
    - *visited_places*: deduplicated list of visited place matches (preserving
      the trimmed canonical form from the known visited list), excluding any
      place that was already picked as the origin.
    """
    if not bio:
        return None, []

    origin_place: str | None = None
    origin_match = _ORIGIN_RE.search(bio)
    if origin_match:
        matched_text = origin_match.group(0)
        for place in get_origin_places():
            if place.lower() == matched_text.lower():
                origin_place = place
                break

    visited_places: list[str] = []
    seen_normalized: set[str] = set()
    if origin_place:
        seen_normalized.add(origin_place.lower())

    for match in _VISITED_RE.finditer(bio):
        matched_text = match.group(0)
        normalized = matched_text.lower()
        if normalized in seen_normalized:
            continue
        for place in get_visited_places():
            if place.strip().lower() == normalized:
                visited_places.append(place.strip())
                seen_normalized.add(normalized)
                break

    return origin_place, visited_places


class BioPlaceBackfillService:
    """Backfill bio-origin/visited places for existing vaults."""

    async def backfill_bio_places_for_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        max_dwellers: int | None = None,
    ) -> int:
        """Register bio places for dwellers in *vault_id* that have no map links yet.

        Dwellers are filtered to those with a non-empty bio and zero existing
        ``DwellerLocation`` rows. Each dweller is committed independently so a
        single registration failure (after the internal retry) cannot roll back
        earlier successful registrations in the same vault.
        """
        candidates = await self._get_dwellers_missing_locations(db_session, vault_id, max_dwellers)
        processed = 0
        for dweller in candidates:
            origin, visited = extract_places_from_bio(dweller.bio)
            if not origin and not visited:
                continue

            registered = await map_service.register_bio_places(
                db_session,
                dweller,
                origin_place=origin or "",
                visited_places=visited,
            )
            if not registered:
                continue

            try:
                await db_session.commit()
                processed += 1
                logger.info(
                    "Backfilled bio places for dweller %s in vault %s: origin=%s visited=%s",
                    dweller.id,
                    vault_id,
                    origin,
                    visited,
                )
            except Exception:  # broad by design: worker-loop isolation; logged+rolled back so backfill continues
                logger.exception(
                    "Failed to commit bio place backfill for dweller %s in vault %s",
                    dweller.id,
                    vault_id,
                )
                await db_session.rollback()

        return processed

    async def backfill_bio_places_for_active_vaults(
        self,
        db_session: AsyncSession,
        *,
        max_dwellers_per_vault: int | None = None,
        max_vaults: int | None = None,
    ) -> dict[UUID4, int]:
        """Backfill bio places across all active (non-deleted) vaults.

        Returns a mapping of ``vault_id`` → number of dwellers processed.
        Vaults are ordered by creation date for deterministic runs.
        """
        from app.crud.vault import vault as vault_crud

        vaults = await vault_crud.get_active_ordered(db_session, max_vaults)

        counts: dict[UUID4, int] = {}
        for vault in vaults:
            processed = await self.backfill_bio_places_for_vault(
                db_session,
                vault.id,
                max_dwellers=max_dwellers_per_vault,
            )
            counts[vault.id] = processed

        return counts

    async def _get_dwellers_missing_locations(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        max_dwellers: int | None,
    ) -> Sequence[Dweller]:
        """Return dwellers with a bio but no ``DwellerLocation`` links."""
        return await dweller_crud.get_bio_without_locations(db_session, vault_id, max_dwellers)


# Module-level singleton — matches the convention used by other services.
bio_place_backfill_service = BioPlaceBackfillService()
