from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.models.quest import Quest, QuestCreate, QuestUpdate, QuestRead, QuestReadWithSteps
from app.api.crud.quest import quest
from app.db.base import get_session

router = APIRouter()


@router.post("/", response_model=Quest)
def create_quest(quest_data: QuestCreate, db: Session = Depends(get_session)):
    return quest.create(db, quest_data)


@router.get("/quests/", response_model=list[QuestRead])
def read_quest_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    quests = quest.get_multi(db, skip=skip, limit=limit)
    return quests


@router.get("/quests/{quest_id}", response_model=QuestReadWithSteps)
def read_quest(quest_id: int, db: Session = Depends(get_session)):
    return quest.get(db, quest_id)


@router.put("/quests/{quest_id}", response_model=Quest)
def update_quest(quest_id: int, quest_data: QuestUpdate, db: Session = Depends(get_session)):
    return quest.update(db, quest_id, quest_data)


@router.delete("/quests/{quest_id}", status_code=204)
def delete_quest(quest_id: int, db: Session = Depends(get_session)):
    return quest.delete(db, quest_id)
