import random
from typing import Any

from pydantic import UUID4
from sqlalchemy import update
from sqlalchemy.orm import aliased
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CreateSchemaType, CRUDBase, ModelType, UpdateSchemaType

# from app.crud.mixins import SellItemMixin
from app.models import Outfit, Storage, Vault, Weapon
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.schemas.common import ItemTypeEnum, JunkTypeEnum, RarityEnum
from app.utils.exceptions import ContentNoChangeException, InvalidItemAssignmentException, ResourceNotFoundException

SAME_RARITY_JUNK_PROBABILITY = 0.4
DIFFERENT_RARITY_JUNK_PROBABILITY = 0.6


class CRUDItem(
    CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType],
    # SellItemMixin[ModelType]
):
    async def create(self, db_session: AsyncSession, obj_in: CreateSchemaType | dict) -> ModelType:
        obj_in = obj_in if isinstance(obj_in, dict) else obj_in.model_dump()
        if obj_in.get("storage_id") and obj_in.get("dweller_id"):
            raise InvalidItemAssignmentException(self.model)
        return await super().create(db_session, obj_in)

    async def update(
        self,
        db_session: AsyncSession,
        id: int | UUID4,
        obj_in: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        if obj_in.storage_id and obj_in.dweller_id:
            raise InvalidItemAssignmentException(self.model)
        return await super().update(db_session, id=id, obj_in=obj_in)

    async def equip(self, *, db_session: AsyncSession, item_id: UUID4, dweller_id: UUID4) -> ModelType:
        from sqlalchemy.orm import selectinload

        # Determine which relationship to eager load (weapon or outfit)
        item_attr = self.model.__name__.lower()

        query = (
            select(Dweller, self.model)
            .outerjoin(self.model, (Dweller.id == self.model.dweller_id) | (self.model.id == item_id))
            .where(Dweller.id == dweller_id)
            .options(selectinload(Dweller.vault).selectinload(Vault.storage), selectinload(getattr(Dweller, item_attr)))
        )
        result = await db_session.execute(query)
        row = result.first()

        if not row or not row.Dweller:
            raise ResourceNotFoundException(Dweller, identifier=dweller_id)

        dweller, item = row

        if not item:
            # The item wasn't found in the join, so we need to fetch it separately
            item = await db_session.get(self.model, item_id)
            if not item:
                raise ResourceNotFoundException(self.model, identifier=item_id)

        current_item = getattr(dweller, item_attr)

        if current_item:
            if current_item.id == item_id:
                raise ContentNoChangeException(detail=f"Dweller {dweller_id} already has this {item_attr} equipped.")
            # Unequip the current item
            current_item.dweller_id = None
            current_item.storage_id = dweller.vault.storage.id
            db_session.add(current_item)

        # Equip the new item
        item.dweller_id = dweller.id
        item.storage_id = None
        setattr(dweller, item_attr, item)

        db_session.add(item)
        db_session.add(dweller)
        await db_session.commit()
        await db_session.refresh(item)

        return item

    @staticmethod
    async def _fetch_unequip_data(
        db_session: AsyncSession, item_id: UUID4
    ) -> tuple[Dweller, UUID4, str] | tuple[None, None, None]:
        WeaponAlias, OutfitAlias = aliased(Weapon), aliased(Outfit)  # noqa: N806

        query = (
            select(Dweller, Storage.id.label("storage_id"), (WeaponAlias.id != None).label("is_weapon"))  # noqa: E711
            .select_from(Dweller)
            .join(Vault, Dweller.vault_id == Vault.id)
            .join(Storage, Vault.id == Storage.vault_id)
            .outerjoin(WeaponAlias, (Dweller.id == WeaponAlias.dweller_id) & (WeaponAlias.id == item_id))
            .outerjoin(OutfitAlias, (Dweller.id == OutfitAlias.dweller_id) & (OutfitAlias.id == item_id))
            .where((WeaponAlias.id == item_id) | (OutfitAlias.id == item_id))
        )

        result = await db_session.execute(query)
        row = result.first()

        if not row:
            return None, None, None

        dweller, storage_id, is_weapon = row
        item_type = ItemTypeEnum.WEAPON if is_weapon else ItemTypeEnum.OUTFIT

        return dweller, storage_id, item_type

    @staticmethod
    def _get_item_model(item_type: str) -> type[Weapon | Outfit]:
        return Weapon if item_type == ItemTypeEnum.WEAPON else Outfit

    @staticmethod
    async def _update_item(
        db_session: AsyncSession, item_model: type[Weapon | Outfit], item_id: UUID4, storage_id: UUID4
    ) -> None:
        await db_session.execute(
            update(item_model).where(item_model.id == item_id).values(dweller_id=None, storage_id=storage_id)
        )

    @staticmethod
    async def _update_dweller(db_session: AsyncSession, dweller: Dweller, item_type: str) -> None:
        setattr(dweller, item_type, None)
        db_session.add(dweller)

    async def unequip(self, *, db_session: AsyncSession, item_id: UUID4) -> None:
        dweller, storage_id, item_type = await self._fetch_unequip_data(db_session, item_id)

        if not dweller:
            raise ResourceNotFoundException(Dweller, identifier=item_id)

        item_model = self._get_item_model(item_type)

        await self._update_item(db_session, item_model, item_id, storage_id)
        await self._update_dweller(db_session, dweller, item_type)

        await db_session.commit()

    @staticmethod
    def convert_to_junk(item: Weapon | Outfit) -> list[Junk]:
        """
        Converts an item into junk based on its rarity.
        Junk is generated with probabilities depending on the item's rarity.
        """
        legendary_junk, rare_junk, common_junk = (random.choice(list(JunkTypeEnum)) for _ in range(3))

        # Determine junk options based on item rarity
        match item.rarity:
            case RarityEnum.LEGENDARY:
                junk_options = {
                    legendary_junk: (RarityEnum.LEGENDARY, SAME_RARITY_JUNK_PROBABILITY),
                    rare_junk: (RarityEnum.RARE, DIFFERENT_RARITY_JUNK_PROBABILITY),
                }
            case RarityEnum.RARE:
                junk_options = {
                    rare_junk: (RarityEnum.RARE, SAME_RARITY_JUNK_PROBABILITY),
                    common_junk: (RarityEnum.COMMON, DIFFERENT_RARITY_JUNK_PROBABILITY),
                }
            case RarityEnum.COMMON:
                junk_options = {common_junk: (RarityEnum.COMMON, DIFFERENT_RARITY_JUNK_PROBABILITY)}
            case _:
                error_message = f"Item rarity {item.rarity} is not supported for scrapping."
                raise ValueError(error_message)

        # Generate junk based on the defined probabilities
        junk_results = []

        # Junk value by rarity
        junk_value_map = {
            RarityEnum.COMMON: 2,
            RarityEnum.RARE: 50,
            RarityEnum.LEGENDARY: 200,
        }

        for junk_type, (rarity, probability) in junk_options.items():
            if random.random() < probability:
                junk_results.append(
                    Junk(
                        name=junk_type.value,
                        junk_type=junk_type,
                        rarity=rarity,
                        value=junk_value_map.get(rarity, 2),
                        description=f"Derived from {item.name}",
                    )
                )

        return junk_results

    async def scrap(self, *, db_session: AsyncSession, item_id: UUID4) -> list[Junk]:
        item = await db_session.get(self.model, item_id)
        if not item:
            raise ResourceNotFoundException(self.model, identifier=item_id)

        # Get storage_id from the item before deleting
        storage_id = item.storage_id

        junk_list = self.convert_to_junk(item)

        # Assign junk items to the same storage
        if storage_id:
            for junk in junk_list:
                junk.storage_id = storage_id
                db_session.add(junk)

        await db_session.delete(item)
        await db_session.commit()

        # Refresh junk items to get IDs
        for junk in junk_list:
            if junk.id:
                await db_session.refresh(junk)

        return junk_list

    @staticmethod
    async def add_caps_to_vault(db_session: AsyncSession, vault_id: UUID4, value: int) -> None:
        """Add value to the vault's resources."""
        vault = await db_session.get(Vault, vault_id)
        if not vault:
            raise ResourceNotFoundException(Vault, identifier=vault_id)

        vault.bottle_caps += value
        db_session.add(vault)
        await db_session.commit()

    async def sell(self, db_session: AsyncSession, *, item_id: UUID4) -> None:
        from sqlmodel import select

        item = await db_session.get(self.model, item_id)
        if not item:
            raise ResourceNotFoundException(self.model, identifier=item_id)

        # Get vault_id without lazy loading relationships
        vault_id = None
        if item.storage_id:
            # Item is in storage - get vault via storage
            storage_result = await db_session.execute(select(Storage.vault_id).where(Storage.id == item.storage_id))
            vault_id = storage_result.scalar_one_or_none()
        elif item.dweller_id:
            # Item is equipped - get vault via dweller
            from app.models.dweller import Dweller

            dweller_result = await db_session.execute(select(Dweller.vault_id).where(Dweller.id == item.dweller_id))
            vault_id = dweller_result.scalar_one_or_none()

        if not vault_id:
            raise ResourceNotFoundException(Vault, identifier="Unknown - item has no storage or dweller")

        await self.add_caps_to_vault(db_session, vault_id, item.value)
        await db_session.delete(item)
        await db_session.commit()
