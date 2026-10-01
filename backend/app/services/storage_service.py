"""Vault inventory service: assemble the storage item lists and resolve missing art."""

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud import storage as storage_crud
from app.models.storage import Storage
from app.models.vault import Vault
from app.schemas.item import ItemRead
from app.schemas.junk import JunkRead
from app.schemas.outfit import OutfitRead
from app.schemas.pet import PetRead
from app.schemas.storage import StorageItemsResponse
from app.schemas.weapon import WeaponRead
from app.utils.exceptions import ResourceNotFoundException
from app.utils.junk_assets import get_junk_image_url
from app.utils.pet_assets import get_pet_image_url

logger = logging.getLogger(__name__)


class StorageService:
    """Read model for a vault's inventory, resolving legacy art on the way out."""

    async def get_items(self, db_session: AsyncSession, vault: Vault) -> StorageItemsResponse:
        """Every item in the vault's storage, grouped by kind, with missing images filled in.

        Raises:
            ResourceNotFoundException: If the vault has no storage row.
        """
        storage = await storage_crud.get_storage_by_vault(db_session, vault.id)
        if storage is None:
            raise ResourceNotFoundException(Storage, identifier=vault.id)

        items = await storage_crud.get_all_items(db_session, storage.id)
        response = StorageItemsResponse(
            weapons=[WeaponRead.model_validate(w) for w in items["weapons"]],
            outfits=[OutfitRead.model_validate(o) for o in items["outfits"]],
            junk=[self._with_junk_art(JunkRead.model_validate(j)) for j in items["junk"]],
            items=[ItemRead.model_validate(item) for item in items["items"]],
            pets=[self._with_pet_art(PetRead.model_validate(p)) for p in items["pets"]],
        )
        logger.info(
            "Storage items retrieved",
            extra={
                "vault_id": str(vault.id),
                "weapons_count": len(response.weapons),
                "outfits_count": len(response.outfits),
                "junk_count": len(response.junk),
                "items_count": len(response.items),
                "pets_count": len(response.pets),
            },
        )
        return response

    @staticmethod
    def _with_junk_art(read: JunkRead) -> JunkRead:
        """Legacy junk rows may lack an image URL; fall back to the name-keyed art."""
        if not read.image_url:
            read.image_url = get_junk_image_url(read.name)
        return read

    @staticmethod
    def _with_pet_art(read: PetRead) -> PetRead:
        """Legacy/generic pet rows may lack an image URL; fall back to the name-keyed art."""
        if not read.image_url:
            read.image_url = get_pet_image_url(read.name)
        return read


storage_service = StorageService()
