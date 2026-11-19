from uuid import UUID

from pydantic import computed_field

from app.models.item import ItemBase
from app.options.pet_modifiers import PetEffect, pet_description_for_name, pet_effect_for_name
from app.utils.partial import optional
from app.utils.serialize_types import UTCDateTimeJSON


class PetCreate(ItemBase):
    storage_id: UUID | None = None


class PetEffectRead(PetEffect):
    """Catalog-resolved pet bonus; all-zero without a catalog entry (never null).
    Empty subclass keeps the public schema name stable for generated clients.
    """


class PetRead(ItemBase):
    id: UUID
    created_at: UTCDateTimeJSON
    updated_at: UTCDateTimeJSON
    dweller_id: UUID | None = None
    storage_id: UUID | None = None

    @computed_field
    @property
    def effect(self) -> PetEffectRead:
        """The pet's catalog-resolved bonus, so clients can explain its contribution."""
        return PetEffectRead(**pet_effect_for_name(self.name).model_dump())

    @computed_field
    @property
    def description(self) -> str | None:
        """The pet's catalog description, or None when it has no catalog entry."""
        return pet_description_for_name(self.name)


@optional()
class PetUpdate(ItemBase):
    dweller_id: UUID | None = None
    storage_id: UUID | None = None
