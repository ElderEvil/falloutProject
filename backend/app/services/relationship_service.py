"""Service for managing dweller relationships and compatibility."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import PARTNER_LINKED_STAGES, SPECIAL_STATS, NotificationType, RelationshipTypeEnum
from app.core.game_config import game_config
from app.crud import dweller as dweller_crud
from app.crud.relationship import relationship_crud
from app.models.dweller import Dweller
from app.models.relationship import Relationship
from app.options.identity_modifiers import effective_stat
from app.options.races import DISCOMFORT_EFFECTS, RaceOption, discomfort_between, race_of
from app.schemas.relationship import CompatibilityScore, VaultRelationshipRead
from app.services.bio_service import bio_service
from app.services.family.breeding_service import conception_potential
from app.services.notification_service import NotificationService
from app.utils.dweller_availability import DwellerAction, purposeful_action_error
from app.utils.exceptions import ResourceNotFoundException, ValidationException
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

#: Neutral SPECIAL baseline: the Charisma point where relationship modifiers are 1.0x.
_CHARISMA_BASELINE = 5
#: Lowest affinity a non-committed relationship can reach (model invariant).
_AFFINITY_MIN = -100


@dataclass(frozen=True)
class CompatibilityParts:
    """Pure compatibility inputs shared by the API score and the affinity tick."""

    score: float
    special_score: float
    happiness_score: float
    level_score: float
    proximity_score: float


def effective_charisma(dweller: Dweller) -> int:
    """Charisma after racial, outfit and pet modifiers: the value production reads."""
    return effective_stat(dweller, "charisma")


def shares_race(dweller1: Dweller, dweller2: Dweller) -> bool:
    """Whether both dwellers resolve to the same race; missing races count as human."""
    return (race_of(dweller1) or RaceOption.HUMAN) == (race_of(dweller2) or RaceOption.HUMAN)


def compatibility_components(dweller1: Dweller, dweller2: Dweller) -> CompatibilityParts:
    """Compatibility scores from loaded dweller rows, without touching the session."""
    special_diff = sum(abs(getattr(dweller1, attr, 0) - getattr(dweller2, attr, 0)) for attr in SPECIAL_STATS)
    special_score = 1.0 - (special_diff / game_config.relationship.max_special_diff)

    happiness_diff = abs(dweller1.happiness - dweller2.happiness)
    happiness_score = 1.0 - (happiness_diff / 100.0)

    level_diff = abs(dweller1.level - dweller2.level)
    level_score = 1.0 - (level_diff / game_config.relationship.max_level_diff)

    proximity_score = 1.0 if (dweller1.room_id and dweller1.room_id == dweller2.room_id) else 0.0

    compatibility = (
        special_score * game_config.relationship.compatibility_special_weight
        + happiness_score * game_config.relationship.compatibility_happiness_weight
        + level_score * game_config.relationship.compatibility_level_weight
        + proximity_score * game_config.relationship.compatibility_proximity_weight
    )
    return CompatibilityParts(
        score=min(1.0, max(0.0, compatibility)),
        special_score=special_score,
        happiness_score=happiness_score,
        level_score=level_score,
        proximity_score=proximity_score,
    )


def affinity_chemistry(dweller1: Dweller, dweller2: Dweller) -> float:
    """Compatibility plus race, Charisma and comfort shifts that decide bond direction."""
    config = game_config.relationship
    race_shift = config.race_chemistry_bonus if shares_race(dweller1, dweller2) else -config.race_chemistry_bonus
    average_charisma = (effective_charisma(dweller1) + effective_charisma(dweller2)) / 2
    charisma_shift = (average_charisma - _CHARISMA_BASELINE) * config.charisma_chemistry_weight
    chemistry = compatibility_components(dweller1, dweller2).score + race_shift + charisma_shift
    if discomfort := discomfort_between(dweller1, dweller2):
        chemistry -= DISCOMFORT_EFFECTS[discomfort.severity].chemistry_penalty
    return chemistry


def _charisma_affinity_multiplier(average_charisma: float) -> float:
    config = game_config.relationship
    raw = 1 + (average_charisma - _CHARISMA_BASELINE) * config.charisma_affinity_rate
    return max(config.charisma_affinity_min_multiplier, min(config.charisma_affinity_max_multiplier, raw))


def affinity_change(dweller1: Dweller, dweller2: Dweller) -> int:
    """Signed affinity change per tick for a co-located pair.

    Shared race and Charisma raise the gain; poor chemistry (low compatibility,
    low Charisma, mixed races) tips the same pair into a slow loss instead.
    """
    if (
        purposeful_action_error(dweller1, DwellerAction.SOCIAL) is not None
        or purposeful_action_error(dweller2, DwellerAction.SOCIAL) is not None
    ):
        return 0
    config = game_config.relationship
    average_charisma = (effective_charisma(dweller1) + effective_charisma(dweller2)) / 2
    charisma_factor = _charisma_affinity_multiplier(average_charisma)
    race_factor = (
        config.same_race_affinity_multiplier
        if shares_race(dweller1, dweller2)
        else (config.cross_race_affinity_multiplier)
    )
    if affinity_chemistry(dweller1, dweller2) >= config.affinity_drift_threshold:
        return max(1, int(config.affinity_increase_per_tick * charisma_factor * race_factor + 0.5))
    loss_factor = max(0.5, 2 - charisma_factor) / max(race_factor, 0.01)
    loss = max(1, int(config.affinity_loss_per_tick * loss_factor + 0.5))
    return -min(config.affinity_max_loss_per_tick, loss)


class RelationshipService:
    """Service for managing relationships between dwellers."""

    @staticmethod
    async def get_vault_relationships_with_progress(
        db_session: AsyncSession, vault_id: UUID
    ) -> list[VaultRelationshipRead]:
        """Describe bond growth using the same room and rate rules as the game tick."""
        relationships = await relationship_crud.get_by_vault(db_session, vault_id)
        if not relationships:
            return []
        living_quarters_dwellers = await dweller_crud.get_living_quarters_dwellers(db_session, vault_id)
        dwellers = await dweller_crud.get_by_ids_in_vault(
            db_session,
            list(
                {
                    dweller_id
                    for relationship in relationships
                    for dweller_id in (relationship.dweller_1_id, relationship.dweller_2_id)
                }
            ),
            vault_id,
        )
        dwellers_by_id = {dweller.id: dweller for dweller in dwellers}
        living_quarters_ids = {dweller.id for dweller in living_quarters_dwellers}
        committed_ids = {
            dweller_id
            for relationship in relationships
            if relationship.relationship_type in PARTNER_LINKED_STAGES
            for dweller_id in (relationship.dweller_1_id, relationship.dweller_2_id)
        }

        result = []
        for relationship in relationships:
            first = dwellers_by_id[relationship.dweller_1_id]
            second = dwellers_by_id[relationship.dweller_2_id]
            growing_together = (
                first.id in living_quarters_ids and second.id in living_quarters_ids and first.room_id == second.room_id
            )
            change = affinity_change(first, second) if growing_together else 0
            if change > 0:
                change = min(change, 100 - relationship.affinity)
            else:
                floor = 0 if relationship.relationship_type in PARTNER_LINKED_STAGES else _AFFINITY_MIN
                change = max(change, floor - relationship.affinity)
            discomfort = discomfort_between(first, second)
            result.append(
                VaultRelationshipRead.model_validate(
                    relationship,
                    update={
                        "bond_change_per_tick": change,
                        "bond_tick_seconds": game_config.game_loop.tick_interval,
                        "conception_potential": conception_potential(first, second),
                        "same_race": shares_race(first, second),
                        "average_charisma": int((effective_charisma(first) + effective_charisma(second)) / 2 + 0.5),
                        "discomfort_severity": discomfort.severity.value if discomfort else None,
                        "discomfort_source": discomfort.source.value if discomfort else None,
                        "can_make_partners": (
                            purposeful_action_error(first, DwellerAction.SOCIAL) is None
                            and purposeful_action_error(second, DwellerAction.SOCIAL) is None
                            and not (
                                relationship.relationship_type == RelationshipTypeEnum.ROMANTIC
                                and (
                                    relationship.dweller_1_id in committed_ids
                                    or relationship.dweller_2_id in committed_ids
                                )
                            )
                        ),
                    },
                )
            )
        return result

    @staticmethod
    async def get_relationship(
        db_session: AsyncSession,
        dweller_1_id: UUID,
        dweller_2_id: UUID,
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
        dweller_1_id: UUID,
        dweller_2_id: UUID,
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
    def _stage_update(db_session: AsyncSession, relationship: Relationship, update_data: dict) -> None:
        for field, value in update_data.items():
            setattr(relationship, field, value)
        db_session.add(relationship)

    @staticmethod
    async def increase_affinity(
        db_session: AsyncSession,
        dweller_1_id: UUID,
        dweller_2_id: UUID,
        amount: int = 1,
        *,
        relationship: Relationship | None = None,
        commit: bool = True,
    ) -> Relationship:
        """Increase affinity between two dwellers.

        Args:
            db_session: Database session
            dweller_1_id: First dweller ID
            dweller_2_id: Second dweller ID
            amount: Affinity increase amount
            relationship: Already-loaded relationship, avoiding a pair lookup
            commit: Whether to commit; pass False to let the caller own the transaction

        Returns:
            Updated relationship
        """
        if relationship is None:
            relationship = await relationship_crud.get_by_dweller_pair(db_session, dweller_1_id, dweller_2_id)
        if not relationship:
            msg = "Relationship not found between dwellers"
            raise ValueError(msg)

        new_affinity = min(100, relationship.affinity + amount)
        update_data = {"affinity": new_affinity, "updated_at": utcnow()}
        old_type = relationship.relationship_type
        current_type = old_type

        if (
            current_type == RelationshipTypeEnum.RIVAL
            and new_affinity >= game_config.relationship.rival_recovery_threshold
        ):
            update_data["relationship_type"] = RelationshipTypeEnum.ACQUAINTANCE
            current_type = RelationshipTypeEnum.ACQUAINTANCE

        # Auto-upgrade relationship based on affinity thresholds
        if update_data["affinity"] >= game_config.relationship.romance_threshold:
            # Progress through relationship stages
            if current_type == RelationshipTypeEnum.ACQUAINTANCE:
                update_data["relationship_type"] = RelationshipTypeEnum.FRIEND
            elif current_type == RelationshipTypeEnum.FRIEND:
                update_data["relationship_type"] = RelationshipTypeEnum.ROMANTIC
            elif current_type == RelationshipTypeEnum.ROMANTIC:
                # Skip the promotion if either dweller is already committed to a
                # third dweller (game-loop tick path: log and keep ROMANTIC rather
                # than raising, which would break the vault). Lock both dweller
                # rows first so a concurrent manual make_partners cannot race the
                # guard (the tick holds a per-vault advisory lock, endpoints do not).
                await db_session.flush()
                await RelationshipService._lock_dwellers(
                    db_session, relationship.dweller_1_id, relationship.dweller_2_id
                )
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
        committed = False
        if is_marriage_transition:
            # Defense-in-depth: skip the transition if either dweller is already
            # committed to a third dweller (pre-existing corrupt data). Log and
            # persist only the affinity bump rather than raising. Lock both
            # dweller rows first so a concurrent manual make_partners cannot race
            # the guard (the tick holds a per-vault advisory lock, endpoints do not).
            await db_session.flush()
            await RelationshipService._lock_dwellers(db_session, relationship.dweller_1_id, relationship.dweller_2_id)
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
                RelationshipService._stage_update(db_session, relationship, update_data)
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
                committed = True
            else:
                # Lost the race (already not PARTNER): just persist the affinity bump.
                RelationshipService._stage_update(db_session, relationship, update_data)
        else:
            RelationshipService._stage_update(db_session, relationship, update_data)

        if commit and not committed:
            await db_session.commit()

        logger.debug(
            f"Affinity increased {dweller_1_id} ↔ {dweller_2_id}: {old_type} → {relationship.relationship_type}"
        )
        return relationship

    @staticmethod
    async def decrease_affinity(
        db_session: AsyncSession,
        dweller_1_id: UUID,
        dweller_2_id: UUID,
        amount: int,
        *,
        relationship: Relationship | None = None,
        commit: bool = True,
    ) -> Relationship:
        """Lower affinity; non-committed stages can demote into rivalry.

        PARTNER and MARRIED links survive any affinity drop and end only through
        ``break_up``. Relationship changes stay silent; a first rivalry is
        narrated into both bios instead of the notification bell.
        """
        if amount <= 0:
            msg = "Affinity decrease amount must be positive"
            raise ValueError(msg)
        if relationship is None:
            relationship = await relationship_crud.get_by_dweller_pair(db_session, dweller_1_id, dweller_2_id)
        if not relationship:
            msg = "Relationship not found between dwellers"
            raise ValueError(msg)

        config = game_config.relationship
        floor = 0 if relationship.relationship_type in PARTNER_LINKED_STAGES else _AFFINITY_MIN
        new_affinity = max(floor, relationship.affinity - amount)
        demoted_from = relationship.relationship_type
        demoted_to = RelationshipService._demotion_for(demoted_from, new_affinity)

        update_data = {"affinity": new_affinity, "updated_at": utcnow()}
        if demoted_to is not None:
            update_data["relationship_type"] = demoted_to
        RelationshipService._stage_update(db_session, relationship, update_data)
        if demoted_to == RelationshipTypeEnum.RIVAL:
            await RelationshipService._record_rival_bios(db_session, relationship)

        if commit:
            await db_session.commit()

        logger.debug(
            f"Affinity decreased {dweller_1_id} ↔ {dweller_2_id}: {demoted_from} → {demoted_to or demoted_from}"
        )
        return relationship

    @staticmethod
    def _demotion_for(current: RelationshipTypeEnum, new_affinity: int) -> RelationshipTypeEnum | None:
        config = game_config.relationship
        if current in PARTNER_LINKED_STAGES or current in {RelationshipTypeEnum.RIVAL, RelationshipTypeEnum.EX}:
            return None
        if new_affinity < 0:
            return RelationshipTypeEnum.RIVAL
        if current == RelationshipTypeEnum.ROMANTIC and new_affinity < config.romantic_demotion_threshold:
            return RelationshipTypeEnum.FRIEND
        if current == RelationshipTypeEnum.FRIEND and new_affinity < config.friend_demotion_threshold:
            return RelationshipTypeEnum.ACQUAINTANCE
        return None

    @staticmethod
    async def _record_rival_bios(db_session: AsyncSession, relationship: Relationship) -> None:
        """Stage a first rivalry into both dwellers' bios inside the caller's transaction."""
        try:
            first = await dweller_crud.get(db_session, relationship.dweller_1_id)
            second = await dweller_crud.get(db_session, relationship.dweller_2_id)
        except ResourceNotFoundException:
            logger.warning("Skipping rivalry bio for relationship %s: a dweller is missing", relationship.id)
            return
        name_1 = f"{first.first_name} {first.last_name or ''}".strip()
        name_2 = f"{second.first_name} {second.last_name or ''}".strip()
        bio_service.add_entry(first, "family", f"Can't stand {name_2}.", ref={"rival_id": str(second.id)})
        bio_service.add_entry(second, "family", f"Can't stand {name_1}.", ref={"rival_id": str(first.id)})

    @staticmethod
    async def _require_social_action(db_session: AsyncSession, dweller_ids: tuple[UUID, UUID]) -> None:
        """Reject romance/partnership when either dweller cannot take purposeful social action."""
        for dweller_id in dweller_ids:
            dweller = await dweller_crud.get(db_session, dweller_id)
            if error := purposeful_action_error(dweller, DwellerAction.SOCIAL):
                raise ValidationException(detail=f"Dweller {dweller_id} {error}")

    @staticmethod
    async def initiate_romance(
        db_session: AsyncSession,
        dweller_1_id: UUID,
        dweller_2_id: UUID,
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

        await RelationshipService._require_social_action(db_session, (dweller_1_id, dweller_2_id))

        if relationship.affinity < game_config.relationship.romance_threshold:
            msg = (
                f"Affinity too low for romance ({relationship.affinity} < {game_config.relationship.romance_threshold})"
            )
            raise ValueError(msg)

        update_data = {"relationship_type": RelationshipTypeEnum.ROMANTIC, "updated_at": utcnow()}

        # Update via CRUD
        relationship = await relationship_crud.update(db_session, relationship.id, update_data)

        logger.info(f"Romance initiated {dweller_1_id} ↔ {dweller_2_id}")
        return relationship

    @staticmethod
    async def make_partners(
        db_session: AsyncSession,
        dweller_1_id: UUID,
        dweller_2_id: UUID,
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

        await RelationshipService._require_social_action(db_session, (dweller_1_id, dweller_2_id))

        if relationship.affinity < game_config.relationship.romance_threshold:
            threshold = game_config.relationship.romance_threshold
            msg = f"Affinity too low for partnership ({relationship.affinity} < {threshold})"
            raise ValueError(msg)

        # Serialize concurrent commitment transitions: lock both dweller rows
        # before the guard so two racing make_partners calls cannot both pass it.
        await RelationshipService._lock_dwellers(db_session, dweller_1_id, dweller_2_id)

        # Guard: neither dweller may already be committed to a third dweller.
        for dweller_id in (dweller_1_id, dweller_2_id):
            committed = await RelationshipService._committed_partner_elsewhere(
                db_session, dweller_id, except_ids={dweller_1_id, dweller_2_id}
            )
            if committed is not None:
                msg = f"Dweller {dweller_id} is already {committed.relationship_type.value} to another dweller"
                raise ValidationException(msg)

        update_data = {"relationship_type": RelationshipTypeEnum.PARTNER, "updated_at": utcnow()}

        # Update relationship and both dwellers' partner_ids in ONE transaction.
        relationship = await relationship_crud.update(db_session, relationship.id, update_data, commit=False)
        await RelationshipService._set_partner_ids(db_session, dweller_1_id, dweller_2_id)
        await db_session.commit()

        logger.info(f"Partners made: {dweller_1_id} ↔ {dweller_2_id}")
        return relationship

    @staticmethod
    async def _set_partner_ids(
        db_session: AsyncSession,
        dweller_1_id: UUID,
        dweller_2_id: UUID,
    ) -> None:
        """Stage reciprocal partner_ids on both dwellers.

        No commit: the caller owns the transaction, so the relationship row and both
        dweller links land together (a failure between them cannot split the pair).
        """
        dweller_1 = await dweller_crud.get(db_session, dweller_1_id)
        dweller_2 = await dweller_crud.get(db_session, dweller_2_id)

        dweller_1.partner_id = dweller_2_id
        dweller_2.partner_id = dweller_1_id

        db_session.add(dweller_1)
        db_session.add(dweller_2)

    @staticmethod
    async def _lock_dwellers(db_session: AsyncSession, id_a: UUID, id_b: UUID) -> None:
        """Lock both dweller rows FOR UPDATE in deterministic id order.

        Serializes concurrent commitment transitions (make_partners / marry /
        affinity auto-promotion) so the ``_committed_partner_elsewhere`` guard
        cannot be raced by two requests both passing it. Locks are held until
        the caller's next commit/rollback; SQLite test engines ignore FOR
        UPDATE, PostgreSQL enforces it in production.
        """
        for dweller_id in sorted((id_a, id_b), key=str):
            await dweller_crud.get_for_update(db_session, dweller_id)

    @staticmethod
    async def _committed_partner_elsewhere(
        db_session: AsyncSession,
        dweller_id: UUID,
        except_ids: set[UUID],
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
        dweller_1_id: UUID,
        dweller_2_id: UUID,
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
    async def marry(db_session: AsyncSession, relationship_id: UUID) -> Relationship:
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

        await RelationshipService._require_social_action(
            db_session, (relationship.dweller_1_id, relationship.dweller_2_id)
        )

        # Serialize concurrent commitment transitions: lock both dweller rows
        # before the guard so a racing make_partners/affinity promotion cannot
        # slip a second commitment in between the guard and the transition.
        await RelationshipService._lock_dwellers(db_session, relationship.dweller_1_id, relationship.dweller_2_id)

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
        relationship_id: UUID,
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

        # If partners or married, clear partner_id on both dwellers
        dweller_1 = dweller_2 = None
        if relationship.relationship_type in PARTNER_LINKED_STAGES:
            try:
                dweller_1 = await dweller_crud.get(db_session, relationship.dweller_1_id)
                dweller_2 = await dweller_crud.get(db_session, relationship.dweller_2_id)

                # Clear partner_id in memory
                dweller_1.partner_id = None
                dweller_2.partner_id = None

                # Add both to session
                db_session.add(dweller_1)
                db_session.add(dweller_2)
            except ResourceNotFoundException:
                # One or both dwellers may have been deleted, continue with breakup
                pass
            except Exception:
                # Roll back, then let the driver error surface as a server error:
                # wrapping it in ValueError made the API report a client error and
                # leak the database message.
                await db_session.rollback()
                raise

        update_data = {
            "relationship_type": RelationshipTypeEnum.EX,
            "affinity": max(0, relationship.affinity - 30),  # Penalty for breakup
            "updated_at": utcnow(),
        }
        await relationship_crud.update(db_session, relationship.id, update_data, commit=False)

        await db_session.commit()

        if dweller_1 is not None:
            await db_session.refresh(dweller_1)
        if dweller_2 is not None:
            await db_session.refresh(dweller_2)
        await db_session.refresh(relationship)

        logger.info(f"Break up: {relationship.dweller_1_id} and {relationship.dweller_2_id}")

    @staticmethod
    async def calculate_compatibility_score(
        db_session: AsyncSession,
        dweller_1_id: UUID,
        dweller_2_id: UUID,
    ) -> CompatibilityScore:
        """Calculate compatibility score between two dwellers.

        Raises:
            ResourceNotFoundException: If either dweller is not found (propagates as HTTP 404)
        """
        # Let ResourceNotFoundException propagate directly (HTTP 404)
        dweller_1 = await dweller_crud.get(db_session, dweller_1_id)
        dweller_2 = await dweller_crud.get(db_session, dweller_2_id)
        parts = compatibility_components(dweller_1, dweller_2)

        return CompatibilityScore(
            dweller_1_id=dweller_1_id,
            dweller_2_id=dweller_2_id,
            score=parts.score,
            special_score=parts.special_score,
            happiness_score=parts.happiness_score,
            level_score=parts.level_score,
            proximity_score=parts.proximity_score,
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
