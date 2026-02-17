"""Service for managing dweller breeding, pregnancy, and child growth."""

import html
import logging
import random
from datetime import UTC, datetime, timedelta

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.pregnancy import Pregnancy
from app.models.room import Room
from app.schemas.common import (
    AgeGroupEnum,
    GenderEnum,
    PregnancyStatusEnum,
    RarityEnum,
    RoomTypeEnum,
)
from app.schemas.dweller import DwellerCreate
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# Random event templates for newborn bios (100-200 chars)
NEWBORN_BIO_TEMPLATES = [
    "Born during a {event}. {mother} and {father} couldn't be prouder.",
    "Arrived during {event}. The vault celebrates this new life.",
    "Entered the world during {event}. A blessing for {mother} and {father}.",
    "Born under {event}. {father} and {mother} welcome their bundle of joy.",
    "Came into existence during {event}. A new hope for the vault.",
    "Born during {event}. {mother} and {father} are overjoyed.",
    "First cry echoed through the vault during {event}. Precious to {mother} and {father}.",
    "Entered the shelter during {event}. {father} and {mother} celebrate.",
    "Born amidst {event}. A miracle for {mother} and {father}.",
    "Came from {mother} and {father} during {event}. The vault grows.",
]

NEWBORN_EVENTS = [
    "a quiet night",
    "a vault celebration",
    "a rad-storm",
    "an emergency drill",
    "a power outage",
    "the weekly ration distribution",
    "a radio broadcast",
    "the morning shift change",
    "a rare sunny day",
    "the lunch hour",
    "the night watch",
    "a calm afternoon",
    "the vault door sealing",
    "a happiness surge",
    "the quarterly inventory",
]


def _generate_newborn_bio(mother_name: str, father_name: str, mother_id: str, father_id: str, vault_id: str) -> str:
    template = random.choice(NEWBORN_BIO_TEMPLATES)
    event = random.choice(NEWBORN_EVENTS)

    # Truncate names to a safe max length before escaping
    max_name_len = 30
    safe_mother_name = html.escape(mother_name[:max_name_len])
    safe_father_name = html.escape(father_name[:max_name_len])

    mother_link = f'<a href="/vault/{vault_id}/dwellers/{mother_id}" class="dweller-link">{safe_mother_name}</a>'
    father_link = f'<a href="/vault/{vault_id}/dwellers/{father_id}" class="dweller-link">{safe_father_name}</a>'

    bio = template.format(mother=mother_link, father=father_link, event=event)

    if len(bio) > 200:
        bio = bio[:197] + "..."

    return bio


class BreedingService:
    """Service for managing breeding, pregnancy, and child growth."""

    @staticmethod
    async def _get_living_quarters(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list[Room]:
        """
        Find all living quarters rooms for a vault.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param vault_id: Vault ID to search
        :type vault_id: UUID4
        :returns: List of living quarters rooms
        :rtype: list[Room]
        """
        query = select(Room).where(Room.vault_id == vault_id).where(Room.category == RoomTypeEnum.CAPACITY)
        return list((await db_session.execute(query)).scalars().all())

    @staticmethod
    async def _get_eligible_dwellers(
        db_session: AsyncSession,
        vault_id: UUID4,
        living_quarters_ids: list[UUID4],
    ) -> list[Dweller]:
        """
        Find all adult dwellers with partners in living quarters.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param vault_id: Vault ID to search
        :type vault_id: UUID4
        :param living_quarters_ids: List of living quarters room IDs
        :type living_quarters_ids: list[UUID4]
        :returns: List of eligible dwellers
        :rtype: list[Dweller]
        """
        query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(Dweller.partner_id.is_not(None))
            .where(Dweller.room_id.in_(living_quarters_ids))
            .where(Dweller.age_group == AgeGroupEnum.ADULT)
        )
        return list((await db_session.execute(query)).scalars().all())

    @staticmethod
    async def _get_pregnant_mother_ids(db_session: AsyncSession) -> set[UUID4]:
        """
        Get set of currently pregnant mother IDs.

        :param db_session: Database session
        :type db_session: AsyncSession
        :returns: Set of mother IDs with active pregnancies
        :rtype: set[UUID4]
        """
        query = select(Pregnancy.mother_id).where(Pregnancy.status == PregnancyStatusEnum.PREGNANT)
        return set((await db_session.execute(query)).scalars().all())

    @staticmethod
    def _is_pair_eligible(
        dweller: Dweller,
        pregnant_mother_ids: set[UUID4],
        checked_pairs: set[tuple[str, str]],
    ) -> bool:
        """
        Check if a dweller-partner pair is eligible for conception check.

        :param dweller: Dweller to check
        :type dweller: Dweller
        :param pregnant_mother_ids: Set of currently pregnant mother IDs
        :type pregnant_mother_ids: set[UUID4]
        :param checked_pairs: Set of already checked pair keys
        :type checked_pairs: set[tuple[str, str]]
        :returns: True if pair is eligible for conception check
        :rtype: bool
        """
        # Skip if dweller is female and already pregnant
        if dweller.gender == GenderEnum.FEMALE and dweller.id in pregnant_mother_ids:
            return False

        # Skip if partner is already pregnant
        if dweller.partner_id in pregnant_mother_ids:
            return False

        # Avoid checking same pair twice
        pair_key = tuple(sorted([str(dweller.id), str(dweller.partner_id)]))
        return pair_key not in checked_pairs

    @staticmethod
    async def _get_relationship_affinity(
        db_session: AsyncSession,
        dweller: Dweller,
        partner: Dweller,
    ) -> float:
        """
        Get relationship affinity and calculate conception chance.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param dweller: First dweller in the pair
        :type dweller: Dweller
        :param partner: Partner dweller
        :type partner: Dweller
        :returns: Conception chance as decimal (0.0 to 1.0)
        :rtype: float
        """
        from app.models.relationship import Relationship

        query = select(Relationship).where(
            ((Relationship.dweller_1_id == dweller.id) & (Relationship.dweller_2_id == partner.id))
            | ((Relationship.dweller_1_id == partner.id) & (Relationship.dweller_2_id == dweller.id))
        )
        relationship = (await db_session.execute(query)).scalars().first()

        # Calculate conception chance based on affinity (1% per affinity point)
        # If no relationship found, use base chance
        if relationship:
            return relationship.affinity / 100.0  # 90 affinity = 90% chance
        return game_config.breeding.conception_chance_per_tick  # Fallback to base 2%

    @staticmethod
    async def _roll_for_conception(
        db_session: AsyncSession,
        dweller: Dweller,
        partner: Dweller,
        conception_chance: float,
    ) -> Pregnancy | None:
        """
        Roll random chance and create pregnancy if successful.

        :param db_session: Database session
        :type db_session: AsyncSession
        :param dweller: First dweller in the pair
        :type dweller: Dweller
        :param partner: Partner dweller
        :type partner: Dweller
        :param conception_chance: Probability of conception (0.0 to 1.0)
        :type conception_chance: float
        :returns: Created pregnancy if successful, None otherwise
        :rtype: Pregnancy | None
        """
        roll = random.random()
        if roll >= conception_chance:
            return None

        # Determine mother and father
        if dweller.gender == GenderEnum.FEMALE:
            mother_id = dweller.id
            father_id = partner.id
        else:
            mother_id = partner.id
            father_id = dweller.id

        # Create pregnancy
        pregnancy = await BreedingService.create_pregnancy(db_session, mother_id, father_id)
        logger.info(f"Conception with {conception_chance * 100:.0f}% chance: Mother={mother_id}, Father={father_id}")
        return pregnancy

    @staticmethod
    async def check_for_conception(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list[Pregnancy]:
        """
        Check all partner pairs in living quarters and roll for conception.

        :param db_session: Database session
        :param vault_id: Vault ID to check
        :returns: List of newly created pregnancies
        """
        living_quarters = await BreedingService._get_living_quarters(db_session, vault_id)
        if not living_quarters:
            return []

        living_quarters_ids = [room.id for room in living_quarters]
        dwellers = await BreedingService._get_eligible_dwellers(db_session, vault_id, living_quarters_ids)
        pregnant_mother_ids = await BreedingService._get_pregnant_mother_ids(db_session)

        new_pregnancies: list[Pregnancy] = []
        checked_pairs: set[tuple[str, str]] = set()

        for dweller in dwellers:
            if not BreedingService._is_pair_eligible(dweller, pregnant_mother_ids, checked_pairs):
                continue

            pair_key = tuple(sorted([str(dweller.id), str(dweller.partner_id)]))
            checked_pairs.add(pair_key)

            partner_query = select(Dweller).where(Dweller.id == dweller.partner_id)
            partner = (await db_session.execute(partner_query)).scalars().first()

            if not partner or partner.room_id not in living_quarters_ids or partner.age_group != AgeGroupEnum.ADULT:
                continue

            conception_chance = await BreedingService._get_relationship_affinity(db_session, dweller, partner)
            pregnancy = await BreedingService._roll_for_conception(db_session, dweller, partner, conception_chance)

            if pregnancy:
                new_pregnancies.append(pregnancy)

        return new_pregnancies

    @staticmethod
    async def create_pregnancy(
        db_session: AsyncSession,
        mother_id: UUID4,
        father_id: UUID4,
    ) -> Pregnancy:
        """
        Create a new pregnancy record.

        Args:
            db_session: Database session
            mother_id: Mother dweller ID
            father_id: Father dweller ID

        Returns:
            Created pregnancy
        """
        # NOTE: Using naive datetime to match database TIMESTAMP WITHOUT TIME ZONE
        conceived_at = datetime.now(UTC).replace(tzinfo=None)
        due_at = conceived_at + timedelta(hours=game_config.breeding.pregnancy_duration_hours)

        pregnancy = Pregnancy(
            mother_id=mother_id,
            father_id=father_id,
            conceived_at=conceived_at,
            due_at=due_at,
            status=PregnancyStatusEnum.PREGNANT,
        )

        db_session.add(pregnancy)
        await db_session.commit()
        await db_session.refresh(pregnancy)

        logger.info(f"Created pregnancy: Mother={mother_id}, Father={father_id}, Due at {due_at.isoformat()}")

        return pregnancy

    @staticmethod
    async def check_due_pregnancies(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list[Pregnancy]:
        """
        Find all pregnancies that are due for delivery.

        Args:
            db_session: Database session
            vault_id: Vault ID to check

        Returns:
            List of due pregnancies
        """
        query = (
            select(Pregnancy)
            .join(Dweller, Pregnancy.mother_id == Dweller.id)
            .where(Dweller.vault_id == vault_id)
            .where(Pregnancy.status == PregnancyStatusEnum.PREGNANT)
            .where(Pregnancy.due_at <= datetime.now(UTC).replace(tzinfo=None))
        )

        return (await db_session.execute(query)).scalars().all()

    @staticmethod
    async def deliver_baby(
        db_session: AsyncSession,
        pregnancy_id: UUID4,
    ) -> Dweller:
        """
        Deliver a baby from a pregnancy.

        Args:
            db_session: Database session
            pregnancy_id: Pregnancy ID

        Returns:
            Newly created child dweller

        Raises:
            ValueError: If pregnancy not found or not due
        """
        # Get pregnancy
        pregnancy_query = select(Pregnancy).where(Pregnancy.id == pregnancy_id)
        pregnancy = (await db_session.execute(pregnancy_query)).scalars().first()

        if not pregnancy:
            msg = "Pregnancy not found"
            raise ValueError(msg)

        if not pregnancy.is_due:
            msg = "Pregnancy is not due yet"
            raise ValueError(msg)

        # Get parents
        mother_query = select(Dweller).where(Dweller.id == pregnancy.mother_id)
        father_query = select(Dweller).where(Dweller.id == pregnancy.father_id)

        mother = (await db_session.execute(mother_query)).scalars().first()
        father = (await db_session.execute(father_query)).scalars().first()

        if not mother or not father:
            msg = "Parent dwellers not found"
            raise ValueError(msg)

        # Calculate inherited traits
        child_stats = BreedingService._calculate_inherited_stats(mother, father)
        child_rarity = BreedingService._calculate_inherited_rarity(mother, father)
        child_gender = random.choice(list(GenderEnum))

        # Generate name (simplified - take from mother or father)
        first_name = random.choice([mother.first_name, father.first_name])
        last_name = mother.last_name  # Use mother's last name by default

        # Create a child dweller
        from app import crud

        child_data = {
            "first_name": first_name,
            "last_name": last_name,
            "gender": child_gender,
            "rarity": child_rarity,
            "age_group": AgeGroupEnum.CHILD,
            "birth_date": datetime.now(UTC).replace(tzinfo=None),
            "level": 1,
            "experience": 0,
            "max_health": 100,
            "health": 100,
            "radiation": 0,
            "happiness": 50,
            **child_stats,
        }

        child_in = DwellerCreate(**child_data, vault_id=mother.vault_id)
        child = await crud.dweller.create(db_session=db_session, obj_in=child_in)

        # Set parent IDs (not part of DwellerCreate schema)
        child.parent_1_id = mother.id
        child.parent_2_id = father.id

        newborn_bio = _generate_newborn_bio(
            mother.first_name,
            father.first_name,
            str(mother.id),
            str(father.id),
            str(mother.vault_id),
        )
        child.bio = newborn_bio
        logger.info(f"Generated newborn bio for {child.first_name}: {newborn_bio[:50]}...")

        await db_session.commit()
        await db_session.refresh(child)
        logger.info(f"Baby delivered with bio: {child.bio is not None}")

        # Update pregnancy status
        pregnancy.status = PregnancyStatusEnum.DELIVERED
        pregnancy.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await db_session.commit()
        await db_session.refresh(pregnancy)

        logger.info(f"Baby delivered: {child.first_name} {child.last_name}, Mother={mother.id}, Father={father.id}")

        # Increment birth statistics for the vault owner (best-effort, don't fail birth on stats error)
        try:
            from app.crud.user_profile import profile_crud
            from app.crud.vault import vault as vault_crud

            vault = await vault_crud.get(db_session, mother.vault_id)
            if vault and vault.user_id:
                await profile_crud.increment_statistic(db_session, vault.user_id, "total_dwellers_born")

                # Broadcast via standard notification system
                await notification_service.notify_baby_born(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=mother.vault_id,
                    mother_id=mother.id,
                    mother_name=f"{mother.first_name} {mother.last_name or ''}".strip(),
                    baby_name=f"{child.first_name} {child.last_name or ''}".strip(),
                    meta_data={"child_id": str(child.id), "mother_id": str(mother.id)},
                )
        except Exception:
            logger.exception("Failed to increment birth statistics for vault %s", mother.vault_id)

        return child

    @staticmethod
    def _calculate_inherited_stats(mother: Dweller, father: Dweller) -> dict:
        """
        Calculate child's inherited SPECIAL stats.

        Args:
            mother: Mother dweller
            father: Father dweller

        Returns:
            Dictionary of SPECIAL stats for child
        """
        special_attrs = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]

        child_stats = {}
        for attr in special_attrs:
            mother_stat = getattr(mother, attr, 1)
            father_stat = getattr(father, attr, 1)

            # Average of parents
            avg_stat = (mother_stat + father_stat) / 2

            # Add variance
            variance = random.randint(
                -game_config.breeding.trait_inheritance_variance, game_config.breeding.trait_inheritance_variance
            )
            child_stat = avg_stat + variance

            # Apply child multiplier and clamp to 1-10
            child_stat = int(child_stat * game_config.breeding.child_special_multiplier)
            child_stat = max(1, min(10, child_stat))

            child_stats[attr] = child_stat

        return child_stats

    @staticmethod
    def _calculate_inherited_rarity(mother: Dweller, father: Dweller) -> RarityEnum:
        """
        Calculate child's inherited rarity.

        Args:
            mother: Mother dweller
            father: Father dweller

        Returns:
            Rarity enum for child
        """
        # Get highest parent rarity
        rarity_order = [RarityEnum.COMMON, RarityEnum.RARE, RarityEnum.LEGENDARY]

        mother_rarity_idx = rarity_order.index(mother.rarity)
        father_rarity_idx = rarity_order.index(father.rarity)

        base_rarity_idx = max(mother_rarity_idx, father_rarity_idx)

        # Chance to upgrade rarity
        if random.random() < game_config.breeding.rarity_upgrade_chance and base_rarity_idx < len(rarity_order) - 1:
            base_rarity_idx += 1

        return rarity_order[base_rarity_idx]

    @staticmethod
    async def age_children(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list[Dweller]:
        """
        Age children to adults if they've reached the growth duration.

        Args:
            db_session: Database session
            vault_id: Vault ID to check

        Returns:
            List of aged dwellers
        """
        growth_threshold = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            hours=game_config.breeding.child_growth_duration_hours
        )

        query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(Dweller.age_group == AgeGroupEnum.CHILD)
            .where(Dweller.birth_date.is_not(None))
            .where(Dweller.birth_date <= growth_threshold)
        )

        children = (await db_session.execute(query)).scalars().all()

        aged_dwellers = []
        for child in children:
            # Age to adult
            child.age_group = AgeGroupEnum.ADULT

            # Scale up SPECIAL stats (remove child multiplier)
            special_attrs = ["strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck"]
            for attr in special_attrs:
                current_stat = getattr(child, attr, 1)
                adult_stat = int(current_stat / game_config.breeding.child_special_multiplier)
                adult_stat = max(1, min(10, adult_stat))
                setattr(child, attr, adult_stat)

            child.updated_at = datetime.now(UTC).replace(tzinfo=None)
            aged_dwellers.append(child)

            logger.info(f"Child aged to adult: {child.first_name} {child.last_name} ({child.id})")

        await db_session.commit()

        for dweller in aged_dwellers:
            await db_session.refresh(dweller)

        return aged_dwellers

    @staticmethod
    async def get_active_pregnancies(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list[Pregnancy]:
        """
        Get all active pregnancies for a vault.

        Args:
            db_session: Database session
            vault_id: Vault ID

        Returns:
            List of active pregnancies
        """
        query = (
            select(Pregnancy)
            .join(Dweller, Pregnancy.mother_id == Dweller.id)
            .where(Dweller.vault_id == vault_id)
            .where(Pregnancy.status == PregnancyStatusEnum.PREGNANT)
        )

        return (await db_session.execute(query)).scalars().all()

    @staticmethod
    async def force_conception(
        db_session: AsyncSession,
        mother_id: UUID4,
        father_id: UUID4,
    ) -> Pregnancy:
        mother_query = select(Dweller).where(Dweller.id == mother_id)
        mother = (await db_session.execute(mother_query)).scalars().first()

        if not mother:
            msg = "Mother not found"
            raise ValueError(msg)

        if mother.gender != GenderEnum.FEMALE:
            msg = "Mother must be female"
            raise ValueError(msg)

        if mother.age_group != AgeGroupEnum.ADULT:
            msg = "Mother must be adult"
            raise ValueError(msg)

        father_query = select(Dweller).where(Dweller.id == father_id)
        father = (await db_session.execute(father_query)).scalars().first()

        if not father:
            msg = "Father not found"
            raise ValueError(msg)

        if father.gender != GenderEnum.MALE:
            msg = "Father must be male"
            raise ValueError(msg)

        if father.age_group != AgeGroupEnum.ADULT:
            msg = "Father must be adult"
            raise ValueError(msg)

        existing_query = select(Pregnancy).where(
            Pregnancy.mother_id == mother_id,
            Pregnancy.status == PregnancyStatusEnum.PREGNANT,
        )
        existing = (await db_session.execute(existing_query)).scalars().first()

        if existing:
            msg = "Mother is already pregnant"
            raise ValueError(msg)

        return await BreedingService.create_pregnancy(db_session, mother_id, father_id)

    @staticmethod
    async def accelerate_pregnancy(
        db_session: AsyncSession,
        pregnancy_id: UUID4,
    ) -> Pregnancy:
        query = select(Pregnancy).where(Pregnancy.id == pregnancy_id)
        pregnancy = (await db_session.execute(query)).scalars().first()

        if not pregnancy:
            msg = "Pregnancy not found"
            raise ValueError(msg)

        if pregnancy.status != PregnancyStatusEnum.PREGNANT:
            msg = "Pregnancy is not active"
            raise ValueError(msg)

        pregnancy.due_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        pregnancy.updated_at = datetime.now(UTC).replace(tzinfo=None)

        await db_session.commit()
        await db_session.refresh(pregnancy)

        return pregnancy


breeding_service = BreedingService()
