"""Service for managing dweller breeding, pregnancy, and child growth."""

import html
import logging
import random
from datetime import UTC, datetime, timedelta

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud import vault as vault_crud
from app.crud.dweller import dweller as dweller_crud
from app.crud.pregnancy import pregnancy as pregnancy_crud
from app.crud.room import room as room_crud
from app.models.dweller import Dweller
from app.models.pregnancy import Pregnancy
from app.models.vault import Vault
from app.schemas.common import (
    AgeGroupEnum,
    GenderEnum,
    PregnancyStatusEnum,
    RarityEnum,
    RoomTypeEnum,
)
from app.schemas.dweller import SPECIAL_STATS, DwellerCreate
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

    return template.format(mother=mother_link, father=father_link, event=event)


class BreedingService:
    """Service for managing breeding, pregnancy, and child growth."""

    @staticmethod
    def _pair_key(dweller: Dweller) -> tuple[str, str]:
        return tuple(sorted([str(dweller.id), str(dweller.partner_id)]))

    @staticmethod
    def _is_pair_eligible(
        dweller: Dweller,
        unavailable_mother_ids: set[UUID4],
        checked_pairs: set[tuple[str, str]],
    ) -> bool:
        """Check if a dweller-partner pair is eligible for a conception roll."""
        if dweller.gender == GenderEnum.FEMALE and dweller.id in unavailable_mother_ids:
            return False
        if dweller.partner_id in unavailable_mother_ids:
            return False
        return BreedingService._pair_key(dweller) not in checked_pairs

    @staticmethod
    async def _get_relationship_affinity(
        db_session: AsyncSession,
        dweller: Dweller,
        partner: Dweller,
    ) -> float:
        """Get relationship affinity and calculate conception chance.

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
        """Roll random chance and create pregnancy if successful.

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
        """Check all partner pairs in living quarters and roll for conception.

        :param db_session: Database session
        :param vault_id: Vault ID to check
        :returns: List of newly created pregnancies
        """
        living_quarters = await room_crud.get_by_category(db_session, vault_id, RoomTypeEnum.CAPACITY)
        if not living_quarters:
            return []

        # Capacity reservation: a full vault cannot start new conceptions, and
        # already-committed pregnancies reserve one population slot each, so at
        # most (population_max - population - active_pregnancies) new babies may
        # be conceived this tick. population_max=None means unbounded (legacy).
        population_max = (
            await db_session.execute(select(Vault.population_max).where(Vault.id == vault_id))
        ).scalar_one_or_none()

        if population_max is not None:
            population = await vault_crud.get_population(db_session=db_session, vault_id=vault_id)
            if population >= population_max:
                return []
            active_pregnancies = await BreedingService.get_active_pregnancies(db_session, vault_id)
            available_slots = max(0, population_max - population - len(active_pregnancies))
        else:
            available_slots = None

        living_quarters_ids = [room.id for room in living_quarters]
        dwellers = await dweller_crud.get_adults_with_partners_in_rooms(db_session, vault_id, living_quarters_ids)
        unavailable_mother_ids = await pregnancy_crud.get_unavailable_mother_ids(
            db_session, vault_id, game_config.breeding.birth_cooldown_hours
        )

        new_pregnancies: list[Pregnancy] = []
        checked_pairs: set[tuple[str, str]] = set()

        for dweller in dwellers:
            if available_slots is not None and available_slots <= 0:
                break

            if not BreedingService._is_pair_eligible(dweller, unavailable_mother_ids, checked_pairs):
                continue

            checked_pairs.add(BreedingService._pair_key(dweller))

            partner = await db_session.get(Dweller, dweller.partner_id)

            if (
                not partner
                or partner.is_deleted
                or partner.room_id not in living_quarters_ids
                or partner.age_group != AgeGroupEnum.ADULT
            ):
                continue

            if partner.gender == dweller.gender:
                continue

            conception_chance = await BreedingService._get_relationship_affinity(db_session, dweller, partner)
            pregnancy = await BreedingService._roll_for_conception(db_session, dweller, partner, conception_chance)

            if pregnancy:
                new_pregnancies.append(pregnancy)
                if available_slots is not None:
                    available_slots -= 1

        return new_pregnancies

    @staticmethod
    async def create_pregnancy(
        db_session: AsyncSession,
        mother_id: UUID4,
        father_id: UUID4,
    ) -> Pregnancy:
        """Create a new pregnancy record.

        Args:
            db_session: Database session
            mother_id: Mother dweller ID
            father_id: Father dweller ID

        Returns:
            Created pregnancy

        Raises:
            ResourceNotFoundException: If either parent does not exist.
            ValueError: If either parent is not an adult, or mother is not female, or father is not male.
        """
        from app.schemas.common import AgeGroupEnum, GenderEnum

        mother = await dweller_crud.get(db_session, mother_id)
        if mother.age_group != AgeGroupEnum.ADULT:
            raise ValueError("Mother must be an adult")
        if mother.gender != GenderEnum.FEMALE:
            raise ValueError("Mother must be female")

        father = await dweller_crud.get(db_session, father_id)
        if father.age_group != AgeGroupEnum.ADULT:
            raise ValueError("Father must be an adult")
        if father.gender != GenderEnum.MALE:
            raise ValueError("Father must be male")

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
        """Find all pregnancies that are due for delivery."""
        return await pregnancy_crud.get_due_by_vault(db_session, vault_id)

    @staticmethod
    async def _link_newborn_to_home(db_session: AsyncSession, child: Dweller, vault_id: UUID4) -> None:
        """Best-effort: link newborn to home-vault marker on the world map."""
        try:
            from app.crud.vault import vault as vault_crud
            from app.services.map_service import map_service

            vault = await vault_crud.get(db_session, vault_id)
            if vault:
                await map_service.link_home_origin(db_session, child, vault)
        except Exception:
            logger.exception("Failed to link home origin for newborn: child=%s vault=%s", child.id, vault_id)

    @staticmethod
    async def _increment_birth_statistics(
        db_session: AsyncSession, mother: Dweller, child: Dweller, vault_id: UUID4
    ) -> None:
        """Best-effort: increment birth statistics for the vault owner."""
        try:
            from app.crud.user_profile import profile_crud
            from app.crud.vault import vault as vault_crud

            vault = await vault_crud.get(db_session, vault_id)
            if vault and vault.user_id:
                await profile_crud.increment_statistic(db_session, vault.user_id, "total_dwellers_born")

                await notification_service.notify_baby_born(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=vault_id,
                    mother_id=mother.id,
                    mother_name=f"{mother.first_name} {mother.last_name or ''}".strip(),
                    baby_name=f"{child.first_name} {child.last_name or ''}".strip(),
                    meta_data={"child_id": str(child.id), "mother_id": str(mother.id)},
                )
        except Exception:
            logger.exception("Failed to increment birth statistics for vault %s", vault_id)

    @staticmethod
    async def deliver_baby(
        db_session: AsyncSession,
        pregnancy_id: UUID4,
    ) -> Dweller:
        """Deliver a baby from a pregnancy.

        Args:
            db_session: Database session
            pregnancy_id: Pregnancy ID

        Returns:
            Newly created child dweller

        Raises:
            ResourceNotFoundException: If pregnancy or parents not found.
            ValueError: If pregnancy is not due yet.
        """
        pregnancy = await pregnancy_crud.get(db_session, pregnancy_id)

        if not pregnancy.is_due:
            msg = "Pregnancy is not due yet"
            raise ValueError(msg)

        mother = await dweller_crud.get(db_session, pregnancy.mother_id)
        father = await dweller_crud.get(db_session, pregnancy.father_id)

        # Calculate inherited traits
        child_stats = BreedingService._calculate_inherited_stats(mother, father)
        child_rarity = BreedingService._calculate_inherited_rarity(mother, father)
        child_gender = random.choice(list(GenderEnum))

        from app.utils.dwellers import get_gender_based_name

        first_name = get_gender_based_name(child_gender)
        # Father's last name by default; occasionally inherit the mother's instead
        if random.random() < game_config.breeding.maternal_last_name_chance:
            last_name = mother.last_name
        else:
            last_name = father.last_name

        # Create a child dweller
        child_data = {
            "first_name": first_name,
            "last_name": last_name,
            "gender": child_gender,
            "rarity": child_rarity,
            "age_group": AgeGroupEnum.CHILD,
            "is_adult": False,
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
        child = await dweller_crud.create(db_session=db_session, obj_in=child_in)

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

        vault_id = mother.vault_id

        # Link newborn to home vault on world map (best-effort, non-critical)
        await BreedingService._link_newborn_to_home(db_session, child, vault_id)

        # Update pregnancy status
        pregnancy.status = PregnancyStatusEnum.DELIVERED
        pregnancy.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await db_session.commit()
        await db_session.refresh(pregnancy)

        logger.info(f"Baby delivered: {child.first_name} {child.last_name}, Mother={mother.id}, Father={father.id}")

        # Increment birth statistics for the vault owner (best-effort, don't fail birth on stats error)
        await BreedingService._increment_birth_statistics(db_session, mother, child, vault_id)

        return child

    @staticmethod
    def _calculate_inherited_stats(mother: Dweller, father: Dweller) -> dict:
        """Calculate child's inherited SPECIAL stats.

        Args:
            mother: Mother dweller
            father: Father dweller

        Returns:
            Dictionary of SPECIAL stats for child
        """
        special_attrs = SPECIAL_STATS

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
        """Calculate child's inherited rarity.

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
        """Advance children to teens halfway through maturity and teens to adults at completion."""
        now = datetime.now(UTC).replace(tzinfo=None)
        maturity_hours = game_config.breeding.child_growth_duration_hours
        teen_threshold = now - timedelta(hours=maturity_hours // 2)
        adult_threshold = now - timedelta(hours=maturity_hours)

        teens_query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(Dweller.age_group == AgeGroupEnum.TEEN)
            .where(Dweller.birth_date.is_not(None))
            .where(Dweller.birth_date <= adult_threshold)
        )
        teens = list((await db_session.execute(teens_query)).scalars().all())

        children_query = (
            select(Dweller)
            .where(Dweller.vault_id == vault_id)
            .where(Dweller.age_group == AgeGroupEnum.CHILD)
            .where(Dweller.birth_date.is_not(None))
            .where(Dweller.birth_date <= teen_threshold)
        )
        children = (await db_session.execute(children_query)).scalars().all()

        aged_dwellers = []
        for child in children:
            if child.birth_date <= adult_threshold:
                teens.append(child)
                continue
            child.age_group = AgeGroupEnum.TEEN
            child.is_adult = False
            child.updated_at = now
            aged_dwellers.append(child)
            logger.info(f"Child became teen: {child.first_name} {child.last_name} ({child.id})")

        for teen in teens:
            teen.age_group = AgeGroupEnum.ADULT
            teen.is_adult = True
            teen.apprentice_stat = None
            teen.apprentice_started_at = None
            for attr in SPECIAL_STATS:
                current_stat = getattr(teen, attr, 1)
                gains = teen.apprentice_stat_gains.get(attr, 0)
                base_child_stat = max(1, current_stat - gains)
                adult_stat = int(base_child_stat / game_config.breeding.child_special_multiplier) + gains
                setattr(teen, attr, max(1, min(10, adult_stat)))
            teen.apprentice_stat_gains = {}
            teen.updated_at = now
            aged_dwellers.append(teen)
            logger.info(f"Teen became adult: {teen.first_name} {teen.last_name} ({teen.id})")

        await db_session.commit()

        for dweller in aged_dwellers:
            await db_session.refresh(dweller)

        return aged_dwellers

    @staticmethod
    async def get_active_pregnancies(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list[Pregnancy]:
        """Get all active pregnancies for a vault."""
        return await pregnancy_crud.get_active_by_vault(db_session, vault_id)

    @staticmethod
    async def force_conception(
        db_session: AsyncSession,
        mother_id: UUID4,
        father_id: UUID4,
    ) -> Pregnancy:
        mother = await dweller_crud.get(db_session, mother_id)

        if mother.gender != GenderEnum.FEMALE:
            msg = "Mother must be female"
            raise ValueError(msg)

        if mother.age_group != AgeGroupEnum.ADULT:
            msg = "Mother must be adult"
            raise ValueError(msg)

        father = await dweller_crud.get(db_session, father_id)

        if father.gender != GenderEnum.MALE:
            msg = "Father must be male"
            raise ValueError(msg)

        if father.age_group != AgeGroupEnum.ADULT:
            msg = "Father must be adult"
            raise ValueError(msg)

        if await pregnancy_crud.get_active_by_mother(db_session, mother_id):
            msg = "Mother is already pregnant"
            raise ValueError(msg)

        return await BreedingService.create_pregnancy(db_session, mother_id, father_id)

    @staticmethod
    async def accelerate_pregnancy(
        db_session: AsyncSession,
        pregnancy_id: UUID4,
    ) -> Pregnancy:
        pregnancy = await pregnancy_crud.get(db_session, pregnancy_id)

        if pregnancy.status != PregnancyStatusEnum.PREGNANT:
            msg = "Pregnancy is not active"
            raise ValueError(msg)

        pregnancy.due_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        pregnancy.updated_at = datetime.now(UTC).replace(tzinfo=None)

        await db_session.commit()
        await db_session.refresh(pregnancy)

        return pregnancy


breeding_service = BreedingService()
