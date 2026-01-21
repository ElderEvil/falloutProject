from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models import Dweller, Room, Storage
from app.models.game_state import GameState
from app.models.vault import Vault
from app.schemas.common import GameStatusEnum, RoomActionEnum, RoomTypeEnum
from app.schemas.vault import VaultCreate, VaultCreateWithUserID, VaultNumber, VaultReadWithNumbers, VaultUpdate
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
        msg = f"Invalid room action: {action}"
        raise ValueError(msg)

    async def update_storage(self, db_session: AsyncSession, vault_id: UUID4, new_space_max: int) -> Storage:
        """
        Update the storage max space for a vault.

        Args:
            db_session: Database session
            vault_id: Vault ID
            new_space_max: New maximum storage space

        Returns:
            Updated storage object

        Raises:
            ResourceNotFoundException: If storage not found for vault
        """
        response = await db_session.execute(select(Storage).where(Storage.vault_id == vault_id))
        storage_obj = response.scalar_one_or_none()

        if not storage_obj:
            raise ResourceNotFoundException(model=Storage, identifier=vault_id)

        storage_obj.max_space = new_space_max
        db_session.add(storage_obj)
        await db_session.commit()
        await db_session.refresh(storage_obj)
        return storage_obj

    async def recalculate_vault_attributes(
        self, *, db_session: AsyncSession, vault_obj: Vault, room_obj: Room, action: RoomActionEnum
    ) -> Vault:
        """
        Recalculate the vault attributes based on the newly added or removed room.
        """

        async def _update_vault(vault_update: VaultUpdate):
            await self.update(db_session=db_session, id=vault_obj.id, obj_in=vault_update)

        # Calculate the new vault resource capacity for production rooms
        if room_obj.category == RoomTypeEnum.PRODUCTION and room_obj.capacity is not None:
            match room_obj.ability:
                case "strength":
                    new_capacity = self._calculate_new_capacity(action, vault_obj.power_max, room_obj.capacity)
                    await _update_vault(VaultUpdate(power_max=new_capacity))
                case "agility":
                    new_capacity = self._calculate_new_capacity(action, vault_obj.food_max, room_obj.capacity)
                    await _update_vault(VaultUpdate(food_max=new_capacity))
                case "perception":
                    new_capacity = self._calculate_new_capacity(action, vault_obj.water_max, room_obj.capacity)
                    await _update_vault(VaultUpdate(water_max=new_capacity))
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
                    # Only process if room has capacity defined
                    if room_obj.capacity is not None:
                        # Query storage to get current max_space (avoid lazy load issue)
                        storage_result = await db_session.execute(
                            select(Storage).where(Storage.vault_id == vault_obj.id)
                        )
                        storage_obj = storage_result.scalars().first()
                        current_max_space = storage_obj.max_space if storage_obj else 0

                        new_storage_space_max = self._calculate_new_capacity(
                            action, current_max_space, room_obj.capacity
                        )
                        await self.update_storage(db_session, vault_obj.id, new_storage_space_max)
                case _:
                    error_msg = f"Invalid room name: {room_obj.name}"
                    raise ValueError(error_msg)

        return vault_obj

    @staticmethod
    async def get_population(*, db_session: AsyncSession, vault_id: UUID4) -> int:
        count = await db_session.execute(select(func.count(Vault.dwellers)).where(Vault.id == vault_id))
        return count.scalar()

    @staticmethod
    async def get_rooms_count(*, db_session: AsyncSession, vault_id: UUID4) -> int:
        count = await db_session.execute(select(func.count(Vault.rooms)).where(Vault.id == vault_id))
        return count.scalar()

    async def toggle_game_state(self, *, db_session: AsyncSession, vault_id: UUID4) -> Vault:
        vault_obj = await self.get(db_session, id=vault_id)
        new_state = GameStatusEnum.PAUSED if vault_obj.game_state == GameStatusEnum.ACTIVE else GameStatusEnum.ACTIVE
        obj_in = VaultUpdate(game_state=new_state)
        return await self.update(db_session, id=vault_id, obj_in=obj_in)

    async def get_vaults_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, user_id: UUID4
    ) -> list[VaultReadWithNumbers]:
        result = await db_session.execute(
            select(
                self.model,
                func.count(Room.id.distinct()).label("room_count"),
                func.count(Dweller.id.distinct()).label("dweller_count"),
            )
            .select_from(Vault)
            .join(Room, Room.vault_id == self.model.id, isouter=True)
            .join(Dweller, Dweller.vault_id == self.model.id, isouter=True)
            .where(Vault.user_id == user_id)
            .group_by(Vault.id)
        )

        vaults = result.all()
        return [
            VaultReadWithNumbers(
                **vault_obj.model_dump(),
                room_count=room_count,
                dweller_count=dweller_count,
            )
            for vault_obj, room_count, dweller_count in vaults
        ]

    async def get_vault_with_room_and_dweller_count(
        self, *, db_session: AsyncSession, vault_id: UUID4
    ) -> VaultReadWithNumbers:
        result = await db_session.execute(
            select(
                self.model,
                func.count(Room.id.distinct()).label("room_count"),
                func.count(Dweller.id.distinct()).label("dweller_count"),
            )
            .select_from(Vault)
            .join(Room, Room.vault_id == self.model.id, isouter=True)
            .join(Dweller, Dweller.vault_id == self.model.id, isouter=True)
            .where(Vault.id == vault_id)
            .group_by(Vault.id)
        )

        vault_data = result.one()
        vault_obj, room_count, dweller_count = vault_data
        return VaultReadWithNumbers(
            **vault_obj.model_dump(),
            room_count=room_count,
            dweller_count=dweller_count,
        )

    @staticmethod
    async def create_storage(*, db_session: AsyncSession, vault_id: UUID4) -> Storage:
        storage = Storage(vault_id=vault_id)
        db_session.add(storage)
        await db_session.commit()
        return storage

    async def create_with_user_id(
        self, *, db_session: AsyncSession, obj_in: VaultCreate | VaultNumber | dict, user_id: UUID4
    ) -> Vault:
        obj_data = obj_in.model_dump() if hasattr(obj_in, "model_dump") else obj_in
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
        Only counts dwellers that are assigned to rooms (have room_id).
        Unassigned dwellers don't take up living space.
        """
        result = await db_session.execute(
            select(Vault.population_max, func.count(Dweller.id))
            .select_from(Vault)
            .join(Dweller, Dweller.vault_id == Vault.id)
            .where(Vault.id == vault_id)
            .where(Dweller.room_id.is_not(None))  # Only count assigned dwellers
            .group_by(Vault.id)
        )
        vault_obj = result.first()
        if not vault_obj:
            # Vault exists but has no assigned dwellers yet
            # Check if vault exists
            vault_check = await db_session.execute(select(Vault.population_max).where(Vault.id == vault_id))
            population_max = vault_check.scalar_one_or_none()
            if population_max is None:
                error_msg = f"Vault with ID {vault_id} not found"
                raise ValueError(error_msg)
            return space_required <= population_max
        population_max, current_assigned_population = vault_obj
        if population_max is None:
            return False
        return current_assigned_population + space_required <= population_max

    async def deposit_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int):
        """Deposit the specified amount to the vault's bottle caps as part of a revenue operation."""
        await self.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps + amount))

    async def withdraw_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int):
        """Withdraw the specified amount from the vault's bottle caps as part of a spending operation."""
        if vault_obj.bottle_caps < amount:
            amount_needed = amount - vault_obj.bottle_caps
            raise InsufficientResourcesException(resource_name="bottle caps", resource_amount=amount_needed)
        await self.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps - amount))

    async def delete(self, db_session: AsyncSession, id: UUID4) -> None:
        """Delete vault and its associated gamestate."""
        # First, delete the associated gamestate if it exists
        result = await db_session.execute(select(GameState).where(GameState.vault_id == id))
        gamestate = result.scalar_one_or_none()
        if gamestate:
            await db_session.delete(gamestate)
            await db_session.commit()

        # Now delete the vault using the base class method
        return await super().delete(db_session, id)


vault = CRUDVault(Vault)
