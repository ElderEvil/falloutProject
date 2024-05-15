from collections.abc import Sequence

from pydantic import UUID4
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.crud.base import CRUDBase
from app.models.vault import Vault
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultCreate, VaultCreateWithUserID, VaultUpdate
from app.utils.exceptions import InsufficientResourcesException


class CRUDVault(CRUDBase[Vault, VaultCreate, VaultUpdate]):
    async def get_by_user_id(self, *, db_session: AsyncSession, user_id: int) -> Sequence[Vault]:
        response = await db_session.execute(select(self.model).where(self.model.user_id == user_id))
        return response.scalars().all()

    async def get_population(self, *, db_session: AsyncSession, vault_id: UUID4) -> int:
        count = await db_session.execute(select(func.count(Vault.dwellers)).where(Vault.id == vault_id))
        return count.scalar()

    async def create_with_user_id(self, db_session: AsyncSession, obj_in: VaultCreate, user_id: UUID4) -> Vault:
        obj_data = obj_in.model_dump()
        obj_data["user_id"] = user_id
        obj_in = VaultCreateWithUserID(**obj_data)
        return await super().create(db_session, obj_in)

    async def is_enough_dwellers(self, *, db_session: AsyncSession, vault_id: UUID4, population_required: int) -> bool:
        """
        Check if the vault has enough dwellers to perform an operation.
        """
        dwellers_count = await self.get_population(db_session=db_session, vault_id=vault_id)
        return dwellers_count >= population_required

    async def withdraw_caps(self, *, db_session: AsyncSession, vault_obj: Vault, amount: int):
        """Withdraw the specified amount from the vault's bottle caps as part of a spending operation."""
        if vault_obj.bottle_caps < amount:
            amount_needed = amount - vault_obj.bottle_caps
            raise InsufficientResourcesException(resource_name="bottle caps", resource_amount=amount_needed)
        await self.update(db_session, id=vault_obj.id, obj_in=VaultUpdate(bottle_caps=vault_obj.bottle_caps - amount))

    async def initiate(self, db_session: AsyncSession, obj_in: VaultCreate, user_id: UUID4) -> Vault:
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
