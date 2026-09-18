"""Team roster orchestration: assigning dwellers to quest teams.

Owns the assignment rules that used to live in ``CRUDQuestParty.assign_party``;
the quest endpoints call this service and map the resulting ``TeamMember`` rows
back into the ``QuestPartyMemberRead`` wire contract.
"""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.team import TeamMember
from app.models.vault import Vault
from app.utils.dweller_availability import availability_error
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)


class TeamService:
    async def assign_quest_team(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4, dweller_ids: list[UUID4]
    ) -> list[TeamMember]:
        """Assign dwellers to a quest team, replacing any existing roster."""
        if len(dweller_ids) > 3 or len(dweller_ids) < 1:
            raise ValidationException("Party size must be 1-3")

        if not await crud.quest_crud.get_or_none(db_session, quest_id):
            raise ResourceNotFoundException(Quest, identifier=quest_id)
        if not await crud.vault.get_or_none(db_session, vault_id):
            raise ResourceNotFoundException(Vault, identifier=vault_id)

        if (link := await crud.quest_crud.get_link(db_session, quest_id=quest_id, vault_id=vault_id)) and (
            link.started_at is not None or link.is_reward_ready or link.is_completed
        ):
            raise ResourceConflictException("Quest is already in progress")

        existing_members = await crud.team_crud.get_quest_team(db_session, quest_id, vault_id)
        existing_dweller_ids = {member.dweller_id for member in existing_members}

        # Validate the full replacement before clearing the current team.
        dwellers_by_id = {}
        for dweller_id in dweller_ids:
            # include_deleted so availability_error can reject soft-deleted dwellers explicitly.
            dweller = await crud.dweller.get_or_none(db_session, dweller_id, include_deleted=True)
            if not dweller:
                raise ResourceNotFoundException(Dweller, identifier=dweller_id)
            if dweller.vault_id != vault_id:
                raise ValidationException(f"Dweller {dweller_id} does not belong to vault {vault_id}")
            error = availability_error(dweller, require_healthy=False)
            # A dweller already on THIS quest's team may stay QUESTING.
            if error is not None and not (
                dweller.status == DwellerStatusEnum.QUESTING and dweller_id in existing_dweller_ids
            ):
                raise ValidationException(f"Dweller {dweller_id} {error}")
            dwellers_by_id[dweller_id] = dweller

        for member in existing_members:
            if member.dweller:
                member.dweller.status = DwellerStatusEnum.IDLE
            await db_session.delete(member)
        await db_session.flush()

        team = await crud.team_crud.get_or_create_quest_team(db_session, quest_id, vault_id)

        members = []
        for i, dweller_id in enumerate(dweller_ids):
            dweller = dwellers_by_id[dweller_id]
            dweller.status = DwellerStatusEnum.QUESTING

            member = TeamMember(
                team_id=team.id,
                dweller_id=dweller_id,
                slot_number=i + 1,
                status="assigned",
            )
            db_session.add(member)
            members.append(member)

        await db_session.commit()
        for member in members:
            await db_session.refresh(member)

        logger.info(f"Assigned {len(members)} dwellers to quest {quest_id}")
        return members


team_service = TeamService()
