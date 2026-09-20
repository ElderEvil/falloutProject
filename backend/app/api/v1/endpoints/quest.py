"""Quest endpoints."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.quest import Quest
from app.models.team import TeamMember
from app.schemas.quest import (
    EligibleDwellerRead,
    QuestCompleteResponse,
    QuestCreate,
    QuestPartyAssign,
    QuestPartyMemberRead,
    QuestRead,
    QuestUpdate,
)
from app.schemas.rewards import granted_reward_adapter
from app.services.progression.quests.service import quest_service
from app.services.team_service import team_service
from app.utils.exceptions import ResourceNotFoundException, ValidationException

router = APIRouter(prefix="/quests", tags=["Quest"])


def _to_party_member_read(member: TeamMember, quest_id: UUID4, vault_id: UUID4) -> QuestPartyMemberRead:
    """Map a team member into the quest wire contract (quest/vault come from the team)."""
    slot_number = member.slot_number
    if slot_number is None:
        raise ValidationException("Quest team member is missing a slot number")
    return QuestPartyMemberRead(
        id=member.id,
        quest_id=quest_id,
        vault_id=vault_id,
        dweller_id=member.dweller_id,
        slot_number=slot_number,
        status=member.status,
        created_at=member.created_at.isoformat() if member.created_at else None,
        updated_at=member.updated_at.isoformat() if member.updated_at else None,
    )


@router.get("/", response_model=list[QuestRead])
async def read_all_quests(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[QuestRead]:
    """Get all available quests (not vault-specific).

    Returns:
        List of quests.
    """
    return await crud.quest_crud.get_multi(db_session, skip=skip, limit=limit)


@router.post("/{vault_id}/", response_model=QuestRead)
async def create_quest(
    quest_data: QuestCreate,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Quest:
    """Create a new quest.

    Returns:
        The created quest.
    """
    return await crud.quest_crud.create(db_session, quest_data)


@router.get("/{vault_id}/", response_model=list[QuestRead])
async def read_vault_quests(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[QuestRead]:
    """Get all quests assigned to a specific vault.

    Returns:
        List of quests for the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    await quest_service.check_and_complete_quests(db_session, vault_id=vault_id)
    return await quest_service.get_quests_for_vault(db_session, vault_id, skip, limit)


@router.get("/{vault_id}/available", response_model=list[QuestRead])
async def get_available_quests(
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[QuestRead]:
    """Get available quests for a vault (respects chain unlocks, requirements, and the Office rule).

    Returns:
        List of available quests.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await quest_service.get_quests_for_vault(db_session, vault_id, skip, limit, available_only=True)


@router.get("/{vault_id}/{quest_id}", response_model=QuestRead)
async def read_quest(
    quest_id: UUID4,
    user: CurrentActiveUser,
    vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Quest:
    """Retrieve a quest by ID within a vault.

    Returns:
        The requested quest.

    Raises:
        ResourceNotFoundException: If the quest is not linked to the vault.
    """
    await get_user_vault_or_403(vault_id, user, db_session)

    link = await crud.quest_crud.get_link(db_session, quest_id=quest_id, vault_id=vault_id)
    if link is None:
        raise ResourceNotFoundException(Quest, identifier=quest_id)

    return await crud.quest_crud.get(db_session, quest_id)


@router.put("/{vault_id}/{quest_id}", response_model=QuestRead)
async def update_quest(
    quest_id: UUID4,
    quest_data: QuestUpdate,
    _vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> Quest:
    """Update a quest definition (administrators only).

    Quests are global templates shared by every vault, so vault ownership cannot
    authorize this write — editing one here would change it for all players.

    Returns:
        The updated quest.
    """
    return await crud.quest_crud.update(db_session, quest_id, quest_data)


@router.delete("/{vault_id}/{quest_id}", status_code=204)
async def delete_quest(
    quest_id: UUID4,
    _vault_id: UUID4,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> None:
    """Delete a quest definition (administrators only).

    Like update, this removes a global template shared by every vault.
    """
    await crud.quest_crud.delete(db_session, quest_id)


@router.post("/{vault_id}/{quest_id}/assign", status_code=201)
async def assign_quest_to_vault(
    vault_id: UUID4,
    quest_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    *,
    is_visible: bool = True,
):
    """Assign a quest to a vault, making it available for completion.

    Returns:
        The vault-quest assignment.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await crud.quest_crud.assign_to_vault(
        db_session=db_session, quest_id=quest_id, vault_id=vault_id, is_visible=is_visible
    )


@router.post("/{vault_id}/{quest_id}/claim-rewards", response_model=QuestCompleteResponse, status_code=200)
async def claim_quest_rewards(
    vault_id: UUID4,
    quest_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> QuestCompleteResponse:
    """Claim rewards from a returned quest party.

    Returns:
        Completion response with granted rewards.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    quest, granted_rewards = await quest_service.claim_quest_rewards(db_session, quest_id, vault_id)
    return QuestCompleteResponse(
        quest_id=quest.id,
        quest_title=quest.title,
        is_completed=True,
        granted_rewards=[granted_reward_adapter.validate_python(reward) for reward in granted_rewards],
    )


@router.post("/{vault_id}/{quest_id}/assign-party", response_model=list[QuestPartyMemberRead], status_code=201)
async def assign_party_to_quest(
    vault_id: UUID4,
    quest_id: UUID4,
    party_data: QuestPartyAssign,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """Assign dwellers to a quest party (1-3 dwellers).

    Returns:
        The assigned party members.

    Raises:
        ValidationException: If party size is invalid or assignment fails.
    """
    await get_user_vault_or_403(vault_id, user, db_session)

    members = await team_service.assign_quest_team(db_session, quest_id, vault_id, party_data.dweller_ids)
    return [_to_party_member_read(member, quest_id, vault_id) for member in members]


@router.get("/{vault_id}/{quest_id}/party", response_model=list[QuestPartyMemberRead])
async def get_quest_party(
    vault_id: UUID4,
    quest_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[QuestPartyMemberRead]:
    """Get party members assigned to a quest.

    Returns:
        List of party members.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    members = await crud.team_crud.get_quest_team(db_session, quest_id, vault_id)
    return [_to_party_member_read(member, quest_id, vault_id) for member in members]


@router.post("/{vault_id}/{quest_id}/start", response_model=QuestRead, status_code=200)
async def start_quest(
    vault_id: UUID4,
    quest_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Quest:
    """Start a quest (starts the timer).

    Returns:
        The started quest.

    Raises:
        ResourceNotFoundException: If quest not found.
        ValidationException: If requirements not met or quest cannot be started.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    quest = await db_session.get(Quest, quest_id)
    if quest is None:
        from app.utils.exceptions import ResourceNotFoundException

        raise ResourceNotFoundException(Quest, identifier=quest_id)

    await db_session.refresh(quest, ["quest_requirements"])

    availability = await quest_service.get_quest_availability(db_session, vault_id, quest)
    if not availability.available:
        detail = (
            f"Missing requirements: {', '.join(availability.missing)}"
            if availability.missing
            else (availability.lock_reason or "Quest is not available")
        )
        raise ValidationException(detail=detail)

    try:
        await quest_service.start_quest(db_session, quest_id, vault_id)
    except ValueError as e:
        raise ValidationException(str(e)) from e
    else:
        await db_session.refresh(quest, ["quest_requirements", "quest_rewards"])
        return quest


@router.get("/{vault_id}/{quest_id}/eligible-dwellers", response_model=list[EligibleDwellerRead])
async def get_eligible_dwellers(
    vault_id: UUID4,
    quest_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[EligibleDwellerRead]:
    """Get dwellers eligible for a quest based on requirements.

    Returns:
        List of eligible dwellers.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    return await quest_service.get_eligible_dwellers(db_session, vault_id, quest_id)
