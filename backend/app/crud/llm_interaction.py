from app.crud.base import CreateSchemaType, CRUDBase, ModelType, UpdateSchemaType
from app.models.llm_interaction import LLMInteraction


class CRUDLLMInteraction(CRUDBase[ModelType, CreateSchemaType, UpdateSchemaType]):
    pass


llm_interaction = CRUDLLMInteraction(LLMInteraction)
