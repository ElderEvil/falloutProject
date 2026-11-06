from datetime import datetime

from pydantic import UUID4, computed_field

from app.models.item import ItemBase
from app.options.pet_modifiers import PetEffect, pet_description_for_name, pet_effect_for_name
from app.utils.partial import optional


class PetCreate(ItemBase):
    # Optional fields - can be omitted, but if provided must be valid UUID
    storage_id: UUID4 | None = None


class PetEffectRead(PetEffect):
    """Wire shape for the catalog-resolved bonus a pet grants.

    Fields come from ``PetEffect``; the empty subclass keeps the public schema
    name stable for generated clients. All-zero for pets without a catalog
    entry, so the client can always read the shape without a null check.
    """


class PetRead(ItemBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None

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
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None
