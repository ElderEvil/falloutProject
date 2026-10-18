from datetime import datetime

from pydantic import UUID4, Field, model_validator

from app.models.objective import ObjectiveBase
from app.utils.partial import optional


class ObjectiveCreate(ObjectiveBase):
    template_key: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def assign_template_key(self) -> "ObjectiveCreate":
        if self.template_key is None:
            self.template_key = f"{self.category.value}:{self.challenge.strip().lower()}"
        return self


class ObjectiveRead(ObjectiveBase):
    template_key: str | None = Field(default=None, max_length=160)
    id: UUID4
    resets_at: datetime | None = None
    next_stage_challenge: str | None = None
    progress: int
    total: int
    is_completed: bool


@optional()
class ObjectiveUpdate(ObjectiveBase):
    pass
