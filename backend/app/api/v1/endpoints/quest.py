from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser
from app.db.session import get_async_session
from app.schemas.quest import (
    QuestCompleteResponse,
    QuestCreate,
    QuestPartyAssign,
    QuestRead,
    QuestUpdate,
)

router = APIRouter()


@router.get("/", response_model=list[QuestRead])
async def read_all_quests(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,  # noqa: ARG001
    skip: int = 0,
    limit: int = 100,
):
    """Get all available quests (not vault-specific)."""
    return await crud.quest_crud.get_multi(db_session, skip=skip, limit=limit)


@router.post("/{vault_id}/", response_model=QuestRead)
async def create_quest(
    quest_data: QuestCreate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
):
    return await crud.quest_crud.create(db_session, quest_data)


@router.get("/{vault_id}/", response_model=list[QuestRead])
async def read_vault_quests(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,  # noqa: ARG001
    skip: int = 0,
    limit: int = 100,
):
    """Get all quests assigned to a specific vault."""
    return await crud.quest_crud.get_multi_for_vault(db_session=db_session, vault_id=vault_id, skip=skip, limit=limit)


@router.get("/{vault_id}/{quest_id}", response_model=QuestRead)
async def read_quest(
    quest_id: UUID4,
    user: CurrentActiveUser,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await crud.quest_crud.get_for_vault(db_session=db_session, quest_id=quest_id, vault_id=vault_id, user=user)


@router.put("/{vault_id}/{quest_id}", response_model=QuestRead)
async def update_quest(
    quest_id: UUID4,
    quest_data: QuestUpdate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    return await crud.quest_crud.update(db_session, quest_id, quest_data)


@router.delete("/{vault_id}/{quest_id}", status_code=204)
async def delete_quest(quest_id: UUID4, db_session: Annotated[AsyncSession, Depends(get_async_session)]):
    return await crud.quest_crud.delete(db_session, quest_id)


@router.post("/{vault_id}/{quest_id}/assign", status_code=201)
async def assign_quest_to_vault(
    vault_id: UUID4,
    quest_id: UUID4,
    user: CurrentActiveUser,  # noqa: ARG001
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    *,
    is_visible: bool = True,
):
    """
    Assign a quest to a vault, making it available for completion.
    """
    return await crud.quest_crud.assign_to_vault(
        db_session=db_session, quest_id=quest_id, vault_id=vault_id, is_visible=is_visible
    )


@router.post("/{vault_id}/{quest_id}/complete", response_model=QuestCompleteResponse, status_code=200)
async def complete_quest(
    vault_id: UUID4,
    quest_id: UUID4,
    user: CurrentActiveUser,  # noqa: ARG001
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Mark a quest as completed for a vault.
    """

    from app.crud.quest_party import quest_party_crud
    from app.models.dweller import Dweller

    quest, granted_rewards = await crud.quest_crud.complete(
        db_session=db_session, quest_entity_id=quest_id, vault_id=vault_id
    )

    party = await quest_party_crud.get_party_for_quest(db_session, quest_id, vault_id)
    for member in party:
        dweller = await db_session.get(Dweller, member.dweller_id)
        if dweller:
            dweller.status = "idle"
    await db_session.commit()

    return QuestCompleteResponse(
        quest_id=quest.id,
        quest_title=quest.title,
        is_completed=True,
        granted_rewards=granted_rewards,
    )


@router.post("/{vault_id}/{quest_id}/assign-party", status_code=201)
async def assign_party_to_quest(
    vault_id: UUID4,
    quest_id: UUID4,
    party_data: QuestPartyAssign,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Assign dwellers to a quest party (1-3 dwellers).
    """
    from app.crud.quest_party import quest_party_crud

    if len(party_data.dweller_ids) > 3:
        raise ValueError("Maximum 3 dwellers per quest")

    return await quest_party_crud.assign_party(db_session, quest_id, vault_id, party_data.dweller_ids)


@router.get("/{vault_id}/{quest_id}/party", response_model=list[dict])
async def get_quest_party(
    vault_id: UUID4,
    quest_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get party members assigned to a quest."""
    from app.crud.quest_party import quest_party_crud

    party = await quest_party_crud.get_party_for_quest(db_session, quest_id, vault_id)
    return [
        {
            "id": str(p.id),
            "quest_id": str(p.quest_id),
            "vault_id": str(p.vault_id),
            "dweller_id": str(p.dweller_id),
            "slot_number": p.slot_number,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in party
    ]


@router.post("/{vault_id}/{quest_id}/start", status_code=200)
async def start_quest(
    vault_id: UUID4,
    quest_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    duration_minutes: int | None = None,
):
    """Start a quest (starts the timer)."""
    from app.services.quest_service import quest_service

    return await quest_service.start_quest(db_session, quest_id, vault_id, duration_minutes)
