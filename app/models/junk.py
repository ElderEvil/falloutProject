from app.models.base import BaseUUIDModel, TimeStampMixin
from app.models.item import ItemBase
from app.schemas.common import JunkType, Rarity


class JunkBase(ItemBase):
    junk_type: JunkType
    description: str

    _value_by_rarity = {  # noqa: RUF012
        Rarity.common: 2,
        Rarity.rare: 50,
        Rarity.legendary: 200,
    }


class Junk(BaseUUIDModel, JunkBase, TimeStampMixin, table=True): ...
