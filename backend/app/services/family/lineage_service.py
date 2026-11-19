"""Service for computing a dweller's family lineage."""

import logging
from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import RelationshipTypeEnum
from app.crud import dweller as dweller_crud
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.schemas.dweller import LineageMember, LineageResponse
from app.utils.exceptions import ensure_found

logger = logging.getLogger(__name__)


class LineageService:
    """Computes family relationships (parents, children, siblings, partners) and generation depth."""

    @staticmethod
    def _to_members(
        dwellers: Sequence[Dweller],
        generation: int,
        partner_context: Mapping[UUID, tuple[RelationshipTypeEnum, int]] | None = None,
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
    async def _find_children(db_session: AsyncSession, dweller_id: UUID, vault_id: UUID) -> list[Dweller]:
        """Find dwellers in the same vault whose parent is this dweller."""
        children = await dweller_crud.get_children_of(db_session, vault_id=vault_id, parent_ids=[dweller_id])
        return list(children)

    @staticmethod
    async def _find_siblings(
        db_session: AsyncSession,
        dweller: Dweller,
        parents: list[Dweller],
        vault_id: UUID,
    ) -> list[Dweller]:
        """Find other children of the same parents in the same vault."""
        parent_ids = [p.id for p in parents]
        if not parent_ids:
            return []
        siblings = await dweller_crud.get_children_of(
            db_session, vault_id=vault_id, parent_ids=parent_ids, exclude_id=dweller.id
        )
        return list(siblings)

    @staticmethod
    async def _find_partners(
        db_session: AsyncSession, dweller: Dweller, vault_id: UUID
    ) -> tuple[list[Dweller], dict[UUID, tuple[RelationshipTypeEnum, int]]]:
        """Find the dweller's partner(s): reciprocal partner_id plus MARRIED/PARTNER relationships.

        Takes the already-loaded dweller: re-reading it here cost six statements.

        Returns:
            Tuple of partner dwellers and a mapping of partner_id to (relationship_type, affinity).
        """
        partner_ids = set()
        context: dict[UUID, tuple[RelationshipTypeEnum, int]] = {}

        if dweller.partner_id:
            partner_ids.add(dweller.partner_id)

        reciprocal = await dweller_crud.get_reciprocal_partners(db_session, vault_id, dweller.id)
        partner_ids.update(partner.id for partner in reciprocal)

        for relationship in await relationship_crud.get_partner_links_involving(db_session, dweller.id):
            other_id = (
                relationship.dweller_2_id if relationship.dweller_1_id == dweller.id else relationship.dweller_1_id
            )
            partner_ids.add(other_id)
            context[other_id] = (relationship.relationship_type, relationship.affinity)

        partners = [
            partner
            for partner in await dweller_crud.get_many_with_relations(db_session, list(partner_ids))
            if partner.vault_id == vault_id
        ]
        return partners, context

    @staticmethod
    async def _compute_generation(db_session: AsyncSession, dweller_id: UUID, vault_id: UUID) -> int:
        """Walk parents upward to compute the generation number (0 for orphans).

        Only live, same-vault parents are followed, and every hop is validated
        before it counts, so cross-vault links, soft-deleted dwellers and cycles
        never add phantom generation levels. Each level is one narrow parent-link
        query: the walk needs ids and links, not dweller graphs.
        """
        generation = 0
        seen: set[UUID] = set()
        frontier = [dweller_id]

        while frontier:
            rows = {row[0]: row for row in await dweller_crud.get_ancestry_rows(db_session, frontier)}
            seen.update(frontier)

            candidate_ids: list[UUID] = []
            for current_id in frontier:
                row = rows.get(current_id)
                if row is None:
                    continue
                _, row_vault_id, parent_1_id, parent_2_id, is_deleted = row
                if row_vault_id != vault_id or is_deleted:
                    continue
                candidate_ids.extend(
                    candidate_id
                    for candidate_id in (parent_1_id, parent_2_id)
                    if candidate_id is not None and candidate_id not in seen
                )

            pending = [candidate_id for candidate_id in dict.fromkeys(candidate_ids) if candidate_id not in seen]
            if not pending:
                break

            candidate_rows = {row[0]: row for row in await dweller_crud.get_ancestry_rows(db_session, pending)}
            frontier = [
                candidate_id
                for candidate_id in pending
                if (row := candidate_rows.get(candidate_id)) is not None and row[1] == vault_id and not row[4]
            ]
            if not frontier:
                break
            generation += 1

        return generation

    @classmethod
    async def get_lineage(
        cls, db_session: AsyncSession, dweller_id: UUID, *, dweller: Dweller | None = None
    ) -> LineageResponse:
        """Compute the full lineage for a dweller.

        Pass *dweller* when the caller already loaded it (the detail endpoint does);
        otherwise it is fetched here.

        Raises:
            ResourceNotFoundException: If the dweller does not exist.
        """
        dweller = dweller or await dweller_crud.get(db_session, dweller_id)
        vault_id = dweller.vault_id
        vault_id = ensure_found(vault_id, Dweller, identifier=dweller_id)

        generation = await cls._compute_generation(db_session, dweller_id, vault_id)

        parent_ids = [p for p in (dweller.parent_1_id, dweller.parent_2_id) if p is not None]
        parents = [
            parent
            for parent in await dweller_crud.get_many_with_relations(db_session, parent_ids)
            if parent.vault_id == vault_id
        ]

        children = await cls._find_children(db_session, dweller_id, vault_id)
        siblings = await cls._find_siblings(db_session, dweller, parents, vault_id)
        partners, partner_context = await cls._find_partners(db_session, dweller, vault_id)

        return LineageResponse(
            dweller_id=dweller_id,
            generation=generation,
            parents=cls._to_members(parents, generation - 1),
            children=cls._to_members(children, generation + 1),
            siblings=cls._to_members(siblings, generation),
            partners=cls._to_members(partners, generation, partner_context),
        )


lineage_service = LineageService()
