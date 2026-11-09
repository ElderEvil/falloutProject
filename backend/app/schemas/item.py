from uuid import UUID

from app.core.enums import ItemTypeEnum
from app.models.item import ItemBase
from app.utils.partial import optional


class ItemCreate(ItemBase):
    item_type: ItemTypeEnum = ItemTypeEnum.MISC
    storage_id: UUID | None = None


class ItemRead(ItemBase):
    id: UUID
    item_type: ItemTypeEnum
    storage_id: UUID | None


@optional()
class ItemUpdate(ItemBase):
    pass
