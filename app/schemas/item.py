from pydantic import UUID4

from app.models.item import ItemBase
from app.utils.partial import optional


class ItemCreate(ItemBase):
    pass


class ItemRead(ItemBase):
    id: UUID4


@optional()
class ItemUpdate(ItemBase):
    pass
