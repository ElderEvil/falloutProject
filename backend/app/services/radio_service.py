"""Service for managing radio room recruitment system."""

import logging
import random

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.config.game_balance import (
    BASE_RECRUITMENT_RATE,
    CHARISMA_RATE_MULTIPLIER,
    HAPPINESS_RATE_MULTIPLIER,
    MANUAL_RECRUITMENT_COST,
    RADIO_TIER_MULTIPLIER,
)
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreateCommonOverride

logger = logging.getLogger(__name__)


class RadioService:
    """Service for managing radio room recruitment."""

    @staticmethod
    async def get_radio_rooms(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> list[Room]:
        """
        Get all radio studio rooms for a vault.

        Args:
            db_session: Database session
            vault_id: Vault ID

        Returns:
            List of radio rooms
        """
        # Radio rooms would have "Radio" in the name or a specific type
        # For now, we'll use name-based matching until a RADIO room type is added
        query = select(Room).where(Room.vault_id == vault_id).where(Room.name.ilike("%radio%"))

        rooms = (await db_session.execute(query)).scalars().all()
        return rooms  # noqa: RET504

    @staticmethod
    async def calculate_recruitment_rate(
        db_session: AsyncSession,
        vault: Vault,
        radio_rooms: list[Room] | None = None,
    ) -> float:
        """
        Calculate recruitment rate based on radio rooms, charisma, and happiness.

        Args:
            db_session: Database session
            vault: Vault object
            radio_rooms: Optional list of radio rooms (will fetch if None)

        Returns:
            Recruitment rate (probability per tick)
        """
        if radio_rooms is None:
            radio_rooms = await RadioService.get_radio_rooms(db_session, vault.id)

        if not radio_rooms:
            return 0.0

        # Start with base rate
        rate = BASE_RECRUITMENT_RATE

        # Apply tier and speedup multipliers for each radio room
        for room in radio_rooms:
            tier_multiplier = RADIO_TIER_MULTIPLIER.get(room.tier, 1.0)
            rate *= tier_multiplier

            # Apply speedup multiplier (1.0-10.0x)
            rate *= room.speedup_multiplier

            # Add charisma bonus from assigned dwellers
            # Query dwellers assigned to this room
            dwellers_query = select(Dweller).where(Dweller.room_id == room.id)
            dwellers = (await db_session.execute(dwellers_query)).scalars().all()

            for dweller in dwellers:
                charisma_bonus = dweller.charisma * CHARISMA_RATE_MULTIPLIER
                rate += BASE_RECRUITMENT_RATE * charisma_bonus

        # Apply vault happiness multiplier
        happiness_multiplier = 1.0 + (vault.happiness * HAPPINESS_RATE_MULTIPLIER)
        rate *= happiness_multiplier

        return rate

    @staticmethod
    async def check_for_recruitment(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> Dweller | None:
        """
        Check if a new dweller should be recruited via radio.

        Args:
            db_session: Database session
            vault_id: Vault ID

        Returns:
            Newly recruited dweller if successful, None otherwise
        """
        # Get vault
        vault_query = select(Vault).where(Vault.id == vault_id)
        vault = (await db_session.execute(vault_query)).scalars().first()

        if not vault:
            return None

        # Check if vault is in recruitment mode
        if vault.radio_mode != "recruitment":
            return None

        # Get radio rooms
        radio_rooms = await RadioService.get_radio_rooms(db_session, vault_id)

        if not radio_rooms:
            return None

        # Calculate recruitment rate
        rate = await RadioService.calculate_recruitment_rate(db_session, vault, radio_rooms)

        # Roll for recruitment
        if random.random() < rate:
            dweller = await RadioService.recruit_dweller(db_session, vault_id)
            logger.info(
                f"Radio recruitment successful: {dweller.first_name} {dweller.last_name} joined vault {vault_id}"  # noqa: G004
            )
            return dweller

        return None

    @staticmethod
    async def recruit_dweller(
        db_session: AsyncSession,
        vault_id: UUID4,
        override: DwellerCreateCommonOverride | None = None,
    ) -> Dweller:
        """
        Recruit a new random dweller to the vault.

        Args:
            db_session: Database session
            vault_id: Vault ID
            override: Optional override for dweller attributes

        Returns:
            Newly created dweller
        """
        # Create random common dweller
        dweller = await crud.dweller.create_random(
            db_session=db_session,
            obj_in=override,
            vault_id=vault_id,
        )

        logger.info(f"Recruited dweller: {dweller.first_name} {dweller.last_name} to vault {vault_id}")  # noqa: G004

        return dweller

    @staticmethod
    async def manual_recruit(
        db_session: AsyncSession,
        vault_id: UUID4,
        caps_cost: int = MANUAL_RECRUITMENT_COST,
        override: DwellerCreateCommonOverride | None = None,
    ) -> Dweller:
        """
        Manually recruit a dweller for caps.

        Args:
            db_session: Database session
            vault_id: Vault ID
            caps_cost: Cost in caps (default from config)
            override: Optional override for dweller attributes

        Returns:
            Newly recruited dweller

        Raises:
            ValueError: If insufficient caps or no radio room
        """
        # Get vault
        vault_query = select(Vault).where(Vault.id == vault_id)
        vault = (await db_session.execute(vault_query)).scalars().first()

        if not vault:
            msg = "Vault not found"
            raise ValueError(msg)

        # Check if vault has radio room
        radio_rooms = await RadioService.get_radio_rooms(db_session, vault_id)
        if not radio_rooms:
            msg = "No radio room available"
            raise ValueError(msg)

        # Check if vault has enough caps
        if vault.bottle_caps < caps_cost:
            msg = f"Insufficient caps ({vault.bottle_caps}/{caps_cost})"
            raise ValueError(msg)

        # Deduct caps
        vault.bottle_caps -= caps_cost
        await db_session.commit()

        # Recruit dweller
        dweller = await RadioService.recruit_dweller(db_session, vault_id, override)

        logger.info(
            f"Manual recruitment: {dweller.first_name} {dweller.last_name} to vault {vault_id} for {caps_cost} caps"  # noqa: G004
        )

        return dweller

    @staticmethod
    async def get_recruitment_stats(
        db_session: AsyncSession,
        vault_id: UUID4,
    ) -> dict:
        """
        Get recruitment statistics for a vault.

        Args:
            db_session: Database session
            vault_id: Vault ID

        Returns:
            Dictionary with recruitment stats
        """
        # Get vault
        vault_query = select(Vault).where(Vault.id == vault_id)
        vault = (await db_session.execute(vault_query)).scalars().first()

        if not vault:
            return {
                "has_radio": False,
                "recruitment_rate": 0.0,
                "rate_per_hour": 0.0,
                "estimated_hours_per_recruit": 0.0,
                "radio_rooms_count": 0,
                "manual_cost_caps": MANUAL_RECRUITMENT_COST,
                "radio_mode": "recruitment",
                "speedup_multipliers": [],
            }

        # Get radio rooms
        radio_rooms = await RadioService.get_radio_rooms(db_session, vault_id)

        if not radio_rooms:
            return {
                "has_radio": False,
                "recruitment_rate": 0.0,
                "rate_per_hour": 0.0,
                "estimated_hours_per_recruit": 0.0,
                "radio_rooms_count": 0,
                "manual_cost_caps": MANUAL_RECRUITMENT_COST,
                "radio_mode": vault.radio_mode,
                "speedup_multipliers": [],
            }

        # Calculate rate (per minute)
        rate_per_minute = await RadioService.calculate_recruitment_rate(db_session, vault, radio_rooms)

        # Convert to hours
        rate_per_hour = rate_per_minute * 60
        hours_per_recruit = 1.0 / rate_per_hour if rate_per_hour > 0 else 0.0

        # Get speedup multipliers for each radio room
        speedup_multipliers = [{"room_id": str(room.id), "speedup": room.speedup_multiplier} for room in radio_rooms]

        return {
            "has_radio": True,
            "recruitment_rate": rate_per_minute,
            "rate_per_hour": rate_per_hour,
            "estimated_hours_per_recruit": hours_per_recruit,
            "radio_rooms_count": len(radio_rooms),
            "manual_cost_caps": MANUAL_RECRUITMENT_COST,
            "radio_mode": vault.radio_mode,
            "speedup_multipliers": speedup_multipliers,
        }


radio_service = RadioService()
