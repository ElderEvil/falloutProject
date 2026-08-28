"""Service for computing a dweller's family lineage."""

import logging
from collections.abc import Mapping, Sequence

from pydantic import UUID4
from sqlalchemy import or_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import dweller as dweller_crud
from app.models.dweller import Dweller
from app.models.relationship import Relationship
from app.schemas.common import PARTNER_LINKED_STAGES, RelationshipTypeEnum
from app.schemas.dweller import LineageMember, LineageResponse

logger = logging.getLogger(__name__)


class LineageService:
    """Computes family relationships (parents, children, siblings, partners) and generation depth."""

    @staticmethod
    def _to_members(
        dwellers: Sequence[Dweller],
        generation: int,
        partner_context: Mapping[UUID4, tuple[RelationshipTypeEnum, int]] | None = None,
    ) -> list[LineageMember]:
        """Map dwellers to LineageMember records at the given generation.

        Args:
            dwellers: Dwellers to map
            generation: Generation number for the members
            partner_context: Optional per-partner relationship stage/affinity (only for partners)

        Returns:
            List of LineageMember records
        """
        context = partner_context or {}
        return [
            LineageMember(
                id=d.id,
                first_name=d.first_name,
                last_name=d.last_name,
                generation=generation,
                is_dead=d.is_dead,
                age_group=d.age_group,
                relationship_type=context[d.id][0] if d.id in context else None,
                affinity=context[d.id][1] if d.id in context else None,
            )
            for d in dwellers
        ]

    @staticmethod
    async def _find_children(db_session: AsyncSession, dweller_id: UUID4, vault_id: UUID4) -> list[Dweller]:
        """Find dwellers in the same vault whose parent is this dweller."""
        query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(~Dweller.is_deleted)
            .where(or_(Dweller.parent_1_id == dweller_id, Dweller.parent_2_id == dweller_id))
        )
        result = await db_session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def _find_siblings(
        db_session: AsyncSession,
        dweller: Dweller,
        parents: list[Dweller],
        vault_id: UUID4,
    ) -> list[Dweller]:
        """Find other children of the same parents in the same vault."""
        parent_ids = [p.id for p in parents]
        if not parent_ids:
            return []
        query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(~Dweller.is_deleted)
            .where(Dweller.id != dweller.id)
            .where(
                or_(
                    Dweller.parent_1_id.in_(parent_ids),
                    Dweller.parent_2_id.in_(parent_ids),
                )
            )
        )
        result = await db_session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def _find_partners(
        db_session: AsyncSession, dweller_id: UUID4, vault_id: UUID4
    ) -> tuple[list[Dweller], dict[UUID4, tuple[RelationshipTypeEnum, int]]]:
        """Find the dweller's partner(s): reciprocal partner_id plus MARRIED/PARTNER relationships.

        Returns:
            Tuple of partner dwellers and a mapping of partner_id to (relationship_type, affinity).
        """
        partner_ids = set()
        context: dict[UUID4, tuple[RelationshipTypeEnum, int]] = {}

        dweller = await dweller_crud.get(db_session, dweller_id)
        if dweller and dweller.partner_id:
            partner_ids.add(dweller.partner_id)

        query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(~Dweller.is_deleted)
            .where(Dweller.partner_id == dweller_id)
        )
        result = await db_session.execute(query)
        partner_ids.update(partner.id for partner in result.scalars().all())

        rel_query = (
            select(Relationship)
            .where(Relationship.relationship_type.in_(PARTNER_LINKED_STAGES))
            .where((Relationship.dweller_1_id == dweller_id) | (Relationship.dweller_2_id == dweller_id))
        )
        result = await db_session.execute(rel_query)
        for relationship in result.scalars().all():
            other_id = (
                relationship.dweller_2_id if relationship.dweller_1_id == dweller_id else relationship.dweller_1_id
            )
            partner_ids.add(other_id)
            context[other_id] = (relationship.relationship_type, relationship.affinity)

        partners: list[Dweller] = []
        for partner_id in partner_ids:
            partner = await dweller_crud.get(db_session, partner_id)
            if partner and partner.vault_id == vault_id:
                partners.append(partner)
        return partners, context

    @staticmethod
    async def _compute_generation(db_session: AsyncSession, dweller_id: UUID4, vault_id: UUID4) -> int:
        """Walk parents upward to compute the generation number (0 for orphans).

        Only live, same-vault parents are followed, and a candidate is validated
        before being added to the next frontier so cross-vault links, soft-deleted
        dwellers, and cycles never add phantom generation levels.
        """
        generation = 0
        seen: set[UUID4] = set()
        frontier = [dweller_id]

        while frontier:
            next_frontier: list[UUID4] = []
            for current_id in frontier:
                if current_id in seen:
                    continue
                seen.add(current_id)
                # include_deleted so a deleted ancestor is filtered here (vault+is_deleted), not raised as not-found
                parent = await dweller_crud.get(db_session, current_id, include_deleted=True)
                if not parent or parent.vault_id != vault_id or parent.is_deleted:
                    continue
                for candidate_id in (parent.parent_1_id, parent.parent_2_id):
                    if candidate_id is None or candidate_id in seen:
                        continue
                    candidate = await dweller_crud.get(db_session, candidate_id, include_deleted=True)
                    if candidate and candidate.vault_id == vault_id and not candidate.is_deleted:
                        next_frontier.append(candidate_id)
            if next_frontier:
                generation += 1
            frontier = next_frontier

        return generation

    @classmethod
    async def get_lineage(cls, db_session: AsyncSession, dweller_id: UUID4) -> LineageResponse:
        """Compute the full lineage for a dweller.

        Raises:
            ResourceNotFoundException: If the dweller does not exist.
        """
        dweller = await dweller_crud.get(db_session, dweller_id)

        generation = await cls._compute_generation(db_session, dweller_id, dweller.vault_id)

        parent_ids = [p for p in (dweller.parent_1_id, dweller.parent_2_id) if p is not None]
        parents: list[Dweller] = []
        for parent_id in parent_ids:
            parent = await dweller_crud.get(db_session, parent_id, include_deleted=True)
            if parent and parent.vault_id == dweller.vault_id and not parent.is_deleted:
                parents.append(parent)

        children = await cls._find_children(db_session, dweller_id, dweller.vault_id)
        siblings = await cls._find_siblings(db_session, dweller, parents, dweller.vault_id)
        partners, partner_context = await cls._find_partners(db_session, dweller_id, dweller.vault_id)

        return LineageResponse(
            dweller_id=dweller_id,
            generation=generation,
            parents=cls._to_members(parents, generation - 1),
            children=cls._to_members(children, generation + 1),
            siblings=cls._to_members(siblings, generation),
            partners=cls._to_members(partners, generation, partner_context),
        )


lineage_service = LineageService()
