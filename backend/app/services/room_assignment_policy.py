"""Eligibility rules shared by manual and automatic room assignment."""

# TODO: relocate this kernel plus dweller availability checks outside services so CRUD can share them.

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AgeGroupEnum, RoomTypeEnum, SPECIALEnum
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.dweller import DwellerReadFull
from app.utils.exceptions import ValidationException

ABILITY_TO_STAT_MAP = {
    SPECIALEnum.STRENGTH: "strength",
    SPECIALEnum.PERCEPTION: "perception",
    SPECIALEnum.ENDURANCE: "endurance",
    SPECIALEnum.CHARISMA: "charisma",
    SPECIALEnum.INTELLIGENCE: "intelligence",
    SPECIALEnum.AGILITY: "agility",
    SPECIALEnum.LUCK: "luck",
}


def get_highest_special(dweller: Dweller | DwellerReadFull) -> SPECIALEnum:
    """Return the dweller's highest SPECIAL stat (ties resolve to the first listed stat)."""
    return max(ABILITY_TO_STAT_MAP, key=lambda stat: getattr(dweller, ABILITY_TO_STAT_MAP[stat]))


def calculate_room_capacity(room_size: int | None) -> int:
    """Return dweller slots from room size (2 dwellers per 3 size units, 0 when size is unknown)."""
    return (room_size // 3) * 2 if room_size else 0


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
