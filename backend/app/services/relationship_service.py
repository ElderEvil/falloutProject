"""Service for managing dweller relationships and compatibility."""

import logging
from datetime import datetime

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config.game_balance import (
    AFFINITY_INCREASE_PER_TICK,
    COMPATIBILITY_HAPPINESS_WEIGHT,
    COMPATIBILITY_LEVEL_WEIGHT,
    COMPATIBILITY_PROXIMITY_WEIGHT,
    COMPATIBILITY_SPECIAL_WEIGHT,
    ROMANCE_THRESHOLD,
)
from app.models.dweller import Dweller
from app.models.relationship import Relationship
from app.schemas.common import RelationshipTypeEnum

logger = logging.getLogger(__name__)


class RelationshipService:
    """Service for managing relationships between dwellers."""

    @staticmethod
    async def get_relationship(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> Relationship | None:
        """
        Get existing relationship between two dwellers.

        Args:
            db_session: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID

        Returns:
            Relationship if exists, None otherwise
        """
        # Order doesn't matter - check both directions
        query = select(Relationship).where(
            ((Relationship.dweller_1_id == dweller_1_id) & (Relationship.dweller_2_id == dweller_2_id))
            | ((Relationship.dweller_1_id == dweller_2_id) & (Relationship.dweller_2_id == dweller_1_id))
        )
        result = await db_session.execute(query)
        return result.scalars().first()

    @staticmethod
    async def create_or_get_relationship(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> Relationship:
        """
        Create a new relationship or get existing one.

        Args:
            db_session: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID

        Returns:
            Relationship object
        """
        # Check if relationship already exists
        existing = await RelationshipService.get_relationship(db_session, dweller_1_id, dweller_2_id)
        if existing:
            return existing

        # Create new relationship
        relationship = Relationship(
            dweller_1_id=dweller_1_id,
            dweller_2_id=dweller_2_id,
            relationship_type=RelationshipTypeEnum.ACQUAINTANCE,
            affinity=0,
        )
        db_session.add(relationship)
        await db_session.commit()
        await db_session.refresh(relationship)

        logger.info(f"Created new relationship between {dweller_1_id} and {dweller_2_id}")  # noqa: G004
        return relationship

    @staticmethod
    async def increase_affinity(
        db_session: AsyncSession,
        relationship: Relationship,
        amount: int = AFFINITY_INCREASE_PER_TICK,
    ) -> Relationship:
        """
        Increase affinity between two dwellers.

        Args:
            db_session: Database session
            relationship: Relationship to update
            amount: Amount to increase (default from config)

        Returns:
            Updated relationship
        """
        relationship.affinity = min(100, relationship.affinity + amount)
        relationship.updated_at = datetime.utcnow()
        old_type = relationship.relationship_type

        # Auto-upgrade relationship based on affinity thresholds
        if relationship.affinity >= ROMANCE_THRESHOLD:
            # Progress through relationship stages
            if relationship.relationship_type == RelationshipTypeEnum.ACQUAINTANCE:
                relationship.relationship_type = RelationshipTypeEnum.FRIEND
            elif relationship.relationship_type == RelationshipTypeEnum.FRIEND:
                # Upgrade to romantic at 70+ affinity
                relationship.relationship_type = RelationshipTypeEnum.ROMANTIC

        await db_session.commit()
        await db_session.refresh(relationship)

        # Log relationship progression
        if old_type != relationship.relationship_type:
            logger.info(
                f"Relationship upgraded from {old_type} to {relationship.relationship_type} "  # noqa: G004
                f"between {relationship.dweller_1_id} and {relationship.dweller_2_id}"
            )

        return relationship

    @staticmethod
    async def calculate_compatibility(
        db_session: AsyncSession,  # noqa: ARG004
        dweller_1: Dweller,
        dweller_2: Dweller,
    ) -> float:
        """
        Calculate compatibility score between two dwellers (0.0 - 1.0).

        Factors:
        - SPECIAL similarity (30%)
        - Happiness levels (20%)
        - Level similarity (20%)
        - Same room proximity (30%)

        Args:
            db_session: Database session
            dweller_1: First dweller
            dweller_2: Second dweller

        Returns:
            Compatibility score (0.0 - 1.0)
        """
        # SPECIAL similarity score
        special_attrs = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]
        special_diff = sum(abs(getattr(dweller_1, attr, 0) - getattr(dweller_2, attr, 0)) for attr in special_attrs)
        max_special_diff = 7 * 10  # 7 stats * max 10 difference each
        special_score = 1.0 - (special_diff / max_special_diff)

        # Happiness similarity
        happiness_diff = abs(dweller_1.happiness - dweller_2.happiness)
        happiness_score = 1.0 - (happiness_diff / 100.0)

        # Level similarity
        level_diff = abs(dweller_1.level - dweller_2.level)
        max_level_diff = 50  # Max level is 50
        level_score = 1.0 - (level_diff / max_level_diff)

        # Proximity (same room bonus)
        proximity_score = 1.0 if dweller_1.room_id == dweller_2.room_id and dweller_1.room_id is not None else 0.0

        # Weighted total
        compatibility = (
            special_score * COMPATIBILITY_SPECIAL_WEIGHT
            + happiness_score * COMPATIBILITY_HAPPINESS_WEIGHT
            + level_score * COMPATIBILITY_LEVEL_WEIGHT
            + proximity_score * COMPATIBILITY_PROXIMITY_WEIGHT
        )

        return min(1.0, max(0.0, compatibility))

    @staticmethod
    async def initiate_romance(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> Relationship:
        """
        Initiate a romantic relationship between two dwellers.

        Args:
            db_session: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID

        Returns:
            Updated relationship

        Raises:
            ValueError: If affinity is too low or dwellers are incompatible
        """
        relationship = await RelationshipService.get_relationship(db_session, dweller_1_id, dweller_2_id)

        if not relationship:
            msg = "No relationship exists between these dwellers"
            raise ValueError(msg)

        if relationship.affinity < ROMANCE_THRESHOLD:
            msg = f"Affinity too low ({relationship.affinity}/{ROMANCE_THRESHOLD})"
            raise ValueError(msg)

        relationship.relationship_type = RelationshipTypeEnum.ROMANTIC
        relationship.updated_at = datetime.utcnow()

        await db_session.commit()
        await db_session.refresh(relationship)

        logger.info(f"Initiated romance between {dweller_1_id} and {dweller_2_id}")  # noqa: G004
        return relationship

    @staticmethod
    async def make_partners(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> Relationship:
        """
        Make two dwellers partners (committed relationship).

        Args:
            db_session: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID

        Returns:
            Updated relationship
        """
        relationship = await RelationshipService.get_relationship(db_session, dweller_1_id, dweller_2_id)

        if not relationship:
            msg = "No relationship exists between these dwellers"
            raise ValueError(msg)

        if relationship.relationship_type != RelationshipTypeEnum.ROMANTIC:
            msg = "Dwellers must be in a romantic relationship first"
            raise ValueError(msg)

        relationship.relationship_type = RelationshipTypeEnum.PARTNER
        relationship.updated_at = datetime.utcnow()

        # Update dwellers to have each other as partners
        dweller_1_query = select(Dweller).where(Dweller.id == dweller_1_id)
        dweller_2_query = select(Dweller).where(Dweller.id == dweller_2_id)

        dweller_1 = (await db_session.execute(dweller_1_query)).scalars().first()
        dweller_2 = (await db_session.execute(dweller_2_query)).scalars().first()

        if dweller_1:
            dweller_1.partner_id = dweller_2_id
        if dweller_2:
            dweller_2.partner_id = dweller_1_id

        await db_session.commit()
        await db_session.refresh(relationship)

        logger.info(f"Made partners: {dweller_1_id} and {dweller_2_id}")  # noqa: G004
        return relationship

    @staticmethod
    async def break_up(
        db_session: AsyncSession,
        relationship_id: UUID4,
    ) -> None:
        """
        Break up a relationship.

        Args:
            db_session: Database session
            relationship_id: Relationship ID to break up
        """
        query = select(Relationship).where(Relationship.id == relationship_id)
        relationship = (await db_session.execute(query)).scalars().first()

        if not relationship:
            msg = "Relationship not found"
            raise ValueError(msg)

        # If partners, clear partner_id on both dwellers
        if relationship.relationship_type == RelationshipTypeEnum.PARTNER:
            dweller_1_query = select(Dweller).where(Dweller.id == relationship.dweller_1_id)
            dweller_2_query = select(Dweller).where(Dweller.id == relationship.dweller_2_id)

            dweller_1 = (await db_session.execute(dweller_1_query)).scalars().first()
            dweller_2 = (await db_session.execute(dweller_2_query)).scalars().first()

            if dweller_1:
                dweller_1.partner_id = None
            if dweller_2:
                dweller_2.partner_id = None

        # Mark as ex
        relationship.relationship_type = RelationshipTypeEnum.EX
        relationship.affinity = max(0, relationship.affinity - 30)  # Penalty for breakup
        relationship.updated_at = datetime.utcnow()

        await db_session.commit()

        logger.info(f"Break up: {relationship.dweller_1_id} and {relationship.dweller_2_id}")  # noqa: G004


relationship_service = RelationshipService()
