from pydantic import UUID4

from app.models.item import ItemBase
from app.schemas.common import ItemTypeEnum
from app.utils.partial import optional


class ItemCreate(ItemBase):
    item_type: ItemTypeEnum = ItemTypeEnum.MISC
    storage_id: UUID4 | None = None


class ItemRead(ItemBase):
    id: UUID4
    item_type: ItemTypeEnum
    storage_id: UUID4 | None


@optional()
class ItemUpdate(ItemBase):
    pass
