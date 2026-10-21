"""Team roster orchestration: assigning dwellers to quest teams.

Owns the assignment rules that used to live in ``CRUDQuestParty.assign_party``;
quest start uses this service to stage its ``TeamMember`` rows before departure.
The caller owns the transaction.
"""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.quest import Quest
from app.models.team import TeamMember
from app.models.vault import Vault
from app.utils.dweller_availability import availability_error
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException
from app.utils.quest_duration import STATE_QUEST_CATEGORIES

logger = logging.getLogger(__name__)


class TeamService:
    async def assign_quest_team(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4, dweller_ids: list[UUID4]
    ) -> list[TeamMember]:
        """Assign dwellers to a quest team, replacing any existing roster.

        Stages the roster in the caller's transaction; ``start_quest`` owns
        validation, departure, and commit.
        """
        if len(set(dweller_ids)) != len(dweller_ids):
            raise ValidationException("Choose each dweller only once")
        if len(dweller_ids) > 3 or len(dweller_ids) < 1:
            raise ValidationException("Party size must be 1-3")

        quest = await crud.quest_crud.get_or_none(db_session, quest_id)
        if not quest:
            raise ResourceNotFoundException(Quest, identifier=quest_id)
        if quest.quest_category in STATE_QUEST_CATEGORIES:
            # State objectives complete instantly on start and never run the
            # return path, so a party would stay QUESTING forever.
            raise ValidationException("State objectives cannot take a quest party")
        if not await crud.vault.get_or_none(db_session, vault_id):
            raise ResourceNotFoundException(Vault, identifier=vault_id)

        if (link := await crud.quest_crud.get_link(db_session, quest_id=quest_id, vault_id=vault_id)) and (
            link.started_at is not None or link.is_reward_ready or link.is_completed
        ):
            raise ResourceConflictException("Quest is already in progress")

        existing_members = await crud.team_crud.get_quest_team(db_session, quest_id, vault_id)

        # Validate the full replacement before clearing the current team.
        for dweller_id in dweller_ids:
            # include_deleted so availability_error can reject soft-deleted dwellers explicitly.
            dweller = await crud.dweller.get_or_none(db_session, dweller_id, include_deleted=True)
            if not dweller:
                raise ResourceNotFoundException(Dweller, identifier=dweller_id)
            if dweller.vault_id != vault_id:
                raise ValidationException(f"Dweller {dweller_id} does not belong to vault {vault_id}")
            error = availability_error(dweller, require_healthy=False)
            if error is not None:
                raise ValidationException(f"Dweller {dweller_id} {error}")

        for member in existing_members:
            await db_session.delete(member)
        await db_session.flush()

        team = await crud.team_crud.get_or_create_quest_team(db_session, quest_id, vault_id)

        members = []
        for i, dweller_id in enumerate(dweller_ids):
            member = TeamMember(
                team_id=team.id,
                dweller_id=dweller_id,
                slot_number=i + 1,
                status="assigned",
            )
            db_session.add(member)
            members.append(member)

        await db_session.flush()

        logger.debug("Staged %s dwellers for quest %s; caller owns commit", len(members), quest_id)
        return members


team_service = TeamService()
