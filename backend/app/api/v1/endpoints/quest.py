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


@router.get("/{vault_id}/available", response_model=list[QuestRead])
async def get_available_quests(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,  # noqa: ARG001
    skip: int = 0,
    limit: int = 100,
):
    """Get available quests for a vault (respects quest chain unlocks)."""
    from sqlalchemy.orm import selectinload
    from sqlmodel import and_, select

    from app.models.quest import Quest
    from app.models.vault_quest import VaultQuestCompletionLink

    # Eagerly load requirements and rewards to avoid MissingGreenlet errors
    result = await db_session.execute(
        select(Quest)
        .options(
            selectinload(Quest.quest_requirements),
            selectinload(Quest.quest_rewards),
        )
        .join(
            VaultQuestCompletionLink,
            and_(Quest.id == VaultQuestCompletionLink.quest_id, VaultQuestCompletionLink.vault_id == vault_id),
        )
        .where(VaultQuestCompletionLink.is_visible == True)
    )
    all_quests = result.scalars().all()

    available = []
    for quest in all_quests:
        if quest.previous_quest_id is None:
            available.append(quest)
        else:
            prev_completed = await db_session.execute(
                select(VaultQuestCompletionLink).where(
                    and_(
                        VaultQuestCompletionLink.vault_id == vault_id,
                        VaultQuestCompletionLink.quest_id == quest.previous_quest_id,
                        VaultQuestCompletionLink.is_completed == True,
                    )
                )
            )
            if prev_completed.scalar_one_or_none() is not None:
                available.append(quest)

    return available[skip : skip + limit]


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
    _user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Assign dwellers to a quest party (1-3 dwellers).
    """
    from app.crud.quest_party import quest_party_crud
    from app.utils.exceptions import ValidationException

    if len(party_data.dweller_ids) > 3:
        raise ValidationException("Maximum 3 dwellers per quest")
    if len(party_data.dweller_ids) < 1:
        raise ValidationException("Minimum 1 dweller per quest")

    return await quest_party_crud.assign_party(db_session, quest_id, vault_id, party_data.dweller_ids)


@router.get("/{vault_id}/{quest_id}/party", response_model=list[dict])
async def get_quest_party(
    vault_id: UUID4,
    quest_id: UUID4,
    _user: CurrentActiveUser,
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


@router.post("/{vault_id}/{quest_id}/start", response_model=QuestRead, status_code=200)
async def start_quest(
    vault_id: UUID4,
    quest_id: UUID4,
    _user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    duration_minutes: int | None = None,
):
    """Start a quest (starts the timer)."""
    from fastapi import HTTPException

    from app.models.quest import Quest
    from app.services.prerequisite_service import prerequisite_service
    from app.services.quest_service import quest_service
    from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException

    quest = await db_session.get(Quest, quest_id)
    if quest is None:
        raise ResourceNotFoundException(Quest, identifier=quest_id)

    await db_session.refresh(quest, ["quest_requirements"])

    can_start, missing = await prerequisite_service.can_start_quest(db_session, vault_id, quest)
    if not can_start:
        raise HTTPException(status_code=400, detail=f"Missing requirements: {', '.join(missing)}")

    try:
        await quest_service.start_quest(db_session, quest_id, vault_id, duration_minutes)
        from app.crud.quest import quest_crud

        return await quest_crud.get_for_vault(db_session, quest_id, vault_id, _user)
    except (ResourceNotFoundException, AccessDeniedException):
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{vault_id}/{quest_id}/eligible-dwellers", response_model=list[dict])
async def get_eligible_dwellers(
    vault_id: UUID4,
    quest_id: UUID4,
    _user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Get dwellers eligible for a quest based on requirements."""
    from sqlmodel import select

    from app.models.dweller import Dweller
    from app.models.quest import Quest

    quest = await db_session.get(Quest, quest_id)
    if quest is None:
        from app.utils.exceptions import ResourceNotFoundException

        raise ResourceNotFoundException(Quest, identifier=quest_id)

    await db_session.refresh(quest, ["quest_requirements"])

    result = await db_session.execute(select(Dweller).where(Dweller.vault_id == vault_id, Dweller.is_deleted == False))
    dwellers = result.scalars().all()

    eligible = []
    for dweller in dwellers:
        meets_req = True
        for req in quest.quest_requirements:
            if req.requirement_type == "level" and dweller.level < req.requirement_data.get("level", 1):
                meets_req = False
                break

        if meets_req:
            eligible.append(
                {
                    "id": str(dweller.id),
                    "first_name": dweller.first_name,
                    "last_name": dweller.last_name,
                    "level": dweller.level,
                    "rarity": dweller.rarity,
                }
            )

    return eligible
