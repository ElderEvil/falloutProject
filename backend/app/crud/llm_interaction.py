from app.crud.base import CRUDBase
from app.models.llm_interaction import LLMInteraction
from app.schemas.llm_interaction import LLMInteractionCreate


class CRUDLLMInteraction(CRUDBase[LLMInteraction, LLMInteractionCreate, None]):
    pass


llm_interaction = CRUDLLMInteraction(LLMInteraction)
