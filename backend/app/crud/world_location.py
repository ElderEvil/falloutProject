"""CRUD for the canonical world-place registry and dweller-location links."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum, PlaceKindEnum
from app.models.dweller import Dweller
from app.models.world_location import DwellerLocation, VaultLocationState, WorldLocation
from app.utils.place_groups import group_for_place_name
from app.utils.places import collision_nudge, normalize_place_name, schematic_coords

if TYPE_CHECKING:
    from datetime import datetime
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

    async def get_nearest_within(
        self, db_session: AsyncSession, coord_x: float, coord_y: float, radius: float
    ) -> WorldLocation | None:
        """The closest PLACE row within *radius* registry units, or None.

        Vault markers are excluded — a vault is not a discovery. A coordinate
        box narrows the candidates, then true distance decides, so the circle
        (not the box corner) is the boundary.
        """
        result = await db_session.execute(
            select(WorldLocation).where(
                WorldLocation.kind != PlaceKindEnum.VAULT,
                WorldLocation.coord_x >= coord_x - radius,
                WorldLocation.coord_x <= coord_x + radius,
                WorldLocation.coord_y >= coord_y - radius,
                WorldLocation.coord_y <= coord_y + radius,
            )
        )
        best: WorldLocation | None = None
        best_distance = radius
        for location in result.scalars().all():
            distance = math.dist((location.coord_x, location.coord_y), (coord_x, coord_y))
            if distance <= best_distance:
                best = location
                best_distance = distance
        return best

    async def count_journey_places(self, db_session: AsyncSession, exploration_id: UUID4) -> int:
        """How many spatial rows this journey already placed, for stable per-discovery identity."""
        result = await db_session.execute(
            select(func.count()).where(col(WorldLocation.normalized_name).like(f"{exploration_id}:%"))
        )
        return result.scalar_one()

    async def get_or_create_location(
        self,
        db_session: AsyncSession,
        name: str,
        *,
        description: str | None = None,
        coords: tuple[float, float] | None = None,
        normalized_name: str | None = None,
        commit: bool = True,
    ) -> WorldLocation:
        """Get or create a canonical PLACE row, merging on ``normalized_name``.

        Without ``coords`` the name derives deterministic schematic coordinates,
        nudged against every occupied registry coordinate. With ``coords`` the
        caller's placement is authoritative and no nudge is applied (spatial
        discovery follows the explorer, not a name hash). Pass an explicit
        ``normalized_name`` to disambiguate a same-name row that must not be
        reused. On IntegrityError (concurrent insert of the same name) we roll
        back and re-select; there is no coordinate unique constraint, so no
        retry loop is needed. When ``commit`` is false, inserts are flushed
        into the caller's transaction.
        """
        normalized = normalized_name or normalize_place_name(name)

        # Fast path: already exists
        existing = await self.get_registry_by_normalized(db_session, normalized)
        if existing is not None:
            return existing

        if coords is not None:
            coord_x, coord_y = coords
        else:
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
            group_key=group_for_place_name(name),
        )
        if not commit:
            try:
                async with db_session.begin_nested():
                    db_session.add(obj)
                    await db_session.flush()
            except IntegrityError:
                existing = await self.get_registry_by_normalized(db_session, normalized)
                if existing is not None:
                    return existing
                raise
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

    async def _promote_to_home_marker(
        self,
        db_session: AsyncSession,
        existing: WorldLocation,
        vault: Vault,
        *,
        coord_x: float = 50.0,
        coord_y: float = 50.0,
        commit: bool = True,
    ) -> WorldLocation:
        """Upgrade a name-colliding row to the VAULT marker at the vault's placement."""
        if (
            existing.kind != PlaceKindEnum.VAULT
            or existing.vault_number != vault.number
            or (existing.coord_x, existing.coord_y) != (coord_x, coord_y)
        ):
            existing.kind = PlaceKindEnum.VAULT
            existing.vault_number = vault.number
            existing.coord_x = coord_x
            existing.coord_y = coord_y
            db_session.add(existing)
            if commit:
                await db_session.commit()
                await db_session.refresh(existing)
            else:
                await db_session.flush()
        return existing

    async def get_or_create_home_marker(
        self,
        db_session: AsyncSession,
        vault: Vault,
        *,
        coord_x: float = 50.0,
        coord_y: float = 50.0,
        commit: bool = True,
    ) -> WorldLocation:
        """Idempotent home-vault registry row at the vault's placement.

        Callers pass the vault's slot coordinates so the home marker sits where the
        vault was placed (defaults to the map centre when a vault has no slot).
        """
        vault_name = f"Vault {vault.number:03}"
        normalized = normalize_place_name(vault_name)

        # Fast path — already exists. A bio mention may have registered the same
        # name earlier as a schematic PLACE row; promote it to the VAULT marker.
        existing = await self.get_registry_by_normalized(db_session, normalized)
        if existing is not None:
            return await self._promote_to_home_marker(
                db_session, existing, vault, coord_x=coord_x, coord_y=coord_y, commit=commit
            )

        obj = WorldLocation(
            name=vault_name,
            normalized_name=normalized,
            kind=PlaceKindEnum.VAULT,
            vault_number=vault.number,
            coord_x=coord_x,
            coord_y=coord_y,
        )
        if not commit:
            try:
                async with db_session.begin_nested():
                    db_session.add(obj)
                    await db_session.flush()
            except IntegrityError:
                existing = await self.get_registry_by_normalized(db_session, normalized)
                if existing is not None:
                    return await self._promote_to_home_marker(
                        db_session, existing, vault, coord_x=coord_x, coord_y=coord_y, commit=False
                    )
                raise
            return obj

        try:
            db_session.add(obj)
            await db_session.commit()
        except IntegrityError:
            await db_session.rollback()
            existing = await self.get_registry_by_normalized(db_session, normalized)
            if existing is not None:
                return await self._promote_to_home_marker(
                    db_session, existing, vault, coord_x=coord_x, coord_y=coord_y, commit=True
                )
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

    async def is_location_unlocked(self, db_session: AsyncSession, vault_id: UUID4, location_id: UUID4) -> bool:
        """True when a dweller in the vault has unlocked this location.

        Mirrors the map's visibility rule: a place is known to the vault only once a
        dweller link marks it unlocked, so the registry row alone is not enough.
        """
        result = await db_session.execute(
            select(DwellerLocation.id)
            .join(Dweller, Dweller.id == DwellerLocation.dweller_id)
            .where(
                DwellerLocation.location_id == location_id,
                Dweller.vault_id == vault_id,
                DwellerLocation.is_unlocked == True,  # ruff: ignore[true-false-comparison]
            )
            .limit(1)
        )
        return result.first() is not None

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

    async def get_elapsed_reclears(
        self, db_session: AsyncSession, now: datetime
    ) -> list[tuple[WorldLocation, VaultLocationState]]:
        """States whose reclear window has elapsed, joined to their location.

        Rows are locked (FOR UPDATE, a no-op on SQLite) so overlapping sweeps
        serialize: the loser blocks until the winner commits, then reads the
        nulled window and skips instead of double-notifying. Eligibility is
        rechecked after the lock in case a dispatch set a new window meanwhile.
        """
        result = await db_session.execute(
            select(WorldLocation, VaultLocationState)
            .join(VaultLocationState, VaultLocationState.location_id == WorldLocation.id)
            .where(
                VaultLocationState.reclear_available_at.is_not(None),
                VaultLocationState.reclear_available_at <= now,
            )
            .with_for_update()
        )
        return [
            (row[0], row[1])
            for row in result.all()
            if row[1].reclear_available_at is not None and row[1].reclear_available_at <= now
        ]

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
            try:
                async with db_session.begin_nested():
                    db_session.add(obj)
                    await db_session.flush()
            except IntegrityError:
                existing = await self.get_state(db_session, vault_id, location_id)
                if existing is not None:
                    return existing
                raise
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

    async def ensure_home_state(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        location_id: UUID4,
        description: str | None = None,
    ) -> VaultLocationState:
        """Get or create the vault's HOME_VAULT fog entry, promoting any other type.

        ``get_or_create_state`` is first-write-wins, so a bio registration may
        already hold an ORIGIN entry on the home pair. The owning vault's home
        state must read HOME_VAULT, hence the promotion.
        """
        state = await self.get_or_create_state(
            db_session, vault_id, location_id, LocationTypeEnum.HOME_VAULT, description=description
        )
        if state.type != LocationTypeEnum.HOME_VAULT:
            state.type = LocationTypeEnum.HOME_VAULT
            db_session.add(state)
            await db_session.commit()
            await db_session.refresh(state)
        return state

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
        if not commit:
            try:
                async with db_session.begin_nested():
                    db_session.add(link)
                    await db_session.flush()
            except IntegrityError:
                result = await db_session.execute(stmt)
                existing = result.scalar_one_or_none()
                if existing is not None:
                    if is_unlocked and not existing.is_unlocked:
                        existing.is_unlocked = True
                        db_session.add(existing)
                    return existing
                raise
            return link
        db_session.add(link)
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

    async def get_dweller_refs(
        self, db_session: AsyncSession, vault_id: UUID4, location_ids: list[UUID4]
    ) -> dict[UUID4, list[dict]]:
        """Batch-load dweller references for a list of location ids.

        Only dwellers belonging to ``vault_id`` are returned: registry rows are
        shared globally, but each vault sees just its own dwellers. A single
        query — no N+1.
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
            .where(
                DwellerLocation.location_id.in_(location_ids),
                Dweller.vault_id == vault_id,
            )
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
