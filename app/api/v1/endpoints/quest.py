from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel import Session

from app import crud
from app.db.base import get_session
from app.schemas.quest import QuestCreate, QuestRead, QuestReadWithSteps, QuestUpdate

router = APIRouter()


@router.post("/quests", response_model=QuestRead)
def create_quest(quest_data: QuestCreate, db: Session = Depends(get_session)):
    return crud.quest.create(db, quest_data)


@router.get("/", response_model=list[QuestRead])
def read_quest_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    return crud.quest.get_multi(db, skip=skip, limit=limit)


@router.get("/{quest_id}", response_model=QuestReadWithSteps)
def read_quest(quest_id: UUID4, db: Session = Depends(get_session)):
    return crud.quest.get(db, quest_id)


@router.put("/{quest_id}", response_model=QuestRead)
def update_quest(quest_id: UUID4, quest_data: QuestUpdate, db: Session = Depends(get_session)):
    return crud.quest.update(db, quest_id, quest_data)


@router.delete("/{quest_id}", status_code=204)
def delete_quest(quest_id: UUID4, db: Session = Depends(get_session)):
    return crud.quest.delete(db, quest_id)
