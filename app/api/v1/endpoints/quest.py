from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.schemas.quest import QuestCreate, QuestUpdate, QuestRead, QuestReadWithSteps
from app.crud.quest import quest
from app.db.base import get_session

router = APIRouter()


@router.post("/quests", response_model=QuestRead)
def create_quest(quest_data: QuestCreate, db: Session = Depends(get_session)):
    return quest.create(db, quest_data)


@router.get("/", response_model=list[QuestRead])
def read_quest_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    quests = quest.get_multi(db, skip=skip, limit=limit)
    return quests


@router.get("/{quest_id}", response_model=QuestReadWithSteps)
def read_quest(quest_id: int, db: Session = Depends(get_session)):
    return quest.get(db, quest_id)


@router.put("/{quest_id}", response_model=QuestRead)
def update_quest(quest_id: int, quest_data: QuestUpdate, db: Session = Depends(get_session)):
    return quest.update(db, quest_id, quest_data)


@router.delete("/{quest_id}", status_code=204)
def delete_quest(quest_id: int, db: Session = Depends(get_session)):
    return quest.delete(db, quest_id)
