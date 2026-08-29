"""Eligibility rules shared by manual and automatic room assignment."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.common import AgeGroupEnum, RoomTypeEnum
from app.utils.exceptions import ValidationException


def adult_assignment_conditions() -> tuple:
    """Return database conditions that select mature dwellers for automatic work assignment."""
    return Dweller.is_adult, Dweller.age_group == AgeGroupEnum.ADULT


async def validate_room_assignment(db_session: AsyncSession, dweller: Dweller, room: Room) -> None:
    """Allow one youth apprentice in each production room, training its ability."""
    if dweller.is_mature:
        return
    if room.category == RoomTypeEnum.ARENA:
        raise ValidationException(detail="Only adult dwellers can fight in the Arena")
    if room.category != RoomTypeEnum.PRODUCTION:
        raise ValidationException(
            detail="Child and teen dwellers can only be assigned to production rooms as apprentices"
        )
    if room.ability is None:
        raise ValidationException(detail="Production room must have a SPECIAL ability for an apprentice")

    existing_apprentice = await db_session.execute(
        select(Dweller.id).where(
            Dweller.room_id == room.id,
            Dweller.id != dweller.id,
            Dweller.apprentice_started_at.is_not(None),
        )
    )
    if existing_apprentice.scalars().first() is not None:
        raise ValidationException(detail="This production room already has an apprentice")


def validate_automatic_assignment(dweller: Dweller) -> None:
    """Keep youth assignments deliberate until apprentice automation has dedicated rules."""
    if not dweller.is_mature:
        raise ValidationException(detail="Child and teen dwellers must be assigned manually as apprentices")
