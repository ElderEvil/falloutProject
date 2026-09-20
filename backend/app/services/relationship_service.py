"""Service for managing dweller relationships and compatibility."""

import logging
from datetime import datetime

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import (
    PARTNER_LINKED_STAGES,
    SPECIAL_STATS,
    RelationshipTypeEnum,
)
from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.notification import NotificationType
from app.models.relationship import Relationship
from app.schemas.relationship import CompatibilityScore
from app.services.bio_service import bio_service
from app.services.notification_service import NotificationService
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)


class RelationshipService:
    """Service for managing relationships between dwellers."""

    @staticmethod
    async def get_relationship(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> Relationship | None:
        """Get existing relationship between two dwellers.

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
        """Create a new relationship or get existing one.

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
        """Increase affinity between two dwellers.

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

        new_affinity = min(100, relationship.affinity + amount)
        update_data = {"affinity": new_affinity, "updated_at": datetime.utcnow()}
        old_type = relationship.relationship_type

        # Auto-upgrade relationship based on affinity thresholds
        if update_data["affinity"] >= game_config.relationship.romance_threshold:
            # Progress through relationship stages
            if relationship.relationship_type == RelationshipTypeEnum.ACQUAINTANCE:
                update_data["relationship_type"] = RelationshipTypeEnum.FRIEND
            elif relationship.relationship_type == RelationshipTypeEnum.FRIEND:
                update_data["relationship_type"] = RelationshipTypeEnum.ROMANTIC
            elif relationship.relationship_type == RelationshipTypeEnum.ROMANTIC:
                # Skip the promotion if either dweller is already committed to a
                # third dweller (game-loop tick path: log and keep ROMANTIC rather
                # than raising, which would break the vault).
                if await RelationshipService._committed_partner_elsewhere(
                    db_session,
                    relationship.dweller_1_id,
                    except_ids={relationship.dweller_1_id, relationship.dweller_2_id},
                ) or await RelationshipService._committed_partner_elsewhere(
                    db_session,
                    relationship.dweller_2_id,
                    except_ids={relationship.dweller_1_id, relationship.dweller_2_id},
                ):
                    logger.info(
                        f"Skipping ROMANTIC->PARTNER promotion for {relationship.dweller_1_id} ↔ "
                        f"{relationship.dweller_2_id}: one dweller is already committed to another dweller"
                    )
                else:
                    update_data["relationship_type"] = RelationshipTypeEnum.PARTNER
                    await RelationshipService._set_partner_ids(
                        db_session, relationship.dweller_1_id, relationship.dweller_2_id
                    )

        is_marriage_transition = (
            relationship.relationship_type == RelationshipTypeEnum.PARTNER
            and new_affinity >= game_config.relationship.marriage_threshold
        )
        if is_marriage_transition:
            # Defense-in-depth: skip the transition if either dweller is already
            # committed to a third dweller (pre-existing corrupt data). Log and
            # persist only the affinity bump rather than raising.
            if await RelationshipService._committed_partner_elsewhere(
                db_session,
                relationship.dweller_1_id,
                except_ids={relationship.dweller_1_id, relationship.dweller_2_id},
            ) or await RelationshipService._committed_partner_elsewhere(
                db_session,
                relationship.dweller_2_id,
                except_ids={relationship.dweller_1_id, relationship.dweller_2_id},
            ):
                logger.info(
                    f"Skipping PARTNER->MARRIED transition for {relationship.dweller_1_id} ↔ "
                    f"{relationship.dweller_2_id}: one dweller is already committed to another dweller"
                )
                relationship = await relationship_crud.update(db_session, relationship.id, update_data)
            elif await relationship_crud.transition_partner_to_married(
                db_session, relationship.id, affinity=new_affinity
            ):
                relationship.relationship_type = RelationshipTypeEnum.MARRIED
                relationship.affinity = new_affinity
                relationship.updated_at = update_data["updated_at"]
                db_session.add(relationship)
                await RelationshipService._apply_marriage_bonus(
                    db_session, relationship.dweller_1_id, relationship.dweller_2_id, commit=False
                )
                await db_session.commit()
                await RelationshipService._notify_marriage(db_session, relationship)
            else:
                # Lost the race (already not PARTNER): just persist the affinity bump.
                relationship = await relationship_crud.update(db_session, relationship.id, update_data)
        else:
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
        """Initiate romantic relationship between two dwellers.

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
        """Make two dwellers partners (committed relationship).

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
            msg = "Relationship not found between dwellers"
            raise ValueError(msg)

        if relationship.affinity < game_config.relationship.romance_threshold:
            threshold = game_config.relationship.romance_threshold
            msg = f"Affinity too low for partnership ({relationship.affinity} < {threshold})"
            raise ValueError(msg)

        # Guard: neither dweller may already be committed to a third dweller.
        for dweller_id in (dweller_1_id, dweller_2_id):
            committed = await RelationshipService._committed_partner_elsewhere(
                db_session, dweller_id, except_ids={dweller_1_id, dweller_2_id}
            )
            if committed is not None:
                msg = f"Dweller {dweller_id} is already {committed.relationship_type.value} to another dweller"
                raise ValidationException(msg)

        update_data = {"relationship_type": RelationshipTypeEnum.PARTNER, "updated_at": datetime.utcnow()}

        # Update relationship via CRUD
        relationship = await relationship_crud.update(db_session, relationship.id, update_data)

        # Update both dwellers to have each other as partners in a single transaction
        await RelationshipService._set_partner_ids(db_session, dweller_1_id, dweller_2_id)

        logger.info(f"Partners made: {dweller_1_id} ↔ {dweller_2_id}")
        return relationship

    @staticmethod
    async def _set_partner_ids(db_session: AsyncSession, dweller_1_id: UUID4, dweller_2_id: UUID4) -> None:
        """Set reciprocal partner_ids on both dwellers atomically."""
        try:
            dweller_1 = await dweller_crud.get(db_session, dweller_1_id)
            dweller_2 = await dweller_crud.get(db_session, dweller_2_id)

            dweller_1.partner_id = dweller_2_id
            dweller_2.partner_id = dweller_1_id

            db_session.add(dweller_1)
            db_session.add(dweller_2)
            await db_session.commit()
            await db_session.refresh(dweller_1)
            await db_session.refresh(dweller_2)
        except Exception as e:
            await db_session.rollback()
            msg = f"Failed to update partner IDs for dwellers: {e}"
            raise ValueError(msg) from e

    @staticmethod
    async def _committed_partner_elsewhere(
        db_session: AsyncSession,
        dweller_id: UUID4,
        except_ids: set[UUID4],
    ) -> Relationship | None:
        """Return the first committed relationship whose other side is not in except_ids.

        ``get_partner_links_involving`` is the source of truth for committed
        (PARTNER/MARRIED) relationships; ``except_ids`` lets callers exclude the
        relationship currently being formed so it does not count as a conflict.
        """
        links = await relationship_crud.get_partner_links_involving(db_session, dweller_id)
        for link in links:
            other_id = link.dweller_2_id if link.dweller_1_id == dweller_id else link.dweller_1_id
            if other_id not in except_ids:
                return link
        return None

    @staticmethod
    async def _apply_marriage_bonus(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
        *,
        commit: bool = True,
    ) -> None:
        """Apply the one-time happiness bonus to both newly married dwellers.

        Args:
            db_session: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID
            commit: Whether to commit the bonus (default True); pass False to defer
                the commit so it lands in the same transaction as the relationship update.
        """
        for dweller_id in (dweller_1_id, dweller_2_id):
            dweller = await dweller_crud.get(db_session, dweller_id)
            bonus = game_config.relationship.partner_happiness_bonus + game_config.relationship.married_happiness_bonus
            dweller.happiness = max(0, min(100, dweller.happiness + bonus))
            db_session.add(dweller)
        if commit:
            await db_session.commit()

    @staticmethod
    async def marry(db_session: AsyncSession, relationship_id: UUID4) -> Relationship:
        """Marry two partners with affinity at or above the marriage threshold.

        Raises:
            ValidationException: If the relationship is not found, is not PARTNER,
                or affinity is below the threshold.
        """
        try:
            relationship = await relationship_crud.get(db_session, relationship_id)
        except ResourceNotFoundException:
            msg = "Relationship not found"
            raise ValidationException(msg) from None

        if relationship.relationship_type != RelationshipTypeEnum.PARTNER:
            msg = "Only partners can marry"
            raise ValidationException(msg)

        if relationship.affinity < game_config.relationship.marriage_threshold:
            threshold = game_config.relationship.marriage_threshold
            msg = f"Affinity too low for marriage ({relationship.affinity} < {threshold})"
            raise ValidationException(msg)

        # Defense-in-depth: reject if either dweller is already committed to a
        # third dweller (pre-existing corrupt data).
        for dweller_id in (relationship.dweller_1_id, relationship.dweller_2_id):
            committed = await RelationshipService._committed_partner_elsewhere(
                db_session,
                dweller_id,
                except_ids={relationship.dweller_1_id, relationship.dweller_2_id},
            )
            if committed is not None:
                msg = f"Dweller {dweller_id} is already {committed.relationship_type.value} to another dweller"
                raise ValidationException(msg)

        # Conditional PARTNER->MARRIED update: only one concurrent request wins;
        # the loser raises so it applies no bonus/notification.
        if not await relationship_crud.transition_partner_to_married(db_session, relationship_id):
            msg = "Only partners can marry"
            raise ValidationException(msg)

        relationship.relationship_type = RelationshipTypeEnum.MARRIED
        await RelationshipService._apply_marriage_bonus(
            db_session, relationship.dweller_1_id, relationship.dweller_2_id
        )
        await RelationshipService._record_marriage_bios(db_session, relationship)
        await db_session.refresh(relationship)
        await RelationshipService._notify_marriage(db_session, relationship)

        logger.info(f"Married: {relationship.dweller_1_id} ↔ {relationship.dweller_2_id}")
        return relationship

    @staticmethod
    async def _record_marriage_bios(db_session: AsyncSession, relationship: Relationship) -> None:
        """Narrate the marriage into both partners' bios."""
        dweller_1 = await dweller_crud.get(db_session, relationship.dweller_1_id)
        dweller_2 = await dweller_crud.get(db_session, relationship.dweller_2_id)
        name_1 = f"{dweller_1.first_name} {dweller_1.last_name or ''}".strip()
        name_2 = f"{dweller_2.first_name} {dweller_2.last_name or ''}".strip()
        await bio_service.append_entry(
            db_session, dweller_1.id, "family", f"Married {name_2}.", ref={"partner_id": str(dweller_2.id)}
        )
        await bio_service.append_entry(
            db_session, dweller_2.id, "family", f"Married {name_1}.", ref={"partner_id": str(dweller_1.id)}
        )

    @staticmethod
    async def _notify_marriage(db_session: AsyncSession, relationship: Relationship) -> None:
        """Best-effort notification for the vault owner when two dwellers marry."""
        try:
            dweller_1 = await dweller_crud.get(db_session, relationship.dweller_1_id)
            dweller_2 = await dweller_crud.get(db_session, relationship.dweller_2_id)
            name_1 = f"{dweller_1.first_name} {dweller_1.last_name or ''}".strip()
            name_2 = f"{dweller_2.first_name} {dweller_2.last_name or ''}".strip()
            message = f"{name_1} and {name_2} are now married."
            vault_id = dweller_1.vault_id
        except Exception:
            logger.exception("Failed to send marriage notification for relationship %s", relationship.id)
            return
        await NotificationService.notify_owner(
            db_session,
            vault_id,
            context=f"marriage relationship={relationship.id} vault={vault_id}",
            sender=lambda user_id: NotificationService.create_and_send(
                db_session,
                user_id=user_id,
                notification_type=NotificationType.RELATIONSHIP_FORMED,
                title="Marriage!",
                message=message,
                vault_id=vault_id,
                from_dweller_id=relationship.dweller_1_id,
                meta_data={"relationship_id": str(relationship.id)},
            ),
        )

    @staticmethod
    async def break_up(
        db_session: AsyncSession,
        relationship_id: UUID4,
    ) -> None:
        """Break up a relationship.

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

        # If partners or married, clear partner_id on both dwellers atomically
        if relationship.relationship_type in PARTNER_LINKED_STAGES:
            try:
                dweller_1 = await dweller_crud.get(db_session, relationship.dweller_1_id)
                dweller_2 = await dweller_crud.get(db_session, relationship.dweller_2_id)

                # Clear partner_id in memory
                dweller_1.partner_id = None
                dweller_2.partner_id = None

                # Add both to session and commit atomically
                db_session.add(dweller_1)
                db_session.add(dweller_2)
                await db_session.commit()
                await db_session.refresh(dweller_1)
                await db_session.refresh(dweller_2)
            except ResourceNotFoundException:
                # One or both dwellers may have been deleted, continue with breakup
                pass
            except Exception as e:
                await db_session.rollback()
                msg = f"Failed to clear partner IDs for dwellers: {e}"
                raise ValueError(msg) from e

        # Mark as ex via CRUD
        update_data = {
            "relationship_type": RelationshipTypeEnum.EX,
            "affinity": max(0, relationship.affinity - 30),  # Penalty for breakup
            "updated_at": datetime.utcnow(),
        }
        await relationship_crud.update(db_session, relationship.id, update_data)

        logger.info(f"Break up: {relationship.dweller_1_id} and {relationship.dweller_2_id}")

    @staticmethod
    async def calculate_compatibility_score(
        db_session: AsyncSession,
        dweller_1_id: UUID4,
        dweller_2_id: UUID4,
    ) -> CompatibilityScore:
        """Calculate compatibility score between two dwellers.

        Raises:
            ResourceNotFoundException: If either dweller is not found (propagates as HTTP 404)
        """
        # Let ResourceNotFoundException propagate directly (HTTP 404)
        dweller_1 = await dweller_crud.get(db_session, dweller_1_id)
        dweller_2 = await dweller_crud.get(db_session, dweller_2_id)

        # SPECIAL similarity score
        special_attrs = SPECIAL_STATS
        special_diff = sum(abs(getattr(dweller_1, attr, 0) - getattr(dweller_2, attr, 0)) for attr in special_attrs)
        max_special_diff = game_config.relationship.max_special_diff
        special_score = 1.0 - (special_diff / max_special_diff)

        # Happiness similarity
        happiness_diff = abs(dweller_1.happiness - dweller_2.happiness)
        happiness_score = 1.0 - (happiness_diff / 100.0)

        # Level similarity
        level_diff = abs(dweller_1.level - dweller_2.level)
        max_level_diff = game_config.relationship.max_level_diff
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
        """Backward-compatible wrapper for calculate_compatibility_score.

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
