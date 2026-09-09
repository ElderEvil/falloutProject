"""Eligibility rules shared by manual and automatic room assignment."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AgeGroupEnum, RoomTypeEnum
from app.models.dweller import Dweller
from app.models.room import Room
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

    from app.crud.dweller import dweller as dweller_crud

    existing_apprentice = await dweller_crud.has_other_apprentice(
        db_session, room_id=room.id, exclude_dweller_id=dweller.id
    )
    if existing_apprentice:
        raise ValidationException(detail="This production room already has an apprentice")


def validate_automatic_assignment(dweller: Dweller) -> None:
    """Keep youth assignments deliberate until apprentice automation has dedicated rules."""
    if not dweller.is_mature:
        raise ValidationException(detail="Child and teen dwellers must be assigned manually as apprentices")
