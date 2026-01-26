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
from app.schemas.common import DwellerStatusEnum, RoomTypeEnum
from app.schemas.dweller import (
    DwellerCreate,
    DwellerCreateCommonOverride,
    DwellerReadFull,
    DwellerReadWithRoomID,
    DwellerUpdate,
)
from app.utils.dwellers import create_random_common_dweller
from app.utils.exceptions import ContentNoChangeException, InvalidVaultTransferException, ResourceConflictException

BOOSTED_STAT_VALUE = 5


class CRUDDweller(CRUDBase[Dweller, DwellerCreate, DwellerUpdate]):
    async def get(self, db_session: AsyncSession, id: UUID4, include_deleted: bool = False) -> Dweller:
        """Override to eager load weapon and outfit relationships."""
        from app.utils.exceptions import ResourceNotFoundException

        query = (
            select(self.model)
            .where(self.model.id == id)
            .options(
                selectinload(Dweller.vault),
                selectinload(Dweller.room),
                selectinload(Dweller.weapon),
                selectinload(Dweller.outfit),
            )
        )

        # Filter out soft-deleted dwellers by default
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)

        response = await db_session.execute(query)
        db_obj = response.scalar_one_or_none()
        if db_obj is None:
            raise ResourceNotFoundException(self.model, identifier=id)
        return db_obj

    async def get_multi_by_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
        status: DwellerStatusEnum | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        order: str = "desc",
        include_deleted: bool = False,
    ) -> Sequence[Row[Any] | RowMapping | Any]:
        """Get multiple dwellers by vault ID with optional filtering and sorting."""
        query = select(self.model).where(self.model.vault_id == vault_id)

        # Filter out soft-deleted dwellers by default
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)

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
        if sort_by == "name":
            # Special handling for name sorting - sort by first_name, then last_name
            if order.lower() == "asc":
                query = query.order_by(self.model.first_name.asc(), self.model.last_name.asc())
            else:
                query = query.order_by(self.model.first_name.desc(), self.model.last_name.desc())
        elif hasattr(self.model, sort_by):
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
        include_deleted: bool = False,
    ) -> Sequence[Dweller]:
        """Get dwellers by status."""
        query = select(self.model).where(self.model.vault_id == vault_id).where(self.model.status == status)

        # Filter out soft-deleted dwellers by default
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)

        query = query.offset(skip).limit(limit)
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
        from app.services.notification_service import notification_service

        old_level = dweller_obj.level
        dweller_obj.experience += amount
        experience_required = self.calculate_experience_required(dweller_obj)
        leveled_up = False

        if dweller_obj.experience >= experience_required:
            dweller_obj.level += 1
            dweller_obj.experience -= experience_required
            leveled_up = True

        updated_dweller = await self.update(
            db_session, dweller_obj.id, DwellerUpdate(level=dweller_obj.level, experience=dweller_obj.experience)
        )

        # Send level-up notification
        if leveled_up and updated_dweller.vault_id:
            # Get vault to find the owner
            vault = await vault_crud.get(db_session, updated_dweller.vault_id)
            if vault and vault.user_id:
                await notification_service.notify_level_up(
                    db_session,
                    user_id=vault.user_id,
                    vault_id=updated_dweller.vault_id,
                    dweller_id=updated_dweller.id,
                    dweller_name=f"{updated_dweller.first_name} {updated_dweller.last_name or ''}".strip(),
                    new_level=updated_dweller.level,
                    meta_data={"old_level": old_level, "new_level": updated_dweller.level},
                )

        return updated_dweller

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

        # Validate room transfer (can't move to same room)
        if dweller_obj.room_id == room_id:
            raise ResourceConflictException(detail="Dweller is already in the room")

        room_obj = await room_crud.get(db_session, room_id)

        # Validate vault transfer (can't move between vaults)
        if dweller_obj.vault_id != room_obj.vault_id:
            raise InvalidVaultTransferException

        if not dweller_obj.room_id and not await vault_crud.is_enough_population_space(
            db_session=db_session, vault_id=dweller_obj.vault_id, space_required=1
        ):
            raise ContentNoChangeException(detail="Not enough space in the vault to move dweller")

        # Determine status based on room type
        if room_id:
            # Assign status based on room category
            if room_obj.category == RoomTypeEnum.TRAINING:
                new_status = DwellerStatusEnum.TRAINING
            elif room_obj.category == RoomTypeEnum.PRODUCTION:
                new_status = DwellerStatusEnum.WORKING
            else:
                # Default to WORKING for other room types (CAPACITY, CRAFTING, MISC, QUESTS, THEME)
                new_status = DwellerStatusEnum.WORKING
        else:
            # No room assigned - dweller is IDLE
            new_status = DwellerStatusEnum.IDLE

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

    async def use_stimpack(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
        """Use a stimpack to heal the dweller."""
        dweller_obj = await self.get(db_session, dweller_id)

        if dweller_obj.stimpack <= 0:
            raise ResourceConflictException(detail="No stimpacks available to use.")

        if dweller_obj.health >= dweller_obj.max_health:
            raise ContentNoChangeException(detail="Dweller is already at full health.")

        # Heal for 40% of max health (rounded)
        heal_amount = int(dweller_obj.max_health * 0.4)
        new_health = min(dweller_obj.health + heal_amount, dweller_obj.max_health)

        return await self.update(
            db_session, dweller_id, DwellerUpdate(health=new_health, stimpack=dweller_obj.stimpack - 1)
        )

    async def use_radaway(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
        """Use a radaway to remove radiation from the dweller."""
        dweller_obj = await self.get(db_session, dweller_id)

        if dweller_obj.radaway <= 0:
            raise ResourceConflictException(detail="No radaways available to use.")

        if dweller_obj.radiation <= 0:
            raise ContentNoChangeException(detail="Dweller has no radiation to remove.")

        # Remove 50% of radiation (rounded)
        radiation_removal = int(dweller_obj.radiation * 0.5)
        new_radiation = max(dweller_obj.radiation - radiation_removal, 0)

        return await self.update(
            db_session, dweller_id, DwellerUpdate(radiation=new_radiation, radaway=dweller_obj.radaway - 1)
        )

    async def get_dead_dwellers(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        include_permanent: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dweller]:
        """
        Get dead dwellers for a vault.

        :param db_session: Database session
        :param vault_id: Vault ID to filter by
        :param include_permanent: If True, include permanently dead dwellers
        :param skip: Number of records to skip
        :param limit: Maximum number of records to return
        :returns: List of dead dwellers
        """
        query = select(self.model).where(self.model.vault_id == vault_id).where(self.model.is_dead.is_(True))

        if not include_permanent:
            query = query.where(self.model.is_permanently_dead.is_(False))

        query = query.order_by(self.model.death_timestamp.desc()).offset(skip).limit(limit)
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_deleted_by_vault(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dweller]:
        """
        Get soft-deleted dwellers for a specific vault.

        :param db_session: Database session
        :param vault_id: Vault ID to filter by
        :param skip: Number of records to skip
        :param limit: Maximum number of records to return
        :returns: List of soft-deleted dwellers
        """
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.is_deleted == True)
            .order_by(self.model.deleted_at.desc())
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_revivable_dwellers(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dweller]:
        """
        Get dwellers that can be revived (dead but not permanently dead).

        :param db_session: Database session
        :param vault_id: Vault ID to filter by
        :param skip: Number of records to skip
        :param limit: Maximum number of records to return
        :returns: List of revivable dwellers
        """
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.is_dead.is_(True))
            .where(self.model.is_permanently_dead.is_(False))
            .order_by(self.model.death_timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_graveyard(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Dweller]:
        """
        Get permanently dead dwellers (graveyard).

        :param db_session: Database session
        :param vault_id: Vault ID to filter by
        :param skip: Number of records to skip
        :param limit: Maximum number of records to return
        :returns: List of permanently dead dwellers
        """
        query = (
            select(self.model)
            .where(self.model.vault_id == vault_id)
            .where(self.model.is_permanently_dead.is_(True))
            .order_by(self.model.death_timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        response = await db_session.execute(query)
        return response.scalars().all()

    async def auto_assign_to_best_room(
        self, db_session: AsyncSession, dweller_id: UUID4
    ) -> DwellerReadWithRoomID | None:
        """Auto-assign dweller to the best matching production room based on their highest SPECIAL stat."""
        from app.models.room import Room
        from app.schemas.common import SPECIALEnum

        dweller_obj = await self.get(db_session, dweller_id)

        # Find dweller's highest SPECIAL stat
        special_stats = {
            SPECIALEnum.STRENGTH: dweller_obj.strength,
            SPECIALEnum.PERCEPTION: dweller_obj.perception,
            SPECIALEnum.ENDURANCE: dweller_obj.endurance,
            SPECIALEnum.CHARISMA: dweller_obj.charisma,
            SPECIALEnum.INTELLIGENCE: dweller_obj.intelligence,
            SPECIALEnum.AGILITY: dweller_obj.agility,
            SPECIALEnum.LUCK: dweller_obj.luck,
        }

        best_stat = max(special_stats, key=special_stats.get)

        # Find production rooms in the dweller's vault that match this stat and have space
        query = (
            select(Room)
            .where(Room.vault_id == dweller_obj.vault_id)
            .where(Room.category == RoomTypeEnum.PRODUCTION)
            .where(Room.ability == best_stat)
        )
        response = await db_session.execute(query)
        matching_rooms = response.scalars().all()

        if not matching_rooms:
            raise ResourceConflictException(
                detail=f"No production rooms found matching {best_stat.value} stat in this vault"
            )

        # Check if dweller is already in a matching room
        if dweller_obj.room_id:
            current_room = await room_crud.get(db_session, dweller_obj.room_id)
            if current_room.category == RoomTypeEnum.PRODUCTION and current_room.ability == best_stat:
                raise ContentNoChangeException(
                    detail=f"Dweller is already assigned to the best matching room ({current_room.name})"
                )

        # Find room with available capacity (based on room size)
        best_room = None
        for room in matching_rooms:
            # Get current dweller count in room
            dweller_count_query = select(Dweller).where(Dweller.room_id == room.id)
            dweller_count_response = await db_session.execute(dweller_count_query)
            current_dwellers = len(dweller_count_response.scalars().all())

            # Room capacity: 2 dwellers per 3 size units (e.g., size 3 = 2 dwellers, size 6 = 4 dwellers)
            max_dwellers = room.size // 3 * 2 if room.size else 0
            if current_dwellers < max_dwellers:
                best_room = room
                break

        if not best_room:
            raise ResourceConflictException(detail=f"All {best_stat.value} production rooms are at full capacity")

        # Move dweller to the best room
        return await self.move_to_room(db_session, dweller_id, best_room.id)


dweller = CRUDDweller(Dweller)
