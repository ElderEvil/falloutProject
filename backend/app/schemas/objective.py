from pydantic import UUID4

from app.models.objective import ObjectiveBase
from app.utils.partial import optional


class ObjectiveCreate(ObjectiveBase):
    pass


class ObjectiveRead(ObjectiveBase):
    id: UUID4
    progress: int
    total: int
    is_completed: bool


@optional()
class ObjectiveUpdate(ObjectiveBase):
    pass
