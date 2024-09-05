from datetime import datetime

from pydantic import UUID4

from app.models.weapon import WeaponBase
from app.utils.partial import optional


class WeaponCreate(WeaponBase):
    pass


class WeaponRead(WeaponBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime


@optional()
class WeaponUpdate(WeaponBase):
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None
