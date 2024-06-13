from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.db.session import get_async_session
from app.models.quest import QuestObjective
from app.schemas.quest import QuestCreate, QuestRead, QuestReadWithObjectives, QuestUpdate
from app.utils.load_quests import load_quest_chain_from_json

router = APIRouter()


@router.post("/quests", response_model=QuestRead)
async def create_quest(quest_data: QuestCreate, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.quest_crud.create(db_session, quest_data)


@router.get("/", response_model=list[QuestRead])
async def read_quest_list(skip: int = 0, limit: int = 100, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.quest_crud.get_multi(db_session, skip=skip, limit=limit)


@router.get("/{quest_id}", response_model=QuestReadWithObjectives)
async def read_quest(quest_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.quest_crud.get(db_session, quest_id)


@router.put("/{quest_id}", response_model=QuestRead)
async def update_quest(
    quest_id: UUID4,
    quest_data: QuestUpdate,
    db_session: AsyncSession = Depends(get_async_session),
):
    return await crud.quest_crud.update(db_session, quest_id, quest_data)


@router.delete("/{quest_id}", status_code=204)
async def delete_quest(quest_id: UUID4, db_session: AsyncSession = Depends(get_async_session)):
    return await crud.quest_crud.delete(db_session, quest_id)


@router.post("/upload-quest-chain/")
async def upload_quest_chain(file: UploadFile = File(...), db_session: AsyncSession = Depends(get_async_session)):
    if file.content_type != "application/json":
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload a JSON file.")

    quest_chain_data = load_quest_chain_from_json("data/quests/multi_stage/power_struggle.json")
    await crud.quest_chain_crud.insert_quest_chain(db_session, quest_chain_data)
    return {"status": "success"}


@router.post("/{vault_id}/objectives/{objective_id}/complete", response_model=QuestObjective)
async def complete_objective(objective_id: UUID4, db: AsyncSession = Depends(get_async_session)):
    return await crud.objective_crud.complete(db, objective_id)
