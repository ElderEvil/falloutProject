from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.schemas.dweller import DwellerCreate, DwellerUpdate


class CRUDDweller(CRUDBase[Dweller, DwellerCreate, DwellerUpdate]):
    def experience(self, dweller: Dweller) -> int:
        return dweller.experience

    def level(self, dweller: Dweller):
        return dweller.level

    def calculate_experience_required(self, dweller: Dweller) -> int:
        return int(100 * 1.5**dweller.level)

    def add_experience(self, db_session: AsyncSession, dweller: Dweller, amount: int):
        dweller.experience += amount
        experience_required = self.calculate_experience_required(dweller)
        if dweller.experience >= experience_required:
            dweller.level += 1
            dweller.experience -= experience_required
        db_session.add(dweller)
        db_session.commit()
        db_session.refresh(dweller)  # fixme: RuntimeWarning: coroutine 'AsyncSession.refresh' was never awaited

    def is_alive(self, dweller: Dweller) -> bool:
        return dweller.health > 0

    def reanimate(self, dweller: Dweller) -> None:
        if self.is_alive(dweller):
            error_message = "Cannot reanimate alive dweller"
            raise ValueError(error_message)
        dweller.health = dweller.max_health


dweller = CRUDDweller(Dweller)
