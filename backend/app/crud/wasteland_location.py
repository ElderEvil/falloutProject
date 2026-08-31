"""CRUD operations for WastelandLocation and DwellerLocation models."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.models.dweller import Dweller
from app.models.wasteland_location import DwellerLocation, DwellerLocationRelationEnum, WastelandLocation
from app.utils.places import collision_nudge, normalize_place_name, schematic_coords

if TYPE_CHECKING:
    from uuid import UUID

    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class CRUDWastelandLocation:
    """Race-safe CRUD for wasteland locations and dweller-location links."""

    # -- WastelandLocation queries -------------------------------------------------

    async def get_by_id(self, db_session: AsyncSession, location_id: UUID4) -> WastelandLocation | None:
        """Return a single location row by id, or None."""
        result = await db_session.execute(select(WastelandLocation).where(WastelandLocation.id == location_id))
        return result.scalar_one_or_none()

    async def get_by_vault(self, db_session: AsyncSession, vault_id: UUID4) -> list[WastelandLocation]:
        """List every non-VAULT location row scoped to this vault."""
        result = await db_session.execute(select(WastelandLocation).where(WastelandLocation.vault_id == vault_id))
        return list(result.scalars().all())

    async def get_by_normalized(
        self, db_session: AsyncSession, vault_id: UUID4, normalized_name: str
    ) -> WastelandLocation | None:
        """Find a location by vault + normalized name, or None."""
        result = await db_session.execute(
            select(WastelandLocation).where(
                WastelandLocation.vault_id == vault_id,
                WastelandLocation.normalized_name == normalized_name,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        name: str,
        type: str,
        description: str | None = None,
        exploration_id: UUID4 | None = None,
        commit: bool = True,
    ) -> WastelandLocation:
        """Get or create a location row with race-safe upsert.

        Normalises the name, derives deterministic schematic coordinates,
        nudges against occupied coords, then INSERTs.  On IntegrityError
        (concurrent insert) we roll back and re-SELECT the existing row —
        the exact documented pattern from ``CRUDUserProfile.create_for_user``.

        Distinguishes name conflicts (return existing row) from coordinate
        conflicts (re-derive fresh coords, bounded retry). When ``commit`` is
        false, inserts are flushed and remain part of the caller's outer
        transaction.
        """
        normalized = normalize_place_name(name)

        # Fast path: already exists
        existing = await self.get_by_normalized(db_session, vault_id, normalized)
        if existing is not None:
            return existing

        # Derive base coordinates
        base_x, base_y = schematic_coords(normalized)

        # Bounded retry loop — on coordinate conflict, re-derive fresh coords
        max_retries = 3
        for _attempt in range(max_retries):
            # Gather occupied coordinates for this vault
            occupied_result = await db_session.execute(
                select(WastelandLocation.coord_x, WastelandLocation.coord_y).where(
                    WastelandLocation.vault_id == vault_id
                )
            )
            occupied: set[tuple[float, float]] = {(rx, ry) for rx, ry in occupied_result.all()}

            coord_x, coord_y = collision_nudge((base_x, base_y), occupied)

            obj = WastelandLocation(
                name=name[:64],
                normalized_name=normalized,
                type=type,
                coord_x=coord_x,
                coord_y=coord_y,
                description=description,
                vault_id=vault_id,
                exploration_id=exploration_id,
            )
            if not commit:
                db_session.add(obj)
                await db_session.flush()
                return obj

            try:
                db_session.add(obj)
                await db_session.commit()
            except IntegrityError:
                # Race: another request already inserted this name
                await db_session.rollback()
                # Re-fetch the existing row
                existing = await self.get_by_normalized(db_session, vault_id, normalized)
                if existing is not None:
                    return existing
                # Otherwise: coordinate conflict → add collided coords and retry
                logger.debug(
                    "Coordinate conflict on (%s, %s) for '%s' (attempt %d/%d)",
                    coord_x,
                    coord_y,
                    normalized,
                    _attempt + 1,
                    max_retries,
                )
                # Fall through to next iteration — occupied set is rebuilt from DB
            else:
                await db_session.refresh(obj)
                return obj

        # Exhausted all retries
        raise IntegrityError(
            f"Could not insert location '{normalized}' after {max_retries} coordinate retries",
            orig=None,
            params=None,
        )

    # -- DwellerLocation helpers ---------------------------------------------------

    async def link_dweller(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        location_id: UUID4,
        relation: DwellerLocationRelationEnum,
        is_unlocked: bool = False,
        commit: bool = True,
    ) -> DwellerLocation:
        """Idempotent get-or-insert a dweller-location link.

        Uses the same IntegrityError-rollback-re-select pattern. When
        ``commit`` is False the insert is flushed and remains part of the
        caller's outer transaction.
        """
        # Fast path: already linked
        stmt = select(DwellerLocation).where(
            DwellerLocation.dweller_id == dweller_id,
            DwellerLocation.location_id == location_id,
            DwellerLocation.relation == relation,
        )
        result = await db_session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            if is_unlocked and not existing.is_unlocked:
                existing.is_unlocked = True
                db_session.add(existing)
                if commit:
                    await db_session.commit()
                    await db_session.refresh(existing)
            return existing

        link = DwellerLocation(
            dweller_id=dweller_id,
            location_id=location_id,
            relation=relation,
            is_unlocked=is_unlocked,
        )
        db_session.add(link)
        if not commit:
            await db_session.flush()
            return link
        try:
            await db_session.commit()
        except IntegrityError:
            await db_session.rollback()
            result = await db_session.execute(stmt)
            existing = result.scalar_one_or_none()
            if existing is not None:
                if is_unlocked and not existing.is_unlocked:
                    existing.is_unlocked = True
                    db_session.add(existing)
                    await db_session.commit()
                    await db_session.refresh(existing)
                return existing
            raise
        else:
            await db_session.refresh(link)
            return link

    async def get_dweller_refs(self, db_session: AsyncSession, location_ids: list[UUID4]) -> dict[UUID4, list[dict]]:
        """Batch-load dweller references for a list of location ids.

        Returns a dict mapping ``location_id`` → list of ``{dweller_id,
        first_name, last_name, relation}`` dicts.  A single query — no N+1.
        """
        if not location_ids:
            return {}

        stmt = (
            select(
                DwellerLocation.location_id,
                Dweller.id,
                Dweller.first_name,
                Dweller.last_name,
                DwellerLocation.relation,
                DwellerLocation.is_unlocked,
            )
            .join(Dweller, Dweller.id == DwellerLocation.dweller_id)
            .where(DwellerLocation.location_id.in_(location_ids))
        )
        result = await db_session.execute(stmt)
        rows = result.all()

        mapping: dict[UUID4, list[dict]] = {lid: [] for lid in location_ids}
        for row in rows:
            mapping[row.location_id].append(
                {
                    "dweller_id": row.id,
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "relation": row.relation,
                    "is_unlocked": row.is_unlocked,
                }
            )
        return mapping

    async def unlock_places_for_dweller(self, db_session: AsyncSession, *, dweller_id: UUID) -> list[tuple[UUID, str]]:
        """Unlock linked places and return the IDs and names newly revealed by this dweller."""
        names_result = await db_session.execute(
            select(WastelandLocation.id, WastelandLocation.name)
            .join(DwellerLocation, DwellerLocation.location_id == WastelandLocation.id)
            .where(
                DwellerLocation.dweller_id == dweller_id,
                DwellerLocation.is_unlocked.is_(False),
            )
        )
        unlocked_places = [(row.id, row.name) for row in names_result.all()]
        if not unlocked_places:
            return []

        stmt = (
            sa_update(DwellerLocation)
            .where(
                DwellerLocation.dweller_id == dweller_id,
                DwellerLocation.is_unlocked.is_(False),
            )
            .values(is_unlocked=True)
        )
        await db_session.execute(stmt)
        await db_session.commit()
        return unlocked_places


# Module-level singleton — matches the convention used by other crud modules.
wasteland_location = CRUDWastelandLocation()
