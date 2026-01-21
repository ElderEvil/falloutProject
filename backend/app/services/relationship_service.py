"""Service for managing dweller relationships and compatibility."""

import logging
from datetime import datetime

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.relationship import Relationship
from app.schemas.common import GenderEnum, RelationshipTypeEnum
from app.schemas.relationship import CompatibilityScore
from app.utils.exceptions import ResourceNotFoundException

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
        return await relationship_crud.get_by_dweller_pair(db_session, dweller_1_id, dweller_2_id)

    @staticmethod
    async def get_or_create_relationship(
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
        existing = await relationship_crud.get_by_dweller_pair(db_session, dweller_1_id, dweller_2_id)
        if existing:
            return existing

        # Create new relationship via CRUD
        relationship = await relationship_crud.create_with_defaults(
            db_session, dweller_1_id, dweller_2_id, relationship_type=RelationshipTypeEnum.ACQUAINTANCE, affinity=0
        )

        logger.info(f"Created new relationship between {dweller_1_id} and {dweller_2_id}")
        return relationship

    @staticmethod
    async def increase_affinity(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
        amount: int = 1,
    ) -> Relationship:
        """
        Increase affinity between two dwellers.

        Args:
            db_session: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID
            amount: Affinity increase amount

        Returns:
            Updated relationship
        """
        relationship = await relationship_crud.get_by_dweller_pair(db_session, dweller_1_id, dweller_2_id)
        if not relationship:
            msg = "Relationship not found between dwellers"
            raise ValueError(msg)

        update_data = {"affinity": min(100, relationship.affinity + amount), "updated_at": datetime.utcnow()}
        old_type = relationship.relationship_type

        # Auto-upgrade relationship based on affinity thresholds
        if update_data["affinity"] >= game_config.relationship.romance_threshold:
            # Progress through relationship stages
            if relationship.relationship_type == RelationshipTypeEnum.ACQUAINTANCE:
                update_data["relationship_type"] = RelationshipTypeEnum.FRIEND
            elif relationship.relationship_type == RelationshipTypeEnum.FRIEND:
                # Upgrade to romantic at 70+ affinity
                update_data["relationship_type"] = RelationshipTypeEnum.ROMANTIC

        # Update via CRUD
        relationship = await relationship_crud.update(db_session, relationship.id, update_data)

        logger.debug(
            f"Affinity increased {dweller_1_id} ↔ {dweller_2_id}: {old_type} → {relationship.relationship_type}"
        )
        return relationship

    @staticmethod
    async def initiate_romance(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> Relationship:
        """
        Initiate romantic relationship between two dwellers.

        Args:
            db_session: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID

        Returns:
            Updated relationship

        Raises:
            ValueError: If relationship affinity is too low
        """
        relationship = await relationship_crud.get_by_dweller_pair(db_session, dweller_1_id, dweller_2_id)
        if not relationship:
            msg = "Relationship not found between dwellers"
            raise ValueError(msg)

        if relationship.affinity < game_config.relationship.romance_threshold:
            msg = (
                f"Affinity too low for romance ({relationship.affinity} < {game_config.relationship.romance_threshold})"
            )
            raise ValueError(msg)

        update_data = {"relationship_type": RelationshipTypeEnum.ROMANTIC, "updated_at": datetime.utcnow()}

        # Update via CRUD
        relationship = await relationship_crud.update(db_session, relationship.id, update_data)

        logger.info(f"Romance initiated {dweller_1_id} ↔ {dweller_2_id}")
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

        Raises:
            ValueError: If no relationship exists or affinity is too low
        """
        relationship = await relationship_crud.get_by_dweller_pair(db_session, dweller_1_id, dweller_2_id)
        if not relationship:
            msg = "No relationship exists"
            raise ValueError(msg)

        if relationship.affinity < game_config.relationship.romance_threshold:
            threshold = game_config.relationship.romance_threshold
            msg = f"Affinity too low for partnership ({relationship.affinity} < {threshold})"
            raise ValueError(msg)

        update_data = {"relationship_type": RelationshipTypeEnum.PARTNER, "updated_at": datetime.utcnow()}

        # Update relationship via CRUD
        relationship = await relationship_crud.update(db_session, relationship.id, update_data)

        # Update both dwellers to have each other as partners
        await dweller_crud.update(db_session, dweller_1_id, {"partner_id": dweller_2_id})
        await dweller_crud.update(db_session, dweller_2_id, {"partner_id": dweller_1_id})

        logger.info(f"Partners made: {dweller_1_id} ↔ {dweller_2_id}")
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
        # Get relationship via CRUD, handle ResourceNotFoundException
        try:
            relationship = await relationship_crud.get(db_session, relationship_id)
        except ResourceNotFoundException:
            msg = "Relationship not found"
            raise ValueError(msg) from None

        # If partners, clear partner_id on both dwellers via CRUD
        if relationship.relationship_type == RelationshipTypeEnum.PARTNER:
            if relationship.dweller_1_id:
                await dweller_crud.update(db_session, relationship.dweller_1_id, {"partner_id": None})
            if relationship.dweller_2_id:
                await dweller_crud.update(db_session, relationship.dweller_2_id, {"partner_id": None})

        # Mark as ex via CRUD
        update_data = {
            "relationship_type": RelationshipTypeEnum.EX,
            "affinity": max(0, relationship.affinity - 30),  # Penalty for breakup
            "updated_at": datetime.utcnow(),
        }
        await relationship_crud.update(db_session, relationship.id, update_data)

        logger.info(f"Break up: {relationship.dweller_1_id} and {relationship.dweller_2_id}")

    @staticmethod
    async def quick_pair_dwellers(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> Relationship:
        """
        Irradiated Cupid

        Instantly pairs two random compatible dwellers for testing/fun.
        - Finds one male and one female without partners
        - Creates a high-affinity relationship (90%)
        - Makes them romantic partners
        - Moves them to a private living quarters (kicks out any third wheels!)
        - Ready to breed immediately with 90% conception chance per tick
        """
        # Pre-validate affinity meets romance threshold before creating any records
        quick_pair_affinity = 90
        if quick_pair_affinity < game_config.relationship.romance_threshold:
            msg = (
                f"Quick pair affinity ({quick_pair_affinity}) is below romance threshold "
                f"({game_config.relationship.romance_threshold}). Cannot create partners."
            )
            raise ValueError(msg)

        # Get all adult dwellers in vault without partners (existing logic preserved)
        query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(Dweller.age_group == "adult")
            .where(Dweller.partner_id.is_(None))  # type: ignore[union-attr]
        )
        result = await db_session.execute(query)
        available_dwellers = list(result.scalars().all())

        if len(available_dwellers) < 2:
            msg = "Need at least 2 adult dwellers without partners"
            raise ValueError(msg)

        # Separate by gender
        males = [d for d in available_dwellers if d.gender == GenderEnum.MALE]
        females = [d for d in available_dwellers if d.gender == GenderEnum.FEMALE]

        if not males or not females:
            msg = "Need at least one male and one female dweller"
            raise ValueError(msg)

        # Pick first available from each gender
        dweller_1 = males[0]
        dweller_2 = females[0]

        # Create relationship with partner type directly (since we pre-validated affinity)
        relationship = await relationship_crud.create_with_defaults(
            db_session,
            dweller_1.id,
            dweller_2.id,
            relationship_type=RelationshipTypeEnum.PARTNER,
            affinity=quick_pair_affinity,
        )

        # Update both dwellers to have each other as partners
        await dweller_crud.update(db_session, dweller_1.id, {"partner_id": dweller_2.id})
        await dweller_crud.update(db_session, dweller_2.id, {"partner_id": dweller_1.id})

        # Simplified - just create the relationship and partners, skip complex room management
        logger.info(f"Quick paired: {dweller_1.id} and {dweller_2.id}")
        return relationship

    @staticmethod
    async def calculate_compatibility_score(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> CompatibilityScore:
        """
        Calculate compatibility score between two dwellers.

        Raises:
            ResourceNotFoundException: If either dweller is not found (propagates as HTTP 404)
        """
        # Let ResourceNotFoundException propagate directly (HTTP 404)
        dweller_1 = await dweller_crud.get(db_session, dweller_1_id)
        dweller_2 = await dweller_crud.get(db_session, dweller_2_id)

        # SPECIAL similarity score
        special_attrs = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]
        special_diff = sum(abs(getattr(dweller_1, attr, 0) - getattr(dweller_2, attr, 0)) for attr in special_attrs)
        max_special_diff = 7 * 10
        special_score = 1.0 - (special_diff / max_special_diff)

        # Happiness similarity
        happiness_diff = abs(dweller_1.happiness - dweller_2.happiness)
        happiness_score = 1.0 - (happiness_diff / 100.0)

        # Level similarity
        level_diff = abs(dweller_1.level - dweller_2.level)
        max_level_diff = 50
        level_score = 1.0 - (level_diff / max_level_diff)

        # Proximity (same room bonus)
        proximity_score = 1.0 if (dweller_1.room_id and dweller_1.room_id == dweller_2.room_id) else 0.0

        # Weighted total
        compatibility = (
            special_score * game_config.relationship.compatibility_special_weight
            + happiness_score * game_config.relationship.compatibility_happiness_weight
            + level_score * game_config.relationship.compatibility_level_weight
            + proximity_score * game_config.relationship.compatibility_proximity_weight
        )

        return CompatibilityScore(
            dweller_1_id=dweller_1_id,
            dweller_2_id=dweller_2_id,
            score=min(1.0, max(0.0, compatibility)),
            special_score=special_score,
            happiness_score=happiness_score,
            level_score=level_score,
            proximity_score=proximity_score,
        )

    @staticmethod
    async def calculate_compatibility(
        db_session: AsyncSession,
        dweller_1: Dweller,
        dweller_2: Dweller,
    ) -> float:
        """
        Backward-compatible wrapper for calculate_compatibility_score.

        Args:
            db_session: Database session
            dweller_1: First dweller object
            dweller_2: Second dweller object

        Returns:
            Compatibility score as a float (0.0-1.0)
        """
        result = await RelationshipService.calculate_compatibility_score(db_session, dweller_1.id, dweller_2.id)
        return result.score


relationship_service = RelationshipService()
