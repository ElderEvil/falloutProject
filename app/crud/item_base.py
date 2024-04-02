from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase, ModelType, CreateSchemaType, UpdateSchemaType
from app.models.dweller import Dweller
from app.models.junk import Junk

from app.utils.exceptions import IDNotFoundException, ContentNoChangeException


class CRUDItem(CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]):
    async def equip(self, db_session: AsyncSession, *, item_id: UUID4, dweller_id: UUID4) -> ModelType | None:
        dweller = await db_session.get(Dweller, dweller_id)
        if not dweller:
            raise IDNotFoundException(Dweller, id=dweller_id)

        item_attr = f"{self.model.__name__.lower()}_id"
        if getattr(dweller, item_attr, None) is not None:
            raise ContentNoChangeException(
                detail=f"Dweller {dweller_id} already has a {self.model.__name__.lower()} equipped."
            )

        item = await self.get(db_session=db_session, id=item_id)
        if not item:
            raise IDNotFoundException(self.model, id=item_id)

        setattr(dweller, item_attr, item.id)
        await db_session.commit()
        return item

    async def unequip(self, db_session: AsyncSession, *, dweller_id: UUID4) -> None:
        dweller = await db_session.get(Dweller, dweller_id)
        if not dweller:
            raise IDNotFoundException(Dweller, id=dweller_id)

        item_attr = f"{self.model.__name__.lower()}_id"
        if getattr(dweller, item_attr) is None:
            raise ContentNoChangeException(
                detail=f"Dweller {dweller_id} does not have a {self.model.__name__.lower()} equipped."
            )

        setattr(dweller, item_attr, None)
        await db_session.commit()

    def convert_to_junk(self, item) -> list[Junk]:
        raise NotImplementedError

    async def scrap(self, db_session: AsyncSession, *, item_id: UUID4) -> list[Junk]:
        item = await db_session.get(self.model, item_id)
        if not item:
            raise IDNotFoundException(self.model, id=item_id)

        junk_list = self.convert_to_junk(item)
        await db_session.delete(item)
        await db_session.commit()
        return junk_list

    def add_value_to_vault(self, item) -> None:
        raise NotImplementedError

    async def sell(self, db_session: AsyncSession, *, item_id: UUID4) -> None:
        item = await db_session.get(self.model, item_id)
        if not item:
            raise IDNotFoundException(self.model, id=item_id)

        self.add_value_to_vault(item)
        await db_session.delete(item)
        await db_session.commit()
