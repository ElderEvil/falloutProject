"""CRUD for the reusable team roster primitive."""

import logging

from pydantic import UUID4
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.team import Team, TeamMember

logger = logging.getLogger(__name__)


class CRUDTeam(CRUDBase[Team, None, None]):
    async def _team_row(
        self,
        db_session: AsyncSession,
        purpose: InstrumentedAttribute,
        value: UUID4,
        vault_id: UUID4,
        *,
        refresh: bool = False,
    ) -> Team | None:
        """The vault's team row for one purpose, members and dwellers eager-loaded, or None.

        ``refresh`` forces a read even when the row is already in the session's identity
        map. Incident readers need it so a reassignment sees the committed roster; quest
        readers must not use it, because a caller may hold uncommitted dweller changes
        (e.g. the state-objective backfill) that a refresh would discard.
        """
        statement = (
            select(Team)
            .where(Team.vault_id == vault_id, purpose == value)
            .options(selectinload(Team.members).selectinload(TeamMember.dweller))
        )
        if refresh:
            statement = statement.execution_options(populate_existing=True)
        result = await db_session.execute(statement)
        return result.scalars().one_or_none()

    @staticmethod
    def _members(team: Team | None) -> list[TeamMember]:
        """A team's members in slot order (missing slots first), or empty when there is no team."""
        if team is None:
            return []
        return sorted(team.members, key=lambda member: (member.slot_number is not None, member.slot_number))

    async def get_member(self, db_session: AsyncSession, team_id: UUID4, dweller_id: UUID4) -> TeamMember | None:
        """One member row of a team, or None."""
        result = await db_session.execute(
            select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.dweller_id == dweller_id)
        )
        return result.scalars().one_or_none()

    async def get_quest_team_row(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> Team | None:
        """The vault's team row for a quest, members and dwellers eager-loaded, or None."""
        return await self._team_row(db_session, Team.quest_id, quest_id, vault_id)

    async def get_quest_team(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> list[TeamMember]:
        """All members of the vault's team for a quest, dweller eager-loaded, slot-ordered."""
        return self._members(await self.get_quest_team_row(db_session, quest_id, vault_id))

    async def get_or_create_quest_team(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> Team:
        """The vault's quest team, created on first assignment (flushed so the id is usable)."""
        team = await self.get_quest_team_row(db_session, quest_id, vault_id)
        if team is not None:
            return team
        team = Team(vault_id=vault_id, quest_id=quest_id)
        team.members = []
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
        return await self._team_row(db_session, Team.incident_id, incident_id, vault_id, refresh=True)

    async def get_incident_team(
        self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4
    ) -> list[TeamMember]:
        """All members of the vault's team for an incident, dweller eager-loaded."""
        return self._members(await self.get_incident_team_row(db_session, incident_id, vault_id))

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

    async def add_incident_team_members(
        self, db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4, dweller_ids: list[UUID4]
    ) -> list[TeamMember]:
        """Append dwellers to the vault's incident roster; never removes members.

        The roster is the set of responders sent for the incident; combat presence
        stays derived from the room, so appending keeps them consistent. Dwellers
        already on the roster are skipped (no ``uq_team_member_dweller`` violation).
        """
        team = await self.get_or_create_incident_team(db_session, incident_id, vault_id)
        existing_ids = {member.dweller_id for member in team.members}
        members = [
            TeamMember(team_id=team.id, dweller_id=dweller_id, slot_number=None, status="assigned")
            for dweller_id in dweller_ids
            if dweller_id not in existing_ids
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
