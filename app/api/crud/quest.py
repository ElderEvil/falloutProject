from app.api.crud.base import CRUDBase
from app.api.models.quest import Quest, QuestCreate, QuestUpdate
# from app.api.models.quest_step import QuestStep


class CRUDQuest(CRUDBase[Quest, QuestCreate, QuestUpdate]):
    ...


quest = CRUDQuest(Quest)
