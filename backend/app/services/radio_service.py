"""Service for managing radio room recruitment system."""

import logging
import random

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.room import Room
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreateCommonOverride
from app.services.notification_service import notification_service

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

        return (await db_session.execute(query)).scalars().all()

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
        rate = game_config.radio.base_recruitment_rate

        # Apply tier and speedup multipliers for each radio room
        for room in radio_rooms:
            tier_multiplier = game_config.radio.get_tier_multiplier(room.tier)
            rate *= tier_multiplier

            # Apply speedup multiplier (1.0-10.0x)
            rate *= room.speedup_multiplier

            # Add charisma bonus from assigned dwellers
            # Query dwellers assigned to this room
            dwellers_query = select(Dweller).where(Dweller.room_id == room.id)
            dwellers = (await db_session.execute(dwellers_query)).scalars().all()

            for dweller in dwellers:
                charisma_bonus = dweller.charisma * game_config.radio.charisma_rate_multiplier
                rate += game_config.radio.base_recruitment_rate * charisma_bonus

        # Apply vault happiness multiplier
        happiness_multiplier = 1.0 + (vault.happiness * game_config.radio.happiness_rate_multiplier)
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
                f"Radio recruitment successful: {dweller.first_name} {dweller.last_name} joined vault {vault_id}"
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

        logger.info(f"Recruited dweller: {dweller.first_name} {dweller.last_name} to vault {vault_id}")

        # Send notification (non-critical, don't break recruitment on failure)
        try:
            from app.crud.vault import vault as vault_crud

            vault = await vault_crud.get(db_session, vault_id)
            if vault and vault.user_id:
                await notification_service.notify_radio_new_dweller(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=vault_id,
                    dweller_name=f"{dweller.first_name} {dweller.last_name or ''}".strip(),
                    meta_data={"dweller_id": str(dweller.id)},
                )
        except Exception:
            logger.exception(
                "Failed to send radio recruitment notification: vault_id=%s, dweller_id=%s", vault_id, dweller.id
            )

        return dweller

    @staticmethod
    async def manual_recruit(
        db_session: AsyncSession,
        vault_id: UUID4,
        caps_cost: int | None = None,
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

        if caps_cost is None:
            caps_cost = game_config.radio.manual_recruitment_cost

        # Check if vault has radio room
        radio_rooms = await RadioService.get_radio_rooms(db_session, vault_id)
        if not radio_rooms:
            msg = "No radio room available"
            raise ValueError(msg)

        # Check if any radio room has assigned dwellers
        radio_room_ids = [room.id for room in radio_rooms]
        dwellers_query = select(Dweller).where(
            Dweller.room_id.in_(radio_room_ids), Dweller.vault_id == vault_id, Dweller.is_deleted == False
        )
        assigned_dwellers = (await db_session.execute(dwellers_query)).scalars().all()

        if not assigned_dwellers:
            msg = "No residents assigned to radio room"
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
            f"Manual recruitment: {dweller.first_name} {dweller.last_name} to vault {vault_id} for {caps_cost} caps"
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
                "manual_cost_caps": game_config.radio.manual_recruitment_cost,
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
                "manual_cost_caps": game_config.radio.manual_recruitment_cost,
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
            "manual_cost_caps": game_config.radio.manual_recruitment_cost,
            "radio_mode": vault.radio_mode,
            "speedup_multipliers": speedup_multipliers,
        }


radio_service = RadioService()
