"""CRUD for the canonical world-place registry and dweller-location links."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum, PlaceKindEnum
from app.models.dweller import Dweller
from app.models.world_location import DwellerLocation, VaultLocationState, WorldLocation
from app.utils.places import collision_nudge, normalize_place_name, schematic_coords

if TYPE_CHECKING:
    from uuid import UUID

    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.vault import Vault

logger = logging.getLogger(__name__)


class CRUDWorldLocation:
    """Race-safe CRUD over ``WorldLocation`` / ``VaultLocationState`` / ``DwellerLocation``."""

    # -- WorldLocation registry ----------------------------------------------------

    async def get_registry(self, db_session: AsyncSession, location_id: UUID4) -> WorldLocation | None:
        """Return a canonical registry row by id, or None."""
        result = await db_session.execute(select(WorldLocation).where(WorldLocation.id == location_id))
        return result.scalar_one_or_none()

    async def get_registry_by_normalized(self, db_session: AsyncSession, normalized_name: str) -> WorldLocation | None:
        """Find a canonical registry row by its normalized merge key, or None."""
        result = await db_session.execute(select(WorldLocation).where(WorldLocation.normalized_name == normalized_name))
        return result.scalar_one_or_none()

    async def get_all_coords(self, db_session: AsyncSession) -> set[tuple[float, float]]:
        """Every registry coordinate pair, for collision nudging."""
        result = await db_session.execute(select(WorldLocation.coord_x, WorldLocation.coord_y))
        return {(x, y) for x, y in result.all()}

    async def get_or_create_location(
        self,
        db_session: AsyncSession,
        name: str,
        *,
        description: str | None = None,
        commit: bool = True,
    ) -> WorldLocation:
        """Get or create a canonical PLACE row, merging on ``normalized_name``.

        Normalises the name, derives deterministic schematic coordinates, and
        nudges against the GLOBAL set of occupied registry coordinates.  On
        IntegrityError (concurrent insert of the same name) we roll back and
        re-select the existing row; there is no coordinate unique constraint,
        so no retry loop is needed. When ``commit`` is false, inserts are
        flushed and remain part of the caller's outer transaction.
        """
        normalized = normalize_place_name(name)

        # Fast path: already exists
        existing = await self.get_registry_by_normalized(db_session, normalized)
        if existing is not None:
            return existing

        base_x, base_y = schematic_coords(normalized)
        occupied_result = await db_session.execute(select(WorldLocation.coord_x, WorldLocation.coord_y))
        occupied: set[tuple[float, float]] = {(rx, ry) for rx, ry in occupied_result.all()}
        coord_x, coord_y = collision_nudge((base_x, base_y), occupied)

        obj = WorldLocation(
            name=name[:64],
            normalized_name=normalized,
            kind=PlaceKindEnum.PLACE,
            coord_x=coord_x,
            coord_y=coord_y,
            description=description,
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
            existing = await self.get_registry_by_normalized(db_session, normalized)
            if existing is not None:
                return existing
            raise
        else:
            await db_session.refresh(obj)
            return obj

    async def get_or_create_home_marker(
        self, db_session: AsyncSession, vault: Vault, *, commit: bool = True
    ) -> WorldLocation:
        """Idempotent home-vault registry row pinned at exactly (50.0, 50.0).

        Does NOT nudge coordinates — every home marker shares the centre.
        """
        vault_name = f"Vault {vault.number:03}"
        normalized = normalize_place_name(vault_name)

        # Fast path — already exists
        existing = await self.get_registry_by_normalized(db_session, normalized)
        if existing is not None:
            return existing

        obj = WorldLocation(
            name=vault_name,
            normalized_name=normalized,
            kind=PlaceKindEnum.VAULT,
            vault_number=vault.number,
            coord_x=50.0,
            coord_y=50.0,
        )
        if not commit:
            db_session.add(obj)
            await db_session.flush()
            return obj

        try:
            db_session.add(obj)
            await db_session.commit()
        except IntegrityError:
            await db_session.rollback()
            existing = await self.get_registry_by_normalized(db_session, normalized)
            if existing is not None:
                return existing
            raise
        else:
            await db_session.refresh(obj)
            return obj

    async def get_seeded_vaults(self, db_session: AsyncSession) -> list[WorldLocation]:
        """NPC vault signals seeded into the registry, in seed order."""
        result = await db_session.execute(
            select(WorldLocation)
            .where(WorldLocation.kind == PlaceKindEnum.VAULT, WorldLocation.source == "seed")
            .order_by(WorldLocation.normalized_name)
        )
        return list(result.scalars().all())

    # -- VaultLocationState --------------------------------------------------------

    async def get_state(
        self, db_session: AsyncSession, vault_id: UUID4, location_id: UUID4
    ) -> VaultLocationState | None:
        """A vault's fog entry over a location, or None."""
        result = await db_session.execute(
            select(VaultLocationState).where(
                VaultLocationState.vault_id == vault_id,
                VaultLocationState.location_id == location_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_state_with_location(
        self, db_session: AsyncSession, vault_id: UUID4, location_id: UUID4
    ) -> tuple[WorldLocation, VaultLocationState] | None:
        """The registry row joined with a vault's state over it, or None."""
        result = await db_session.execute(
            select(WorldLocation, VaultLocationState)
            .join(VaultLocationState, VaultLocationState.location_id == WorldLocation.id)
            .where(
                VaultLocationState.vault_id == vault_id,
                VaultLocationState.location_id == location_id,
            )
        )
        row = result.first()
        return (row[0], row[1]) if row else None

    async def get_states_by_vault(
        self, db_session: AsyncSession, vault_id: UUID4
    ) -> list[tuple[WorldLocation, VaultLocationState]]:
        """Every registry row paired with this vault's state over it."""
        result = await db_session.execute(
            select(WorldLocation, VaultLocationState)
            .join(VaultLocationState, VaultLocationState.location_id == WorldLocation.id)
            .where(VaultLocationState.vault_id == vault_id)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def get_discovery_states(
        self, db_session: AsyncSession, vault_id: UUID4
    ) -> list[tuple[WorldLocation, VaultLocationState]]:
        """Discovery states with a linked exploration, for backfill passes."""
        result = await db_session.execute(
            select(WorldLocation, VaultLocationState)
            .join(VaultLocationState, VaultLocationState.location_id == WorldLocation.id)
            .where(
                VaultLocationState.vault_id == vault_id,
                VaultLocationState.type == LocationTypeEnum.DISCOVERY,
                VaultLocationState.exploration_id.is_not(None),
            )
        )
        return [(row[0], row[1]) for row in result.all()]

    async def get_or_create_state(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        location_id: UUID4,
        type: LocationTypeEnum,
        *,
        description: str | None = None,
        exploration_id: UUID4 | None = None,
        commit: bool = True,
    ) -> VaultLocationState:
        """Get or create a vault's fog entry; ``type`` is first-write-wins.

        An existing state is returned unchanged (matching the old per-vault
        ``get_or_create`` semantics). On IntegrityError (concurrent insert) we
        roll back and re-select. When ``commit`` is false, inserts are flushed
        and remain part of the caller's outer transaction.
        """
        # Fast path: already exists
        existing = await self.get_state(db_session, vault_id, location_id)
        if existing is not None:
            return existing

        obj = VaultLocationState(
            vault_id=vault_id,
            location_id=location_id,
            type=type,
            description=description,
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
            await db_session.rollback()
            existing = await self.get_state(db_session, vault_id, location_id)
            if existing is not None:
                return existing
            raise
        else:
            await db_session.refresh(obj)
            return obj

    # -- DwellerLocation helpers ---------------------------------------------------

    async def get_dweller_link(
        self,
        db_session: AsyncSession,
        dweller_id: UUID4,
        location_id: UUID4,
        relation: DwellerLocationRelationEnum,
    ) -> DwellerLocation | None:
        """An existing dweller-location link of the given relation, or None."""
        stmt = select(DwellerLocation).where(
            DwellerLocation.dweller_id == dweller_id,
            DwellerLocation.location_id == location_id,
            DwellerLocation.relation == relation,
        )
        result = await db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_visited_counts(self, db_session: AsyncSession, dweller_ids: list[UUID4]) -> dict[UUID4, int]:
        """Count VISITED locations per dweller in one grouped query."""
        if not dweller_ids:
            return {}
        query = (
            select(DwellerLocation.dweller_id, func.count())
            .where(col(DwellerLocation.dweller_id).in_(dweller_ids))
            .where(DwellerLocation.relation == DwellerLocationRelationEnum.VISITED)
            .group_by(DwellerLocation.dweller_id)
        )
        result = await db_session.execute(query)
        return {row[0]: row[1] for row in result.all()}

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
        stmt = (
            sa_update(DwellerLocation)
            .where(
                col(DwellerLocation.dweller_id) == dweller_id,
                col(DwellerLocation.is_unlocked).is_(False),
            )
            .values(is_unlocked=True)
            .returning(col(DwellerLocation.location_id))
        )
        location_ids = list((await db_session.execute(stmt)).scalars())
        if not location_ids:
            return []

        names_result = await db_session.execute(
            select(WorldLocation.id, WorldLocation.name).where(col(WorldLocation.id).in_(location_ids))
        )
        location_names = {row.id: row.name for row in names_result.all()}
        await db_session.flush()
        return [(location_id, location_names[location_id]) for location_id in location_ids]


# Module-level singleton — matches the convention used by other crud modules.
world_location = CRUDWorldLocation()
