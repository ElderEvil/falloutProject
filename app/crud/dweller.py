from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.crud.room import room as room_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.schemas.dweller import DwellerCreate, DwellerCreateCommonOverride, DwellerReadWithRoom, DwellerUpdate
from app.tests.factory.dwellers import create_random_common_dweller
from app.utils.exceptions import ContentNoChangeException, NoSpaceAvailableException, ResourceConflictException
from app.utils.validation import validate_vault_transfer

BOOSTED_STAT_VALUE = 5


class CRUDDweller(CRUDBase[Dweller, DwellerCreate, DwellerUpdate]):
    @staticmethod
    async def create_random(
        db_session: AsyncSession, vault_id: UUID4, obj_in: DwellerCreateCommonOverride | None = None
    ) -> Dweller:
        """Create a random common dweller."""
        dweller_data = create_random_common_dweller()
        if obj_in:
            new_dweller_data = obj_in.dict(exclude_unset=True)
            if stat := new_dweller_data.get("special_boost"):
                dweller_data[stat.value.lower()] = BOOSTED_STAT_VALUE
                new_dweller_data.pop("special_boost")
            dweller_data.update(new_dweller_data)

        db_obj = Dweller(**dweller_data, vault_id=vault_id)
        db_session.add(db_obj)
        await db_session.commit()
        await db_session.refresh(db_obj)
        return db_obj

    @staticmethod
    def calculate_experience_required(dweller_obj: Dweller) -> int:
        """Calculate the experience required for the next level."""
        return int(100 * 1.5**dweller_obj.level)

    @staticmethod
    def is_alive(dweller_obj: Dweller) -> bool:
        return dweller_obj.health > 0

    async def add_experience(self, db_session: AsyncSession, dweller_obj: Dweller, amount: int):
        """Add experience to dweller and level up if necessary."""
        dweller_obj.experience += amount
        experience_required = self.calculate_experience_required(dweller_obj)
        if dweller_obj.experience >= experience_required:
            dweller_obj.level += 1
            dweller_obj.experience -= experience_required
        return await self.update(
            db_session, dweller_obj.id, DwellerUpdate(level=dweller_obj.level, experience=dweller_obj.experience)
        )

    async def move_to_room(
        self, db_session: AsyncSession, dweller_id: UUID4, room_id: UUID4
    ) -> DwellerReadWithRoom | None:
        """Move dweller to a different room."""
        dweller_obj = await self.get(db_session, dweller_id)
        if dweller_obj.room_id == room_id:
            raise ResourceConflictException(detail="Dweller is already in the room")

        room_obj = await room_crud.get(db_session, room_id)

        validate_vault_transfer(dweller_obj.vault_id, room_obj.vault_id)
        dweller_obj = await self.update(db_session, dweller_id, DwellerUpdate(room_id=room_id))

        if not await vault_crud.is_enough_population_space():
            raise NoSpaceAvailableException(space_needed=1)

        return DwellerReadWithRoom.from_orm(dweller_obj)

    def reanimate(self, db_session: AsyncSession, dweller_obj: Dweller) -> Dweller | None:
        """Revive a dead dweller."""
        if self.is_alive(dweller_obj):
            raise ContentNoChangeException(detail="Dweller is already alive")
        self.update(db_session, dweller_obj.id, DwellerUpdate(health=dweller_obj.max_health))
        return dweller_obj


dweller = CRUDDweller(Dweller)
