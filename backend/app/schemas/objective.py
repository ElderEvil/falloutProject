from pydantic import UUID4

from app.models.objective import ObjectiveBase
from app.utils.partial import optional


class ObjectiveCreate(ObjectiveBase):
    pass


class QuestObjectiveRead(ObjectiveBase):
    id: UUID4


@optional()
class ObjectiveUpdate(ObjectiveBase):
    pass
