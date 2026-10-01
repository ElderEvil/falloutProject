from dataclasses import asdict
from datetime import datetime

from pydantic import UUID4, BaseModel, computed_field

from app.models.item import ItemBase
from app.options.pet_modifiers import pet_effect_for_name
from app.utils.partial import optional


class PetCreate(ItemBase):
    # Optional fields - can be omitted, but if provided must be valid UUID
    storage_id: UUID4 | None = None


class PetEffectRead(BaseModel):
    """Wire shape for the catalog-resolved bonus a pet grants.

    Mirrors ``PetEffect``; all-zero for pets without a catalog entry, so the
    client can always read the shape without a null check.
    """

    strength: int = 0
    perception: int = 0
    endurance: int = 0
    charisma: int = 0
    intelligence: int = 0
    agility: int = 0
    luck: int = 0
    max_health: int = 0
    damage_pct: float = 0.0
    incident_response_pct: float = 0.0
    radiation_resist_pct: float = 0.0
    happiness: float = 0.0
    caps_pct: float = 0.0
    xp_pct: float = 0.0
    training_speed_pct: float = 0.0


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
        return PetEffectRead(**asdict(pet_effect_for_name(self.name)))


@optional()
class PetUpdate(ItemBase):
    dweller_id: UUID4 | None = None
    storage_id: UUID4 | None = None
