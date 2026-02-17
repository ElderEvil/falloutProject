from collections.abc import Sequence
from logging import getLogger

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models import Dweller, Room, Storage
from app.models.game_state import GameState
from app.models.vault import Vault
from app.schemas.common import GameStatusEnum, RoomActionEnum, RoomTypeEnum, SPECIALEnum
from app.schemas.vault import VaultCreate, VaultCreateWithUserID, VaultNumber, VaultReadWithNumbers, VaultUpdate
from app.services.resource_manager import ResourceManager
from app.utils.exceptions import InsufficientResourcesException, ResourceNotFoundException

logger = getLogger(__name__)


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    async def get_by_user_id(
        self, *, db_session: AsyncSession, user_id: UUID4, include_deleted: bool = False
    ) -> Sequence[Vault]:
        query = select(self.model).where(self.model.user_id == user_id)
        if not include_deleted:
            query = query.where(self.model.is_deleted == False)
        response = await db_session.execute(query)
        return response.scalars().all()

    @staticmethod
    def _calculate_new_capacity(action: RoomActionEnum, current_capacity: int, room_capacity: int | None) -> int:
        # Handle rooms without capacity (elevators, vault door, etc.)
        if room_capacity is None:
            return current_capacity

        if action in {RoomActionEnum.BUILD, RoomActionEnum.UPGRADE}:
            return current_capacity + room_capacity
        if action == RoomActionEnum.DESTROY:
            return current_capacity - room_capacity
        msg = f"Invalid room action: {action}"
        raise ValueError(msg)

    async def update_storage(self, db_session: AsyncSession, vault_id: UUID4, new_space_max: int) -> Storage:
        """
        Update the storage max space for a vault.

        :param db_session: Database session
        :param vault_id: Vault ID
        :param new_space_max: New maximum storage space
        :returns: Updated storage object
        :raises ResourceNotFoundException: If storage not found for vault
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
        """Recalculate the vault attributes based on the newly added or removed room."""
        if room_obj.category == RoomTypeEnum.PRODUCTION and room_obj.capacity is not None:
            await self._handle_production_room(db_session, vault_obj, room_obj, action)
        elif room_obj.category == RoomTypeEnum.CAPACITY:
            await self._handle_capacity_room(db_session, vault_obj, room_obj, action)

        return vault_obj

    async def _handle_production_room(
        self, db_session: AsyncSession, vault_obj: Vault, room_obj: Room, action: RoomActionEnum
    ) -> None:
        """Handle production room capacity updates."""
        if room_obj.ability not in (
            SPECIALEnum.STRENGTH,
            SPECIALEnum.AGILITY,
            SPECIALEnum.PERCEPTION,
            SPECIALEnum.INTELLIGENCE,
        ):
            msg = f"Invalid room ability: {room_obj.ability}"
            raise ValueError(msg)

        resource_map = {
            SPECIALEnum.STRENGTH: ("power_max", vault_obj.power_max),
            SPECIALEnum.AGILITY: ("food_max", vault_obj.food_max),
            SPECIALEnum.PERCEPTION: ("water_max", vault_obj.water_max),
            SPECIALEnum.INTELLIGENCE: (None, None),
        }

        field, current = resource_map[room_obj.ability]

        if room_obj.ability == SPECIALEnum.INTELLIGENCE:
            if "medbay" in room_obj.name.lower():
                field = "stimpack_max"
                current = vault_obj.stimpack_max or 0
            elif "science" in room_obj.name.lower():
                field = "radaway_max"
                current = vault_obj.radaway_max or 0

        if field:
            new_capacity = self._calculate_new_capacity(action, current, room_obj.capacity)
            await self.update(db_session=db_session, id=vault_obj.id, obj_in={field: new_capacity}, commit=False)
            await db_session.commit()

    async def _handle_capacity_room(
        self, db_session: AsyncSession, vault_obj: Vault, room_obj: Room, action: RoomActionEnum
    ) -> None:
        """Handle capacity room updates."""
        from app.schemas.vault import VaultUpdate

        # Living rooms: ability=Charisma
        if room_obj.ability == SPECIALEnum.CHARISMA:
            new_population_max = self._calculate_new_capacity(action, vault_obj.population_max or 0, room_obj.capacity)
            await self.update(db_session, vault_obj.id, VaultUpdate(population_max=new_population_max))
        elif room_obj.ability == SPECIALEnum.ENDURANCE and room_obj.capacity is not None:
            storage_result = await db_session.execute(select(Storage).where(Storage.vault_id == vault_obj.id))
            storage_obj = storage_result.scalars().first()

            if storage_obj is None:
                storage_obj = await self.create_storage(db_session=db_session, vault_id=vault_obj.id)

            current_max_space = storage_obj.max_space
            new_storage_space_max = self._calculate_new_capacity(action, current_max_space, room_obj.capacity)
            await self.update_storage(db_session, vault_obj.id, new_storage_space_max)

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
            .where(Vault.deleted_at.is_(None))
            .group_by(Vault.id)
        )

        vaults = result.all()
        return [
            VaultReadWithNumbers(
                **vault_obj.model_dump(),
                room_count=room_count,
                dweller_count=dweller_count,
                resource_warnings=ResourceManager._check_resource_warnings(
                    vault_obj,
                    {
                        "power": float(vault_obj.power),
                        "food": float(vault_obj.food),
                        "water": float(vault_obj.water),
                    },
                ),
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
            resource_warnings=ResourceManager._check_resource_warnings(
                vault_obj,
                {
                    "power": float(vault_obj.power),
                    "food": float(vault_obj.food),
                    "water": float(vault_obj.water),
                },
            ),
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

    async def deposit_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int, commit: bool = True):
        """Deposit the specified amount to the vault's bottle caps as part of a revenue operation."""
        await self.update(
            db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps + amount), commit=commit
        )

        # Emit resource collected event for objective tracking
        from app.services.event_bus import GameEvent, event_bus

        await event_bus.emit(GameEvent.RESOURCE_COLLECTED, vault_obj.id, {"resource_type": "caps", "amount": amount})

    async def withdraw_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int):
        """Withdraw the specified amount from the vault's bottle caps as part of a spending operation."""
        if vault_obj.bottle_caps < amount:
            amount_needed = amount - vault_obj.bottle_caps
            raise InsufficientResourcesException(resource_name="bottle caps", resource_amount=amount_needed)
        await self.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps - amount))

    async def delete(self, db_session: AsyncSession, id: UUID4, soft: bool = True) -> Vault:
        """Delete vault and its associated gamestate."""
        # First, delete the associated gamestate if it exists
        result = await db_session.execute(select(GameState).where(GameState.vault_id == id))
        gamestate = result.scalar_one_or_none()
        if gamestate:
            await db_session.delete(gamestate)
            await db_session.commit()

        # Now delete the vault using the base class method with soft parameter
        return await super().delete(db_session, id, soft=soft)


vault = CRUDVault(Vault)
