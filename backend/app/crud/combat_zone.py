"""CRUD for Combat Zone parties, matches, journal rows, and the shared POI.

Every write path in the service is expected to hold the party/match row it is
mutating; the ``*_for_update`` helpers make that explicit. Queries only — the
service owns lifecycle decisions and escrow arithmetic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.core.combat_zone import COMBAT_ZONE_NORMALIZED
from app.core.enums import CombatZoneMatchStatus, CombatZonePartyStatus
from app.models.combat_zone import CombatZoneEvent, CombatZoneMatch, CombatZoneParty
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.models.world_location import WorldLocation

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession


class CRUDCombatZone:
    """Row access for the Combat Zone domain."""

    # -- Party --------------------------------------------------------------------

    async def get_party_by_vault(self, db_session: AsyncSession, vault_id: UUID) -> CombatZoneParty | None:
        result = await db_session.execute(select(CombatZoneParty).where(CombatZoneParty.vault_id == vault_id))
        return result.scalar_one_or_none()

    async def get_party_by_vault_for_update(self, db_session: AsyncSession, vault_id: UUID) -> CombatZoneParty | None:
        result = await db_session.execute(
            select(CombatZoneParty)
            .where(CombatZoneParty.vault_id == vault_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_party_for_update(self, db_session: AsyncSession, party_id: UUID) -> CombatZoneParty | None:
        result = await db_session.execute(
            select(CombatZoneParty)
            .where(CombatZoneParty.id == party_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_dwellers_by_ids(self, db_session: AsyncSession, dweller_ids: Sequence[UUID]) -> Sequence[Dweller]:
        """Snapshot participants for match reads; includes deleted rows for history."""
        if not dweller_ids:
            return []
        result = await db_session.execute(
            select(Dweller)
            .where(Dweller.id.in_(dweller_ids))
            .options(selectinload(Dweller.weapon), selectinload(Dweller.outfit), selectinload(Dweller.pet))
        )
        return result.scalars().all()

    async def get_room(self, db_session: AsyncSession, room_id: UUID) -> Room | None:
        result = await db_session.execute(select(Room).where(Room.id == room_id))
        return result.scalar_one_or_none()

    async def get_parties(self, db_session: AsyncSession, party_ids: Sequence[UUID]) -> Sequence[CombatZoneParty]:
        if not party_ids:
            return []
        result = await db_session.execute(select(CombatZoneParty).where(CombatZoneParty.id.in_(party_ids)))
        return result.scalars().all()

    async def get_dweller_for_update(self, db_session: AsyncSession, dweller_id: UUID) -> Dweller | None:
        result = await db_session.execute(
            select(Dweller)
            .where(Dweller.id == dweller_id)
            .options(selectinload(Dweller.weapon), selectinload(Dweller.outfit), selectinload(Dweller.pet))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_queued(self, db_session: AsyncSession) -> Sequence[CombatZoneParty]:
        """Queued parties in arrival order (FIFO pairing).

        ``arrives_at`` is retained as the queue-entry timestamp after promotion,
        which is why ordering does not use the reused row's ``created_at``.
        """
        result = await db_session.execute(
            select(CombatZoneParty)
            .where(CombatZoneParty.status == CombatZonePartyStatus.QUEUED)
            .order_by(CombatZoneParty.arrives_at, CombatZoneParty.id)
        )
        return result.scalars().all()

    async def list_due_parties(
        self, db_session: AsyncSession, status: CombatZonePartyStatus, cutoff
    ) -> Sequence[CombatZoneParty]:
        """Parties in ``status`` whose travel ETA has passed."""
        result = await db_session.execute(
            select(CombatZoneParty)
            .where(
                CombatZoneParty.status == status,
                CombatZoneParty.arrives_at.is_not(None),
                CombatZoneParty.arrives_at <= cutoff,
            )
            .order_by(CombatZoneParty.arrives_at, CombatZoneParty.id)
        )
        return result.scalars().all()

    async def list_by_status(
        self, db_session: AsyncSession, status: CombatZonePartyStatus
    ) -> Sequence[CombatZoneParty]:
        result = await db_session.execute(select(CombatZoneParty).where(CombatZoneParty.status == status))
        return result.scalars().all()

    async def count_unfinished_parties(self, db_session: AsyncSession) -> int:
        result = await db_session.execute(
            select(func.count())
            .select_from(CombatZoneParty)
            .where(CombatZoneParty.status != CombatZonePartyStatus.HOME)
        )
        return result.scalar_one()

    async def list_parties_with_owners(
        self, db_session: AsyncSession, party_ids: Sequence[UUID]
    ) -> Sequence[tuple[CombatZoneParty, Dweller, Vault]]:
        """Party + dweller + vault rows for schema building (one query)."""
        if not party_ids:
            return []
        result = await db_session.execute(
            select(CombatZoneParty, Dweller, Vault)
            .join(Dweller, Dweller.id == CombatZoneParty.dweller_id)
            .join(Vault, Vault.id == CombatZoneParty.vault_id)
            .options(selectinload(Dweller.weapon), selectinload(Dweller.outfit), selectinload(Dweller.pet))
            .where(CombatZoneParty.id.in_(party_ids))
        )
        return result.all()

    async def list_queued_with_owners(
        self, db_session: AsyncSession
    ) -> Sequence[tuple[CombatZoneParty, Dweller, Vault]]:
        result = await db_session.execute(
            select(CombatZoneParty, Dweller, Vault)
            .join(Dweller, Dweller.id == CombatZoneParty.dweller_id)
            .join(Vault, Vault.id == CombatZoneParty.vault_id)
            .options(selectinload(Dweller.weapon), selectinload(Dweller.outfit), selectinload(Dweller.pet))
            .where(CombatZoneParty.status == CombatZonePartyStatus.QUEUED)
            .order_by(CombatZoneParty.arrives_at, CombatZoneParty.id)
        )
        return result.all()

    # -- Match --------------------------------------------------------------------

    async def get_match(self, db_session: AsyncSession, match_id: UUID) -> CombatZoneMatch | None:
        result = await db_session.execute(select(CombatZoneMatch).where(CombatZoneMatch.id == match_id))
        return result.scalar_one_or_none()

    async def get_match_for_update(self, db_session: AsyncSession, match_id: UUID) -> CombatZoneMatch | None:
        result = await db_session.execute(
            select(CombatZoneMatch)
            .where(CombatZoneMatch.id == match_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_active_matches(self, db_session: AsyncSession) -> Sequence[CombatZoneMatch]:
        result = await db_session.execute(
            select(CombatZoneMatch)
            .where(CombatZoneMatch.status == CombatZoneMatchStatus.ACTIVE)
            .order_by(CombatZoneMatch.started_at, CombatZoneMatch.id)
        )
        return result.scalars().all()

    async def list_history_for_vault(
        self, db_session: AsyncSession, vault_id: UUID4, *, limit: int
    ) -> Sequence[CombatZoneMatch]:
        """Finished bouts involving this vault, newest first."""
        party_ids = select(CombatZoneParty.id).where(CombatZoneParty.vault_id == vault_id)
        result = await db_session.execute(
            select(CombatZoneMatch)
            .where(
                CombatZoneMatch.status == CombatZoneMatchStatus.FINISHED,
                (CombatZoneMatch.party_a_id.in_(party_ids)) | (CombatZoneMatch.party_b_id.in_(party_ids)),
            )
            .order_by(CombatZoneMatch.finished_at.desc(), CombatZoneMatch.id.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # -- Journal ------------------------------------------------------------------

    async def next_event_sequence(self, db_session: AsyncSession, match_id: UUID) -> int:
        result = await db_session.execute(
            select(func.max(CombatZoneEvent.sequence)).where(CombatZoneEvent.match_id == match_id)
        )
        return (result.scalar_one_or_none() or 0) + 1

    async def list_events(
        self, db_session: AsyncSession, match_id: UUID, after_seq: int | None = None
    ) -> Sequence[CombatZoneEvent]:
        query = select(CombatZoneEvent).where(CombatZoneEvent.match_id == match_id)
        if after_seq is not None:
            query = query.where(CombatZoneEvent.sequence > after_seq)
        result = await db_session.execute(query.order_by(CombatZoneEvent.sequence))
        return result.scalars().all()

    # -- Shared POI ---------------------------------------------------------------

    async def get_poi(self, db_session: AsyncSession) -> WorldLocation | None:
        result = await db_session.execute(
            select(WorldLocation).where(WorldLocation.normalized_name == COMBAT_ZONE_NORMALIZED)
        )
        return result.scalar_one_or_none()


combat_zone_crud = CRUDCombatZone()
