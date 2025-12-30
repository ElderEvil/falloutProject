from collections.abc import Sequence
from typing import Any

from pydantic import UUID4
from sqlalchemy import Row, RowMapping
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.crud.room import room as room_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.schemas.common import DwellerStatusEnum
from app.schemas.dweller import (
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerReadFull,
    DwellerReadWithRoomID,
    DwellerUpdate,
)
from app.tests.factory.dwellers import create_random_common_dweller
from app.utils.exceptions import ContentNoChangeException
from app.utils.validation import validate_room_transfer, validate_vault_transfer

BOOSTED_STAT_VALUE = 5


class CRUDDweller(CRUDBase[Dweller, DwellerCreate, DwellerUpdate]):
    async def get_multi_by_vault(  # noqa: PLR0913
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
        status: DwellerStatusEnum | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> Sequence[Row[Any] | RowMapping | Any]:
        """Get multiple dwellers by vault ID with optional filtering and sorting."""
        query = select(self.model).where(self.model.vault_id == vault_id)

        # Filter by status
        if status:
            query = query.where(self.model.status == status)

        # Search by name
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (self.model.first_name.ilike(search_pattern)) | (self.model.last_name.ilike(search_pattern))
            )

        # Sorting
        if hasattr(self.model, sort_by):
            sort_column = getattr(self.model, sort_by)
            if order.lower() == "asc":  # noqa: SIM108
                query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(sort_column.desc())

        query = query.offset(skip).limit(limit)
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_by_status(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        status: DwellerStatusEnum,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dweller]:
        """Get dwellers by status."""
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.status == status)
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()

    @staticmethod
    async def create_random(
        db_session: AsyncSession, vault_id: UUID4, obj_in: DwellerCreateCommonOverride | None = None
    ) -> Dweller:
        """Create a random common dweller."""
        dweller_data = create_random_common_dweller()
        if obj_in:
            new_dweller_data = obj_in.model_dump(exclude_unset=True)
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

    async def get_dweller_by_name(self, db_session: AsyncSession, name: str) -> Dweller | None:
        """Get dweller by name."""
        query = select(self.model).where(self.model.first_name == name)
        response = await db_session.execute(query)
        return response.scalars().first()

    async def move_to_room(
        self, db_session: AsyncSession, dweller_id: UUID4, room_id: UUID4
    ) -> DwellerReadWithRoomID | None:
        """Move dweller to a different room."""
        dweller_obj = await self.get(db_session, dweller_id)
        validate_room_transfer(dweller_obj.room_id, room_id)

        room_obj = await room_crud.get(db_session, room_id)
        validate_vault_transfer(dweller_obj.vault_id, room_obj.vault_id)

        if not dweller_obj.room_id and not await vault_crud.is_enough_population_space(
            db_session=db_session, vault_id=dweller_obj.vault_id, space_required=1
        ):
            raise ContentNoChangeException(detail="Not enough space in the vault to move dweller")

        # Update status to WORKING when assigned to room, IDLE when removed
        new_status = DwellerStatusEnum.WORKING if room_id else DwellerStatusEnum.IDLE
        dweller_obj = await self.update(db_session, dweller_id, DwellerUpdate(room_id=room_id, status=new_status))

        return DwellerReadWithRoomID.model_validate(dweller_obj)

    async def reanimate(self, db_session: AsyncSession, dweller_obj: Dweller) -> Dweller | None:
        """Revive a dead dweller."""
        if self.is_alive(dweller_obj):
            raise ContentNoChangeException(detail="Dweller is already alive")
        await self.update(
            db_session, dweller_obj.id, DwellerUpdate(health=dweller_obj.max_health, status=DwellerStatusEnum.IDLE)
        )
        return dweller_obj

    async def mark_as_dead(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
        """Mark dweller as dead (health=0, status=DEAD)."""
        return await self.update(db_session, dweller_id, DwellerUpdate(health=0, status=DwellerStatusEnum.DEAD))

    async def get_full_info(self, db_session: AsyncSession, dweller_id: UUID4) -> DwellerReadFull:
        """Get full information about a dweller."""
        query = (
            select(self.model)
            .options(
                selectinload(self.model.vault),
                selectinload(self.model.room),
                selectinload(self.model.weapon),
                selectinload(self.model.outfit),
            )
            .where(self.model.id == dweller_id)
        )
        response = await db_session.execute(query)
        dweller_obj = response.scalar_one_or_none()

        return DwellerReadFull.model_validate(dweller_obj)


dweller = CRUDDweller(Dweller)
