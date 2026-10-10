"""Pets: owned inventory entities equipped to a dweller (Phase A)."""

import logging
from collections.abc import Sequence

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.item_base import get_item_vault_id, get_items_by_vault
from app.crud.pet import pet as pet_crud
from app.models.pet import Pet
from app.models.user import User
from app.services.access_service import get_accessible_vault, verify_dweller_access
from app.utils.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)


class PetService:
    """Thin pet operations: vault-scoped list, equip, unequip.

    Ownership is validated through ``access_service`` (the same policy the API
    dependency layer wraps), so the service stays transport-free.
    """

    async def list_pets(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        user: User,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Pet]:
        """Pets of a vault (in storage or equipped), scoped to the owning user."""
        await get_accessible_vault(vault_id, user, db_session)
        return await get_items_by_vault(db_session, Pet, vault_id, skip, limit)

    async def get_pet(self, db_session: AsyncSession, pet_id: UUID4, user: User) -> Pet:
        """One pet, verified to belong to a vault the user can access."""
        pet = await pet_crud.get(db_session, pet_id)
        await self._verify_pet_vault(db_session, pet, user)
        return pet

    async def equip(self, db_session: AsyncSession, dweller_id: UUID4, pet_id: UUID4, user: User) -> Pet:
        """Equip a pet on a dweller of the same vault.

        The dweller must belong to a vault the user owns, and the pet must
        belong to that same vault.
        """
        dweller = await verify_dweller_access(dweller_id, user, db_session)
        pet = await pet_crud.get(db_session, pet_id)
        pet_vault_id = await get_item_vault_id(db_session, pet)
        if pet_vault_id is None or pet_vault_id != dweller.vault_id:
            raise ResourceNotFoundException(Pet, identifier=pet_id)
        return await pet_crud.equip(db_session=db_session, item_id=pet_id, dweller_id=dweller_id)

    async def unequip(self, db_session: AsyncSession, pet_id: UUID4, user: User) -> None:
        """Return an equipped pet to its vault's storage."""
        pet = await pet_crud.get(db_session, pet_id)
        await self._verify_pet_vault(db_session, pet, user)
        await pet_crud.unequip(db_session=db_session, item_id=pet_id)

    @staticmethod
    async def _verify_pet_vault(db_session: AsyncSession, pet: Pet, user: User) -> None:
        vault_id = await get_item_vault_id(db_session, pet)
        if vault_id is None:
            raise ResourceNotFoundException(Pet, identifier=pet.id)
        await get_accessible_vault(vault_id, user, db_session)


# Singleton instance
pet_service = PetService()
