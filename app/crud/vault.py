from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models import Dweller, Room, Storage
from app.models.vault import Vault
from app.schemas.common import RoomActionEnum, RoomTypeEnum
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultCreate, VaultCreateWithUserID, VaultStart, VaultUpdate
from app.utils.exceptions import InsufficientResourcesException, ResourceNotFoundException


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    async def get_by_user_id(self, *, db_session: AsyncSession, user_id: UUID4) -> Sequence[Vault]:
        response = await db_session.execute(select(self.model).where(self.model.user_id == user_id))
        return response.scalars().all()

    @staticmethod
    def _calculate_new_capacity(action: RoomActionEnum, current_capacity: int, room_capacity: int) -> int:
        if action in {RoomActionEnum.BUILD, RoomActionEnum.UPGRADE}:
            return current_capacity + room_capacity
        if action == RoomActionEnum.DESTROY:
            return current_capacity - room_capacity
        raise ValueError(f"Invalid room action: {action}")  # noqa: TRY003

    async def recalculate_vault_attributes(
        self, db_session: AsyncSession, vault_obj: Vault, room_obj: Room, action: RoomActionEnum
    ) -> Vault:
        """
        Recalculate the vault attributes based on the newly added or removed room.
        """

        async def _update_vault(vault_update: VaultUpdate):
            await self.update(db_session=db_session, id=vault_obj.id, obj_in=vault_update)

        async def _update_storage(vault_id: UUID4, new_space_max: int):
            response = await db_session.execute(select(Storage).where(Storage.vault_id == vault_id))
            storage_obj = response.scalar_one_or_none()

            if not storage_obj:
                raise ResourceNotFoundException(model=Storage, identifier=vault_id)

            storage_obj.max_space = new_space_max
            db_session.add(storage_obj)
            await db_session.commit()
            await db_session.refresh(storage_obj)

        # Calculate the new vault resource capacity for production rooms
        if room_obj.category == RoomTypeEnum.PRODUCTION and room_obj.capacity is not None:
            match room_obj.ability:
                case "Strength":
                    new_capacity = self._calculate_new_capacity(action, vault_obj.power_max, room_obj.capacity)
                    await _update_vault(VaultUpdate(power_capacity=new_capacity))
                case "Agility":
                    new_capacity = self._calculate_new_capacity(action, vault_obj.food_max, room_obj.capacity)
                    await _update_vault(VaultUpdate(food_capacity=new_capacity))
                case "Perception":
                    new_capacity = self._calculate_new_capacity(action, vault_obj.water_max, room_obj.capacity)
                    await _update_vault(VaultUpdate(water_capacity=new_capacity))
                case _:
                    error_msg = f"Invalid room ability: {room_obj.ability}"
                    raise ValueError(error_msg)

        # Calculate the new vault capacity for capacity rooms
        elif room_obj.category == RoomTypeEnum.CAPACITY:
            match room_obj.name.lower():
                case "living room":
                    new_population_max = self._calculate_new_capacity(
                        action, vault_obj.population_max or 0, room_obj.capacity
                    )
                    await _update_vault(VaultUpdate(population_max=new_population_max))
                case "storage room":
                    new_storage_space_max = self._calculate_new_capacity(
                        action, vault_obj.storage.max_space or 0, room_obj.capacity
                    )
                    await _update_storage(vault_obj.id, new_storage_space_max)
                case _:
                    error_msg = f"Invalid room name: {room_obj.name}"
                    raise ValueError(error_msg)

        return vault_obj

    @staticmethod
    async def get_population(*, db_session: AsyncSession, vault_id: UUID4) -> int:
        count = await db_session.execute(select(func.count(Vault.dwellers)).where(Vault.id == vault_id))
        return count.scalar()

    async def create_with_user_id(
        self, db_session: AsyncSession, obj_in: VaultCreate | VaultStart, user_id: UUID4
    ) -> Vault:
        obj_data = obj_in.model_dump()
        obj_data["user_id"] = user_id
        obj_in = VaultCreateWithUserID(**obj_data)
        return await super().create(db_session, obj_in)

    async def is_enough_dwellers(
        self, *, db_session: AsyncSession, vault_id: UUID4, population_required: int | None
    ) -> bool:
        """
        Check if the vault has enough dwellers to perform an operation.
        """
        if population_required is None:
            return True
        dwellers_count = await self.get_population(db_session=db_session, vault_id=vault_id)
        return dwellers_count >= population_required

    @staticmethod
    async def is_enough_population_space(*, db_session: AsyncSession, vault_id: UUID4, space_required: int) -> bool:
        """
        Check if the vault has enough space to perform an operation.
        """
        result = await db_session.execute(
            select(Vault.population_max, func.count(Dweller.id))
            .select_from(Vault)
            .join(Dweller, Dweller.vault_id == Vault.id)
            .where(Vault.id == vault_id)
            .group_by(Vault.id)
        )
        vault_obj = result.first()
        if not vault_obj:
            error_msg = f"Vault with ID {vault_id} not found"
            raise ValueError(error_msg)
        population_max, current_population = vault_obj
        if population_max is None:
            return False
        return current_population + space_required <= population_max

    async def deposit_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int):
        """Deposit the specified amount to the vault's bottle caps as part of a revenue operation."""
        await self.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps + amount))

    async def withdraw_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int):
        """Withdraw the specified amount from the vault's bottle caps as part of a spending operation."""
        if vault_obj.bottle_caps < amount:
            amount_needed = amount - vault_obj.bottle_caps
            raise InsufficientResourcesException(resource_name="bottle caps", resource_amount=amount_needed)
        await self.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps - amount))

    async def initiate(self, *, db_session: AsyncSession, obj_in: VaultStart, user_id: UUID4) -> Vault:
        """
        Create a new vault for a user and initialize it with essential rooms.
        Includes a vault door and multiple elevators.
        """
        from app.crud.room import room as room_crud

        vault_db_obj = await self.create_with_user_id(db_session, obj_in, user_id)

        # Prepare the initial vault door
        vault_door = RoomCreate(
            name="Vault Door",
            vault_id=vault_db_obj.id,
            coordinate_x=0,
            coordinate_y=0,  # Vault Door at (0,0)
        )

        # Prepare elevators at different 'y' coordinates
        elevators = [
            RoomCreate(
                name="Elevator",
                vault_id=vault_db_obj.id,
                coordinate_x=1,
                coordinate_y=i,  # Unique 'y' coordinate for each elevator
            )
            for i in range(3)
        ]

        # List of all initial rooms to create
        initial_rooms = [vault_door, *elevators]

        # Create all initial rooms in a single transaction
        await room_crud.create_all(db_session, initial_rooms)

        return vault_db_obj


vault = CRUDVault(Vault)
