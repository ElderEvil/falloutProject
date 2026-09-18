"""CRUD for the reusable team roster primitive."""

import logging

from pydantic import UUID4
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.team import Team, TeamMember

logger = logging.getLogger(__name__)


class CRUDTeam(CRUDBase[Team, None, None]):
    async def get_quest_team_row(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> Team | None:
        """The vault's team row for a quest, members and dwellers eager-loaded, or None."""
        result = await db_session.execute(
            select(Team)
            .where(Team.vault_id == vault_id, Team.quest_id == quest_id)
            .options(selectinload(Team.members).selectinload(TeamMember.dweller))
        )
        return result.scalars().one_or_none()

    async def get_quest_team(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> list[TeamMember]:
        """All members of the vault's team for a quest, dweller eager-loaded."""
        team = await self.get_quest_team_row(db_session, quest_id, vault_id)
        return list(team.members) if team is not None else []

    async def get_member(self, db_session: AsyncSession, team_id: UUID4, dweller_id: UUID4) -> TeamMember | None:
        """One member row of a team, or None."""
        result = await db_session.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.dweller_id == dweller_id)
        )
        return result.scalars().one_or_none()

    async def get_or_create_quest_team(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> Team:
        """The vault's quest team, created on first assignment (flushed so the id is usable)."""
        team = await self.get_quest_team_row(db_session, quest_id, vault_id)
        if team is not None:
            return team
        team = Team(vault_id=vault_id, quest_id=quest_id)
        db_session.add(team)
        await db_session.flush()
        return team

    async def delete_quest_team(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> None:
        """Remove the vault's quest team; members cascade via delete-orphan."""
        team = await self.get_quest_team_row(db_session, quest_id, vault_id)
        if team is not None:
            await db_session.delete(team)

    async def get_incident_team_row(self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4) -> Team | None:
        """The vault's team row for an incident, members and dwellers eager-loaded, or None."""
        result = await db_session.execute(
            select(Team)
            .where(Team.vault_id == vault_id, Team.incident_id == incident_id)
            .options(selectinload(Team.members).selectinload(TeamMember.dweller))
            .execution_options(populate_existing=True)
        )
        return result.scalars().one_or_none()

    async def get_incident_team(
        self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4
    ) -> list[TeamMember]:
        """All members of the vault's team for an incident, dweller eager-loaded."""
        team = await self.get_incident_team_row(db_session, incident_id, vault_id)
        return list(team.members) if team is not None else []

    async def get_or_create_incident_team(self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4) -> Team:
        """The vault's incident team, created on first assignment (flushed so the id is usable)."""
        team = await self.get_incident_team_row(db_session, incident_id, vault_id)
        if team is not None:
            return team
        team = Team(vault_id=vault_id, incident_id=incident_id)
        team.members = []
        db_session.add(team)
        await db_session.flush()
        return team

    async def replace_incident_team(
        self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4, dweller_ids: list[UUID4]
    ) -> list[TeamMember]:
        """Replace the vault's incident roster with the given dwellers (no slot numbers)."""
        existing_members = await self.get_incident_team(db_session, incident_id, vault_id)
        for member in existing_members:
            await db_session.delete(member)
        await db_session.flush()
        team = await self.get_or_create_incident_team(db_session, incident_id, vault_id)
        members = [
            TeamMember(team_id=team.id, dweller_id=dweller_id, slot_number=None, status="assigned")
            for dweller_id in dweller_ids
        ]
        db_session.add_all(members)
        await db_session.flush()
        return members

    async def delete_incident_team(self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4) -> None:
        """Remove the vault's incident team; members cascade via delete-orphan."""
        team = await self.get_incident_team_row(db_session, incident_id, vault_id)
        if team is not None:
            await db_session.delete(team)


team_crud = CRUDTeam(Team)
