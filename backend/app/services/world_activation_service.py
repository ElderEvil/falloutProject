"""Service: reviewed lifecycle for one shared active world and stored candidates.

Generation stores a candidate snapshot; nothing activates it. An operator previews
the structured compatibility diff against the current active world and then
explicitly activates the candidate. Activation is atomic, progress-preserving
(it never deletes users, vaults, discoveries, explorations, or locations), and
refuses to run while an affected expedition is in progress.

Coordinate reconciliation: the active snapshot is the placement authority. Its
slots are read back by the home-marker and dispatch-origin consumers, so moving a
vault's approved placement updates one source and every consumer agrees.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from sqlalchemy.exc import IntegrityError

from app.crud import exploration as exploration_crud
from app.crud.vault_slot import vault_slot as vault_slot_crud
from app.crud.world_location import world_location as wl_crud
from app.crud.world_snapshot import world_snapshot as snapshot_crud
from app.models.world_snapshot import WorldSnapshot
from app.services.world_generation_service import WORLD_ID
from app.utils import world_terrain
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException
from app.utils.vault_slots import slot_coords

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

SlotChange = Literal["added", "removed", "moved", "unchanged"]


@dataclass(frozen=True)
class TerrainDelta:
    """How many terrain tiles the candidate changes, by new tile kind."""

    changed_tiles: int
    total_tiles: int
    changed_by_kind: dict[str, int]


@dataclass(frozen=True)
class SlotDelta:
    """One slot index's placement difference between active and candidate."""

    slot_index: int
    active_coord: tuple[float, float] | None
    candidate_coord: tuple[float, float] | None
    change: SlotChange


@dataclass(frozen=True)
class SlotLandSafety:
    """Land safety of an occupied slot under the candidate terrain."""

    slot_index: int
    live_coord: tuple[float, float]
    candidate_coord: tuple[float, float] | None
    live_on_water: bool
    candidate_on_water: bool


@dataclass(frozen=True)
class HomeMarkerMismatch:
    """A vault whose stored home marker disagrees with its dispatch origin."""

    vault_id: UUID4
    vault_number: int
    slot_index: int
    home_coord: tuple[float, float] | None
    origin_coord: tuple[float, float]


@dataclass(frozen=True)
class DispatchOriginMismatch:
    """A vault whose dispatch origin would move on activation."""

    vault_id: UUID4
    vault_number: int
    slot_index: int
    origin_coord: tuple[float, float]
    candidate_coord: tuple[float, float]


@dataclass(frozen=True)
class AffectedVault:
    """A vault whose approved placement moves from the old origin to the candidate."""

    vault_id: UUID4
    vault_number: int
    slot_index: int
    current_coord: tuple[float, float]
    candidate_coord: tuple[float, float]
    reason: str


@dataclass(frozen=True)
class AffectedExpedition:
    """An in-progress run belonging to a vault whose placement would move."""

    exploration_id: UUID4
    vault_id: UUID4
    status: str


@dataclass(frozen=True)
class ActivationPreview:
    """Read-only, structured comparison of a candidate against the active world."""

    world_id: str
    active_version: int | None
    candidate_version: int
    candidate_fingerprint: str
    candidate_checksum: str
    terrain: TerrainDelta
    slot_deltas: list[SlotDelta]
    land_safety: list[SlotLandSafety]
    home_marker_mismatches: list[HomeMarkerMismatch]
    dispatch_origin_mismatches: list[DispatchOriginMismatch]
    affected_vaults: list[AffectedVault]
    affected_expeditions: list[AffectedExpedition]
    conflicts: list[str]
    warnings: list[str]
    activatable: bool


@dataclass(frozen=True)
class ActivationResult:
    """Outcome of a committed activation."""

    world_id: str
    active_version: int
    previous_version: int | None
    relocated_vaults: list[AffectedVault]
    activated_at: datetime


def _slot_map(snapshot: WorldSnapshot | None) -> dict[int, tuple[float, float]]:
    """Slot index -> registry coordinate for a snapshot's stored slots."""
    if snapshot is None:
        return {}
    slots: dict[int, tuple[float, float]] = {}
    for slot in snapshot.slots:
        index = slot.get("slot_index")
        coord_x = slot.get("coord_x")
        coord_y = slot.get("coord_y")
        if index is None or coord_x is None or coord_y is None:
            continue
        slots[int(index)] = (float(coord_x), float(coord_y))
    return slots


def _terrain_delta(active: WorldSnapshot | None, candidate: WorldSnapshot) -> TerrainDelta:
    """Tiles the candidate reclassifies, counted by the candidate's tile kind."""
    candidate_terrain = list(candidate.terrain)
    total = len(candidate_terrain)
    changed_by_kind: dict[str, int] = {}

    def count(kind: str) -> None:
        changed_by_kind[kind] = changed_by_kind.get(kind, 0) + 1

    if active is None:
        for kind in candidate_terrain:
            count(kind)
        return TerrainDelta(changed_tiles=total, total_tiles=total, changed_by_kind=changed_by_kind)

    active_terrain = list(active.terrain)
    for index, kind in enumerate(candidate_terrain):
        if index >= len(active_terrain) or active_terrain[index] != kind:
            count(kind)
    return TerrainDelta(
        changed_tiles=sum(changed_by_kind.values()),
        total_tiles=total,
        changed_by_kind=changed_by_kind,
    )


def _slot_deltas(
    active_slots: dict[int, tuple[float, float]], candidate_slots: dict[int, tuple[float, float]]
) -> list[SlotDelta]:
    """Added/removed/moved/unchanged slot indices across active and candidate."""
    deltas: list[SlotDelta] = []
    for index in sorted(set(active_slots) | set(candidate_slots)):
        before = active_slots.get(index)
        after = candidate_slots.get(index)
        if before is None:
            change: SlotChange = "added"
        elif after is None:
            change = "removed"
        elif before != after:
            change = "moved"
        else:
            change = "unchanged"
        deltas.append(SlotDelta(slot_index=index, active_coord=before, candidate_coord=after, change=change))
    return deltas


class WorldActivationService:
    """Preview and activate a stored candidate world for one shared world id."""

    async def preview(
        self, db_session: AsyncSession, *, candidate_version: int, world_id: str = WORLD_ID
    ) -> ActivationPreview:
        """Read-only structured diff of a candidate against the active world."""
        candidate = await self._require_version(db_session, world_id=world_id, version=candidate_version)
        active = await snapshot_crud.get_active(db_session, world_id=world_id)
        active_slots = _slot_map(active)
        candidate_slots = _slot_map(candidate)

        vaults = await vault_slot_crud.list_markers(db_session)
        home_markers = await wl_crud.get_home_markers(db_session, [number for _, _, number, _ in vaults])

        land_safety: list[SlotLandSafety] = []
        home_mismatches: list[HomeMarkerMismatch] = []
        origin_mismatches: list[DispatchOriginMismatch] = []
        affected_vaults: list[AffectedVault] = []
        conflicts: list[str] = []
        warnings: list[str] = []

        for slot_index, vault_id, vault_number, _user_id in vaults:
            live_coord = active_slots.get(slot_index) or slot_coords(slot_index)
            candidate_coord = candidate_slots.get(slot_index)
            live_on_water = world_terrain.is_blocked(candidate, live_coord[0], live_coord[1])
            candidate_on_water = (
                world_terrain.is_blocked(candidate, candidate_coord[0], candidate_coord[1])
                if candidate_coord is not None
                else False
            )
            land_safety.append(
                SlotLandSafety(
                    slot_index=slot_index,
                    live_coord=live_coord,
                    candidate_coord=candidate_coord,
                    live_on_water=live_on_water,
                    candidate_on_water=candidate_on_water,
                )
            )

            marker = home_markers.get(vault_number)
            home_coord = (marker.coord_x, marker.coord_y) if marker is not None else None
            if home_coord is not None and home_coord != live_coord:
                home_mismatches.append(
                    HomeMarkerMismatch(
                        vault_id=vault_id,
                        vault_number=vault_number,
                        slot_index=slot_index,
                        home_coord=home_coord,
                        origin_coord=live_coord,
                    )
                )

            if candidate_coord is None:
                conflicts.append(f"slot {slot_index} (vault {vault_number}) is absent from the candidate")
                continue

            if candidate_coord != live_coord:
                origin_mismatches.append(
                    DispatchOriginMismatch(
                        vault_id=vault_id,
                        vault_number=vault_number,
                        slot_index=slot_index,
                        origin_coord=live_coord,
                        candidate_coord=candidate_coord,
                    )
                )
                reason = "home marker on water" if live_on_water else "approved placement moved"
                affected_vaults.append(
                    AffectedVault(
                        vault_id=vault_id,
                        vault_number=vault_number,
                        slot_index=slot_index,
                        current_coord=live_coord,
                        candidate_coord=candidate_coord,
                        reason=reason,
                    )
                )
                if live_on_water:
                    warnings.append(f"vault {vault_number} relocates off water at slot {slot_index}")
            if candidate_on_water:
                conflicts.append(f"candidate slot {slot_index} (vault {vault_number}) lands on water")

        affected_expeditions = await self._affected_expeditions(db_session, affected_vaults)
        blocking = list(conflicts)
        if affected_expeditions:
            blocking.append(f"{len(affected_expeditions)} in-progress expedition(s) belong to affected vaults")

        return ActivationPreview(
            world_id=world_id,
            active_version=active.generator_version if active is not None else None,
            candidate_version=candidate.generator_version,
            candidate_fingerprint=candidate.recipe_fingerprint,
            candidate_checksum=candidate.snapshot_checksum,
            terrain=_terrain_delta(active, candidate),
            slot_deltas=_slot_deltas(active_slots, candidate_slots),
            land_safety=land_safety,
            home_marker_mismatches=home_mismatches,
            dispatch_origin_mismatches=origin_mismatches,
            affected_vaults=affected_vaults,
            affected_expeditions=affected_expeditions,
            conflicts=conflicts,
            warnings=warnings,
            activatable=not blocking,
        )

    async def activate(
        self,
        db_session: AsyncSession,
        *,
        candidate_version: int,
        expected_active_version: int | None,
        confirm: bool = False,
        world_id: str = WORLD_ID,
    ) -> ActivationResult:
        """Atomically activate an exact candidate after rechecking compatibility.

        ``expected_active_version`` guards against stale/concurrent activations: a
        mismatch (including a missing expected active world) is a conflict, so a
        preview built against an older active world cannot silently apply.
        """
        if not confirm:
            raise ValidationException("Explicit confirmation is required to activate a world.")

        candidate = await self._require_version(db_session, world_id=world_id, version=candidate_version)
        active = await snapshot_crud.get_active(db_session, world_id=world_id)
        active_version = active.generator_version if active is not None else None

        if candidate.is_active:
            raise ResourceConflictException(f"World snapshot v{candidate_version} is already active.")
        if expected_active_version != active_version:
            raise ResourceConflictException(
                f"Active world changed (expected v{expected_active_version}, found v{active_version}); "
                "re-open the preview and confirm again."
            )

        preview = await self.preview(db_session, candidate_version=candidate_version, world_id=world_id)
        if not preview.activatable:
            raise ResourceConflictException("Activation blocked: " + "; ".join(preview.conflicts))

        now = datetime.utcnow()
        try:
            if active is not None:
                await snapshot_crud.deactivate_active(db_session, world_id=world_id)
            for affected in preview.affected_vaults:
                await wl_crud.move_home_marker(
                    db_session,
                    vault_number=affected.vault_number,
                    coord_x=affected.candidate_coord[0],
                    coord_y=affected.candidate_coord[1],
                )
            candidate.is_active = True
            candidate.activated_at = now
            db_session.add(candidate)
            await db_session.commit()
        except IntegrityError as exc:
            await db_session.rollback()
            raise ResourceConflictException("Another activation committed first; reload and retry.") from exc

        await db_session.refresh(candidate)
        logger.info(
            "Activated world %s v%s (previous v%s, relocated %s vaults)",
            world_id,
            candidate_version,
            active_version,
            len(preview.affected_vaults),
        )
        return ActivationResult(
            world_id=world_id,
            active_version=candidate_version,
            previous_version=active_version,
            relocated_vaults=preview.affected_vaults,
            activated_at=now,
        )

    async def _affected_expeditions(
        self, db_session: AsyncSession, affected_vaults: Sequence[AffectedVault]
    ) -> list[AffectedExpedition]:
        """In-progress runs whose vault placement would move on activation."""
        moved_vault_ids = {affected.vault_id for affected in affected_vaults}
        if not moved_vault_ids:
            return []
        active_runs = await exploration_crud.get_all_active(db_session)
        return [
            AffectedExpedition(
                exploration_id=run.id,
                vault_id=run.vault_id,
                status=run.status.value,
            )
            for run in active_runs
            if run.vault_id in moved_vault_ids
        ]

    async def _require_version(self, db_session: AsyncSession, *, world_id: str, version: int) -> WorldSnapshot:
        snapshot = await snapshot_crud.get_version(db_session, world_id=world_id, generator_version=version)
        if snapshot is None:
            raise ResourceNotFoundException(WorldSnapshot, identifier=str(version), identifier_type="generator_version")
        return snapshot


world_activation_service = WorldActivationService()
