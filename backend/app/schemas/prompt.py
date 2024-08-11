from pydantic import UUID4

from app.models.prompt import PromptBase
from app.utils.partial import optional


class PromptCreate(PromptBase):
    pass


class PromptRead(PromptBase):
    id: UUID4


@optional()
class PromptUpdate(PromptBase):
    pass
