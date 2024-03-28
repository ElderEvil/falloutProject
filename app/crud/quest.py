from app.crud.base import CRUDBase
from app.models.quest import Quest
from app.schemas.quest import QuestCreate, QuestUpdate


class CRUDQuest(CRUDBase[Quest, QuestCreate, QuestUpdate]): ...


quest = CRUDQuest(Quest)
