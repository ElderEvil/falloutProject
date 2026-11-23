"""Quest endpoints."""

from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter

from app import crud
from app.api.deps import CurrentActiveUser, CurrentSuperuser, DBSession, PaginationParams, get_user_vault_or_403
from app.models.quest import Quest
from app.models.team import TeamMember
from app.models.vault_quest import VaultQuestCompletionLink
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
from app.services.progression.quests.rotation import ensure_current_quest_rotation
from app.services.progression.quests.service import quest_service
from app.utils.exceptions import ValidationException, ensure_found
from app.utils.serialize import serialize_optional_utc_datetime

router = APIRouter(prefix="/quests", tags=["Quest"])


def _to_party_member_read(member: TeamMember, quest_id: UUID, vault_id: UUID) -> QuestPartyMemberRead:
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
        created_at=serialize_optional_utc_datetime(member.created_at),
        updated_at=serialize_optional_utc_datetime(member.updated_at),
    )


@router.get("/", response_model=list[QuestRead])
async def read_all_quests(
    db_session: DBSession,
    _user: CurrentActiveUser,
    pagination: PaginationParams,
) -> Sequence[QuestRead]:
    """Get all available quests (not vault-specific)."""
    return await crud.quest_crud.get_multi(db_session, skip=pagination.skip, limit=pagination.limit)


# Global quest templates retain legacy vault URLs; the vault segment is unused.
@router.post("/{vault_id}/", response_model=QuestRead)  # ruff: ignore[fast-api-unused-path-parameter]
async def create_quest(
    quest_data: QuestCreate,
    db_session: DBSession,
    _: CurrentSuperuser,
) -> Quest:
    """Create a new quest."""
    return await crud.quest_crud.create(db_session, quest_data)


@router.get("/{vault_id}/", response_model=list[QuestRead])
async def read_vault_quests(
    vault_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
    pagination: PaginationParams,
) -> Sequence[QuestRead]:
    """Get all quests assigned to a specific vault."""
    await get_user_vault_or_403(vault_id, user, db_session)
    await quest_service.check_and_complete_quests(db_session, vault_id=vault_id)
    await ensure_current_quest_rotation(db_session, vault_id)
    return await quest_service.get_quests_for_vault(db_session, vault_id, pagination.skip, pagination.limit)


@router.get("/{vault_id}/available", response_model=list[QuestRead])
async def get_available_quests(
    vault_id: UUID,
    db_session: DBSession,
    user: CurrentActiveUser,
    pagination: PaginationParams,
) -> Sequence[QuestRead]:
    """Get available quests for a vault (respects chain unlocks, requirements, and the Office rule)."""
    await get_user_vault_or_403(vault_id, user, db_session)
    await ensure_current_quest_rotation(db_session, vault_id)
    return await quest_service.get_quests_for_vault(
        db_session, vault_id, pagination.skip, pagination.limit, available_only=True
    )


@router.get("/{vault_id}/{quest_id}", response_model=QuestRead)
async def read_quest(
    quest_id: UUID,
    user: CurrentActiveUser,
    vault_id: UUID,
    db_session: DBSession,
) -> Quest:
    """Retrieve a quest by ID within a vault."""
    await get_user_vault_or_403(vault_id, user, db_session)

    link = await crud.quest_crud.get_link(db_session, quest_id=quest_id, vault_id=vault_id)
    link = ensure_found(link, Quest, identifier=quest_id)

    return await crud.quest_crud.get(db_session, quest_id)


@router.put("/{vault_id}/{quest_id}", response_model=QuestRead)  # ruff: ignore[fast-api-unused-path-parameter] - global template, legacy vault URL
async def update_quest(
    quest_id: UUID,
    quest_data: QuestUpdate,
    _vault_id: UUID,
    db_session: DBSession,
    _: CurrentSuperuser,
) -> Quest:
    """Update a quest definition (administrators only).

    Quests are global templates shared by every vault, so vault ownership cannot
    authorize this write — editing one here would change it for all players.
    """
    return await crud.quest_crud.update(db_session, quest_id, quest_data)


@router.delete("/{vault_id}/{quest_id}", status_code=204)  # ruff: ignore[fast-api-unused-path-parameter] - global template, legacy vault URL
async def delete_quest(
    quest_id: UUID,
    _vault_id: UUID,
    db_session: DBSession,
    _: CurrentSuperuser,
) -> None:
    """Delete a quest definition (administrators only).

    Like update, this removes a global template shared by every vault.
    """
    await crud.quest_crud.delete(db_session, quest_id)


@router.post("/{vault_id}/{quest_id}/assign", response_model=VaultQuestCompletionLink, status_code=201)
async def assign_quest_to_vault(
    vault_id: UUID,
    quest_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
    *,
    is_visible: bool = True,
) -> VaultQuestCompletionLink:
    """Assign a quest to a vault, making it available for completion."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await quest_service.assign_quest_to_vault(
        db_session=db_session, quest_id=quest_id, vault_id=vault_id, is_visible=is_visible
    )


@router.post("/{vault_id}/{quest_id}/claim-rewards", response_model=QuestCompleteResponse, status_code=200)
async def claim_quest_rewards(
    vault_id: UUID,
    quest_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> QuestCompleteResponse:
    """Claim rewards from a returned quest party."""
    await get_user_vault_or_403(vault_id, user, db_session)
    quest, granted_rewards = await quest_service.claim_quest_rewards(db_session, quest_id, vault_id)
    return QuestCompleteResponse(
        quest_id=quest.id,
        quest_title=quest.title,
        is_completed=True,
        granted_rewards=[granted_reward_adapter.validate_python(reward) for reward in granted_rewards],
    )


@router.get("/{vault_id}/{quest_id}/party", response_model=list[QuestPartyMemberRead])
async def get_quest_party(
    vault_id: UUID,
    quest_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> list[QuestPartyMemberRead]:
    """Get party members assigned to a quest."""
    await get_user_vault_or_403(vault_id, user, db_session)
    members = await crud.team_crud.get_quest_team(db_session, quest_id, vault_id)
    return [_to_party_member_read(member, quest_id, vault_id) for member in members]


@router.post("/{vault_id}/{quest_id}/start", response_model=QuestRead, status_code=200)
async def start_quest(
    vault_id: UUID,
    quest_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
    party_data: QuestPartyAssign | None = None,
) -> Quest:
    """Start a quest, atomically assigning and departing the supplied party.

    The UI supplies dweller_ids for timed missions. Bodyless requests support
    state objectives and callers with an existing roster.
    """
    await get_user_vault_or_403(vault_id, user, db_session)
    await ensure_current_quest_rotation(db_session, vault_id)
    return await quest_service.start_quest_for_vault(
        db_session, vault_id, quest_id, dweller_ids=party_data.dweller_ids if party_data else None
    )


@router.get("/{vault_id}/{quest_id}/eligible-dwellers", response_model=list[EligibleDwellerRead])
async def get_eligible_dwellers(
    vault_id: UUID,
    quest_id: UUID,
    user: CurrentActiveUser,
    db_session: DBSession,
) -> list[EligibleDwellerRead]:
    """Get dwellers eligible for a quest based on requirements."""
    await get_user_vault_or_403(vault_id, user, db_session)
    return await quest_service.get_eligible_dwellers(db_session, vault_id, quest_id)
