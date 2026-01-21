"""CRUD operations for relationships."""

from typing import TYPE_CHECKING

from pydantic import UUID4
from sqlalchemy import and_
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.relationship import Relationship
from app.schemas.relationship import RelationshipCreate, RelationshipUpdate

if TYPE_CHECKING:
    pass


class CRUDRelationship(CRUDBase[Relationship, RelationshipCreate, RelationshipUpdate]):
    """CRUD operations for relationships."""

    async def get_by_dweller_pair(
        self,
        db: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> Relationship | None:
        """
        Get relationship between two dwellers (order doesn't matter).

        Args:
            db: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID

        Returns:
            Relationship if exists, None otherwise
        """
        query = select(Relationship).where(
            ((Relationship.dweller_1_id == dweller_1_id) & (Relationship.dweller_2_id == dweller_2_id))
            | ((Relationship.dweller_1_id == dweller_2_id) & (Relationship.dweller_2_id == dweller_1_id))
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def get_by_dweller(
        self,
        db: AsyncSession,
        dweller_id: UUID4,
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

    async def get_by_type(
        self,
        db: AsyncSession,
        relationship_type: str,
        vault_id: UUID4 | None = None,
    ) -> list[Relationship]:
        """
        Get relationships by type, optionally filtered by vault.

        Args:
            db: Database session
            relationship_type: Type of relationship
            vault_id: Optional vault ID filter

        Returns:
            List of matching relationships
        """
        from app.models.dweller import Dweller

        query = select(Relationship).where(Relationship.relationship_type == relationship_type)

        if vault_id is not None:
            query = query.join(Dweller, Relationship.dweller_1_id == Dweller.id).where(Dweller.vault_id == vault_id)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_partners(
        self,
        db: AsyncSession,
        dweller_id: UUID4,
    ) -> Relationship | None:
        """
        Get partner relationship for a dweller.

        Args:
            db: Database session
            dweller_id: Dweller ID

        Returns:
            Partner relationship if exists, None otherwise
        """
        query = select(Relationship).where(
            and_(
                (Relationship.dweller_1_id == dweller_id) | (Relationship.dweller_2_id == dweller_id),
                Relationship.relationship_type == "partner",
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def exists_between(
        self,
        db: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> bool:
        """
        Check if relationship exists between two dwellers.

        Args:
            db: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID

        Returns:
            True if relationship exists, False otherwise
        """
        relationship = await self.get_by_dweller_pair(db, dweller_1_id, dweller_2_id)
        return relationship is not None

    async def get_by_vault(
        self,
        db: AsyncSession,
        vault_id: UUID4,
    ) -> list[Relationship]:
        """
        Get all relationships for dwellers in a vault.

        Args:
            db: Database session
            vault_id: Vault ID

        Returns:
            List of relationships in the vault
        """
        from app.models.dweller import Dweller

        query = (
            select(Relationship)
            .join(Dweller, Relationship.dweller_1_id == Dweller.id)
            .where(Dweller.vault_id == vault_id)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def create_with_defaults(
        self,
        db: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
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
