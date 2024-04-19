import random

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase, ModelType, CreateSchemaType, UpdateSchemaType
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.schemas.common import JunkType, Rarity
from app.utils.exceptions import ResourceNotFoundException, ContentNoChangeException

SAME_RARITY_JUNK_PROBABILITY = 0.4
DIFFERENT_RARITY_JUNK_PROBABILITY = 0.6


class CRUDItem(CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]):
    async def equip(self, db_session: AsyncSession, *, item_id: UUID4, dweller_id: UUID4) -> ModelType | None:
        dweller = await db_session.get(Dweller, dweller_id)
        if not dweller:
            raise ResourceNotFoundException(Dweller, identifier=dweller_id)

        item_attr = f"{self.model.__name__.lower()}_id"
        if getattr(dweller, item_attr, None) is not None:
            raise ContentNoChangeException(
                detail=f"Dweller {dweller_id} already has a {self.model.__name__.lower()} equipped."
            )

        item = await self.get(db_session=db_session, id=item_id)
        if not item:
            raise ResourceNotFoundException(self.model, identifier=item_id)

        setattr(dweller, item_attr, item.id)
        await db_session.commit()
        return item

    async def unequip(self, db_session: AsyncSession, *, dweller_id: UUID4) -> None:
        dweller = await db_session.get(Dweller, dweller_id)
        if not dweller:
            raise ResourceNotFoundException(Dweller, identifier=dweller_id)

        item_attr = f"{self.model.__name__.lower()}_id"
        if getattr(dweller, item_attr) is None:
            raise ContentNoChangeException(
                detail=f"Dweller {dweller_id} does not have a {self.model.__name__.lower()} equipped."
            )

        setattr(dweller, item_attr, None)
        await db_session.commit()

    @staticmethod
    def convert_to_junk(item) -> list[Junk]:
        """
        Converts an item into junk based on its rarity.
        Junk is generated with probabilities depending on the item's rarity.
        """
        legendary_junk, rare_junk, common_junk = (random.choice(list(JunkType)) for _ in range(3))

        # Determine junk options based on item rarity
        match item.rarity:
            case Rarity.legendary:
                junk_options = {
                    legendary_junk: (Rarity.legendary, SAME_RARITY_JUNK_PROBABILITY),
                    rare_junk: (Rarity.rare, DIFFERENT_RARITY_JUNK_PROBABILITY),
                }
            case Rarity.rare:
                junk_options = {
                    rare_junk: (Rarity.rare, SAME_RARITY_JUNK_PROBABILITY),
                    common_junk: (Rarity.common, DIFFERENT_RARITY_JUNK_PROBABILITY),
                }
            case Rarity.common:
                junk_options = {common_junk: (Rarity.common, DIFFERENT_RARITY_JUNK_PROBABILITY)}
            case _:
                error_message = f"Item rarity {item.rarity} is not supported for scrapping."
                raise ValueError(error_message)

        # Generate junk based on the defined probabilities
        junk_results = []

        for junk_type, (rarity, probability) in junk_options.items():
            if random.random() < probability:
                junk_results.append(
                    Junk(
                        name=junk_type.value,
                        junk_type=junk_type,
                        rarity=rarity,
                        description=f"Derived from {item.name}",
                    )
                )

        return junk_results

    async def scrap(self, db_session: AsyncSession, item_id: UUID4) -> list[Junk]:
        item = await db_session.get(self.model, item_id)
        if not item:
            raise ResourceNotFoundException(self.model, identifier=item_id)

        junk_list = self.convert_to_junk(item)
        await db_session.delete(item)
        await db_session.commit()
        return junk_list

    def add_value_to_vault(self, item) -> None:
        raise NotImplementedError

    async def sell(self, db_session: AsyncSession, *, item_id: UUID4) -> None:
        item = await db_session.get(self.model, item_id)
        if not item:
            raise ResourceNotFoundException(self.model, identifier=item_id)

        self.add_value_to_vault(item)
        await db_session.delete(item)
        await db_session.commit()
