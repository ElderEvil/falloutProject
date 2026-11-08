from uuid import UUID

from app.models.prompt import PromptBase
from app.utils.partial import optional


class PromptCreate(PromptBase):
    pass


class PromptRead(PromptBase):
    id: UUID


@optional()
class PromptUpdate(PromptBase):
    pass
