"""Service for managing dweller breeding, pregnancy, and child growth."""

import logging
import random
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config.game_balance import (
    CHILD_GROWTH_DURATION_HOURS,
    CHILD_SPECIAL_MULTIPLIER,
    CONCEPTION_CHANCE_PER_TICK,
    PREGNANCY_DURATION_HOURS,
    RARITY_INHERITANCE_UPGRADE_CHANCE,
    TRAIT_INHERITANCE_VARIANCE,
)
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

logger = logging.getLogger(__name__)


class BreedingService:
    """Service for managing breeding, pregnancy, and child growth."""

    @staticmethod
    async def check_for_conception(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list[Pregnancy]:
        """
        Check all partner pairs in living quarters and roll for conception.

        Args:
            db_session: Database session
            vault_id: Vault ID to check

        Returns:
            List of newly created pregnancies
        """
        # Find all dwellers in living quarters
        living_quarters_query = (
            select(Room).where(Room.vault_id == vault_id).where(Room.category == RoomTypeEnum.CAPACITY)
        )
        living_quarters = (await db_session.execute(living_quarters_query)).scalars().all()

        if not living_quarters:
            return []

        living_quarters_ids = [room.id for room in living_quarters]

        # Find all dwellers with partners in living quarters
        dwellers_query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(Dweller.partner_id.is_not(None))
            .where(Dweller.room_id.in_(living_quarters_ids))
            .where(Dweller.age_group == AgeGroupEnum.ADULT)
        )
        dwellers = (await db_session.execute(dwellers_query)).scalars().all()

        # Check existing pregnancies to avoid duplicates
        existing_pregnancies_query = select(Pregnancy.mother_id).where(Pregnancy.status == PregnancyStatusEnum.PREGNANT)
        pregnant_mother_ids = set((await db_session.execute(existing_pregnancies_query)).scalars().all())

        new_pregnancies = []
        checked_pairs = set()

        for dweller in dwellers:
            # Skip if already pregnant
            if dweller.gender == GenderEnum.FEMALE and dweller.id in pregnant_mother_ids:
                continue

            # Skip if partner is already pregnant
            if dweller.partner_id in pregnant_mother_ids:
                continue

            # Avoid checking same pair twice
            pair_key = tuple(sorted([str(dweller.id), str(dweller.partner_id)]))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            # Get partner
            partner_query = select(Dweller).where(Dweller.id == dweller.partner_id)
            partner = (await db_session.execute(partner_query)).scalars().first()

            if not partner:
                continue

            # Check if partner is also in living quarters
            if partner.room_id not in living_quarters_ids:
                continue

            # Check if partner is adult
            if partner.age_group != AgeGroupEnum.ADULT:
                continue

            # Roll for conception
            if random.random() < CONCEPTION_CHANCE_PER_TICK:
                # Determine mother and father
                if dweller.gender == GenderEnum.FEMALE:
                    mother_id = dweller.id
                    father_id = partner.id
                else:
                    mother_id = partner.id
                    father_id = dweller.id

                # Create pregnancy
                pregnancy = await BreedingService.create_pregnancy(
                    db_session,
                    mother_id,
                    father_id,
                )
                new_pregnancies.append(pregnancy)
                logger.info(f"Conception: Mother={mother_id}, Father={father_id}")  # noqa: G004

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
        conceived_at = datetime.utcnow()
        due_at = conceived_at + timedelta(hours=PREGNANCY_DURATION_HOURS)

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

        logger.info(f"Created pregnancy: Mother={mother_id}, Father={father_id}, Due at {due_at.isoformat()}")  # noqa: G004

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
            .where(Pregnancy.due_at <= datetime.utcnow())
        )

        pregnancies = (await db_session.execute(query)).scalars().all()
        return pregnancies  # noqa: RET504

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

        # Create child dweller
        from app import crud

        child_data = {
            "first_name": first_name,
            "last_name": last_name,
            "gender": child_gender,
            "rarity": child_rarity,
            "age_group": AgeGroupEnum.CHILD,
            "birth_date": datetime.utcnow(),
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
        await db_session.commit()
        await db_session.refresh(child)

        # Update pregnancy status
        pregnancy.status = PregnancyStatusEnum.DELIVERED
        pregnancy.updated_at = datetime.utcnow()
        await db_session.commit()
        await db_session.refresh(pregnancy)

        logger.info(f"Baby delivered: {child.first_name} {child.last_name}, Mother={mother.id}, Father={father.id}")  # noqa: G004

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
            variance = random.randint(-TRAIT_INHERITANCE_VARIANCE, TRAIT_INHERITANCE_VARIANCE)
            child_stat = avg_stat + variance

            # Apply child multiplier and clamp to 1-10
            child_stat = int(child_stat * CHILD_SPECIAL_MULTIPLIER)
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
        if random.random() < RARITY_INHERITANCE_UPGRADE_CHANCE and base_rarity_idx < len(rarity_order) - 1:
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
        growth_threshold = datetime.utcnow() - timedelta(hours=CHILD_GROWTH_DURATION_HOURS)

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
                adult_stat = int(current_stat / CHILD_SPECIAL_MULTIPLIER)
                adult_stat = max(1, min(10, adult_stat))
                setattr(child, attr, adult_stat)

            child.updated_at = datetime.utcnow()
            aged_dwellers.append(child)

            logger.info(f"Child aged to adult: {child.first_name} {child.last_name} ({child.id})")  # noqa: G004

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

        pregnancies = (await db_session.execute(query)).scalars().all()
        return pregnancies  # noqa: RET504


breeding_service = BreedingService()
