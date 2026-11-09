"""CRUD operations for relationships."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import or_, tuple_
from sqlalchemy import update as sa_update
from sqlmodel import select

from app.core.enums import PARTNER_LINKED_STAGES
from app.crud.base import CRUDBase
from app.models.relationship import Relationship
from app.schemas.relationship import RelationshipCreate, RelationshipUpdate
from app.utils.time import utcnow

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller


class CRUDRelationship(CRUDBase[Relationship, RelationshipCreate, RelationshipUpdate]):
    """CRUD operations for relationships."""

    async def get_committed_both_alive(
        self, db: AsyncSession, vault_id: UUID, *, minimum_affinity: int = 0
    ) -> list[tuple[Dweller, Dweller]]:
        from sqlalchemy.orm import aliased

        from app.core.enums import AgeGroupEnum
        from app.models.dweller import Dweller

        first_parent = aliased(Dweller)
        second_parent = aliased(Dweller)
        query = (
            select(first_parent, second_parent)
            .select_from(Relationship)
            .join(first_parent, Relationship.dweller_1_id == first_parent.id)
            .join(second_parent, Relationship.dweller_2_id == second_parent.id)
            .where(Relationship.relationship_type.in_(PARTNER_LINKED_STAGES))
            .where(Relationship.affinity >= minimum_affinity)
            .where(first_parent.vault_id == vault_id, second_parent.vault_id == vault_id)
            .where(~first_parent.is_deleted, ~second_parent.is_deleted)
            .where(~first_parent.is_dead, ~second_parent.is_dead)
            .where(first_parent.partner_id == second_parent.id, second_parent.partner_id == first_parent.id)
            .where(
                first_parent.age_group == AgeGroupEnum.ADULT,
                second_parent.age_group == AgeGroupEnum.ADULT,
            )
            .order_by(first_parent.id, second_parent.id)
        )
        result = await db.execute(query)
        couples = {}
        for first, second in result.all():
            # Legacy/imported rows may record the same pair in either direction.
            key = frozenset((first.id, second.id))
            couples.setdefault(key, (first, second))
        return list(couples.values())

    async def get_by_dweller_pair(
        self,
        db: AsyncSession,
        dweller_1_id: UUID,
        dweller_2_id: UUID,
    ) -> Relationship | None:
        """
        Get relationship between two dwellers (order doesn't matter).

        :param db: Database session
        :param dweller_1_id: First dweller ID
        :param dweller_2_id: Second dweller ID
        :returns: Relationship if exists, None otherwise
        """
        query = (
            select(Relationship)
            .where(
                ((Relationship.dweller_1_id == dweller_1_id) & (Relationship.dweller_2_id == dweller_2_id))
                | ((Relationship.dweller_1_id == dweller_2_id) & (Relationship.dweller_2_id == dweller_1_id))
            )
            .order_by(Relationship.id)
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_by_pairs(
        self,
        db: AsyncSession,
        pairs: list[tuple[UUID, UUID]],
    ) -> list[Relationship]:
        """Relationships for the given unordered pairs, ordered by id."""
        if not pairs:
            return []
        forward = tuple_(Relationship.dweller_1_id, Relationship.dweller_2_id).in_(pairs)
        reverse = tuple_(Relationship.dweller_2_id, Relationship.dweller_1_id).in_(pairs)
        query = select(Relationship).where(or_(forward, reverse)).order_by(Relationship.id)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def transition_partner_to_married(
        self,
        db: AsyncSession,
        relationship_id: UUID,
        affinity: int | None = None,
    ) -> bool:
        """Atomically transition a PARTNER relationship to MARRIED.

        Uses a conditional UPDATE so only one concurrent request wins: it only
        updates rows that are still PARTNER. Returns True if this call performed
        the transition (and so should apply the one-time bonus/notification),
        False if the relationship was already not PARTNER (another request won).
        """
        values: dict = {"relationship_type": "MARRIED", "updated_at": utcnow()}
        if affinity is not None:
            values["affinity"] = affinity
        query = (
            sa_update(Relationship)
            .where(Relationship.id == relationship_id, Relationship.relationship_type == "PARTNER")
            .values(**values)
        )
        result = await db.execute(query)
        return result.rowcount > 0

    async def get_by_dweller(
        self,
        db: AsyncSession,
        dweller_id: UUID,
    ) -> list[Relationship]:
        """
        Get all relationships for a specific dweller.

        Args:
            db: Database session
            dweller_id: Dweller ID

        Returns:
            List of relationships for dweller
        """
        query = select(Relationship).where(
            (Relationship.dweller_1_id == dweller_id) | (Relationship.dweller_2_id == dweller_id)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_vault(
        self,
        db: AsyncSession,
        vault_id: UUID,
    ) -> list[Relationship]:
        """
        Get all relationships for dwellers in a vault.

        Args:
            db: Database session
            vault_id: Vault ID

        Returns:
            List of relationships in the vault
        """
        from sqlalchemy.orm import aliased

        from app.models.dweller import Dweller

        dweller_1_alias = aliased(Dweller)
        dweller_2_alias = aliased(Dweller)
        query = (
            select(Relationship)
            .join(dweller_1_alias, Relationship.dweller_1_id == dweller_1_alias.id)
            .join(dweller_2_alias, Relationship.dweller_2_id == dweller_2_alias.id)
            .where(dweller_1_alias.vault_id == vault_id)
            .where(dweller_2_alias.vault_id == vault_id)
            .where(~dweller_1_alias.is_deleted)
            .where(~dweller_2_alias.is_deleted)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_involving_any(self, db: AsyncSession, dweller_ids: set[UUID] | list[UUID]) -> list[Relationship]:
        """Relationships where either side is one of the given dwellers."""
        query = select(Relationship).where(
            (Relationship.dweller_1_id.in_(dweller_ids)) | (Relationship.dweller_2_id.in_(dweller_ids))
        )
        return list((await db.execute(query)).scalars().all())

    async def get_partner_links_involving(self, db: AsyncSession, dweller_id: UUID) -> list[Relationship]:
        """PARTNER/MARRIED-stage relationships where the dweller is either side."""
        query = (
            select(Relationship)
            .where(Relationship.relationship_type.in_(PARTNER_LINKED_STAGES))
            .where((Relationship.dweller_1_id == dweller_id) | (Relationship.dweller_2_id == dweller_id))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_cross_vault_orphans(
        self,
        db: AsyncSession,
        vault_id: UUID,
    ) -> list[Relationship]:
        """Relationships touching a vault whose two dwellers live in different vaults."""
        from sqlalchemy.orm import aliased

        from app.models.dweller import Dweller

        d1 = aliased(Dweller)
        d2 = aliased(Dweller)
        query = (
            select(Relationship)
            .join(d1, Relationship.dweller_1_id == d1.id)
            .join(d2, Relationship.dweller_2_id == d2.id)
            .where(d1.vault_id != d2.vault_id)
            .where((d1.vault_id == vault_id) | (d2.vault_id == vault_id))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create_with_defaults(
        self,
        db: AsyncSession,
        dweller_1_id: UUID,
        dweller_2_id: UUID,
        relationship_type: str = "acquaintance",
        affinity: int = 0,
    ) -> Relationship:
        """
        Create a relationship with default values.

        Args:
            db: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID
            relationship_type: Initial relationship type
            affinity: Initial affinity

        Returns:
            Created relationship
        """
        relationship = Relationship(
            dweller_1_id=dweller_1_id,
            dweller_2_id=dweller_2_id,
            relationship_type=relationship_type,
            affinity=affinity,
        )
        db.add(relationship)
        await db.commit()
        await db.refresh(relationship)
        return relationship


# Create singleton instance
relationship_crud = CRUDRelationship(Relationship)
