"""CRUD for the reusable team roster primitive."""

import logging

from pydantic import UUID4
from sqlalchemy import func, update
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import HazardTeam
from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS, Team, TeamMember

logger = logging.getLogger(__name__)


class CRUDTeam(CRUDBase[Team, None, None]):
    async def _team_row(
        self,
        db_session: AsyncSession,
        purpose: InstrumentedAttribute,
        value: UUID4 | HazardTeam,
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

    async def get_quest_team_row(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> Team | None:
        """The vault's team row for a quest, members and dwellers eager-loaded, or None."""
        return await self._team_row(db_session, Team.quest_id, quest_id, vault_id)

    async def get_quest_team(self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4) -> list[TeamMember]:
        """All members of the vault's team for a quest, dweller eager-loaded, slot-ordered."""
        return self._members(await self.get_quest_team_row(db_session, quest_id, vault_id))

    async def get_quest_team_dwellers(
        self, db_session: AsyncSession, quest_id: UUID4, vault_id: UUID4
    ) -> list[Dweller]:
        """The quest party's Dweller rows, weapon/outfit eager-loaded, in slot order."""
        team = await self.get_quest_team_row(db_session, quest_id, vault_id)
        members = self._members(team)
        if not members:
            return []
        result = await db_session.execute(
            select(Dweller)
            .options(selectinload(Dweller.weapon), selectinload(Dweller.outfit))
            .where(Dweller.id.in_([member.dweller_id for member in members]))
        )
        by_id = {dweller.id: dweller for dweller in result.scalars().all()}
        return [by_id[member.dweller_id] for member in members if member.dweller_id in by_id]

    async def get_exploration_team(self, db_session: AsyncSession, exploration_id: UUID4) -> Team | None:
        """The team row for an exploration dispatch, members and dwellers eager-loaded, or None."""
        statement = (
            select(Team)
            .where(Team.exploration_id == exploration_id)
            .options(selectinload(Team.members).selectinload(TeamMember.dweller))
        )
        result = await db_session.execute(statement)
        return result.scalars().one_or_none()

    async def get_exploration_team_dwellers(self, db_session: AsyncSession, exploration_id: UUID4) -> list[Dweller]:
        """The dispatch party's Dweller rows, weapon/outfit eager-loaded, in slot order."""
        team = await self.get_exploration_team(db_session, exploration_id)
        members = self._members(team)
        if not members:
            return []
        result = await db_session.execute(
            select(Dweller)
            .options(selectinload(Dweller.weapon), selectinload(Dweller.outfit))
            .where(Dweller.id.in_([member.dweller_id for member in members]))
        )
        by_id = {dweller.id: dweller for dweller in result.scalars().all()}
        return [by_id[member.dweller_id] for member in members if member.dweller_id in by_id]

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

    def _hazard_members_query(self, vault_id: UUID4, team: HazardTeam, *, status: str | None = None):
        """Living members of a vault's hazard team, scoped by the team's purpose column.

        A fallen or removed member must not occupy a place, or the team keeps a
        phantom slot and no bench member can ever step up.
        """
        query = (
            select(TeamMember)
            .join(Team, Team.id == TeamMember.team_id)
            .join(Dweller, Dweller.id == TeamMember.dweller_id)
            .where(
                Team.vault_id == vault_id,
                Team.hazard_team == team,
                Dweller.is_dead.is_(False),
                Dweller.is_deleted.is_(False),
            )
        )
        if status is not None:
            query = query.where(TeamMember.status == status)
        return query

    async def _hazard_members(
        self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam, *, status: str | None = None
    ) -> list[TeamMember]:
        """Living hazard-team members, most senior first."""
        query = self._hazard_members_query(vault_id, team, status=status).order_by(TeamMember.created_at)
        return list((await db_session.execute(query)).scalars().all())

    async def get_hazard_team(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> list[TeamMember]:
        """Every place a living dweller holds on one hazard team, most senior first."""
        return await self._hazard_members(db_session, vault_id, team)

    async def get_hazard_reserve(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> list[TeamMember]:
        """Bench places held by a living dweller, most senior first."""
        return await self._hazard_members(db_session, vault_id, team, status=RESERVE_STATUS)

    async def count_active_hazard(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> int:
        """How many of the team's places are held by a living dweller."""
        query = self._hazard_members_query(vault_id, team, status=ACTIVE_STATUS).with_only_columns(func.count())
        return (await db_session.execute(query)).scalar_one_or_none() or 0

    async def get_active_hazard_member_ids(
        self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam, dweller_ids: list[UUID4]
    ) -> set[UUID4]:
        """Ids among ``dweller_ids`` who hold a living active place on the team."""
        if not dweller_ids:
            return set()
        query = (
            self._hazard_members_query(vault_id, team, status=ACTIVE_STATUS)
            .where(TeamMember.dweller_id.in_(dweller_ids))
            .with_only_columns(TeamMember.dweller_id)
        )
        return set((await db_session.execute(query)).scalars().all())

    async def get_hazard_member(
        self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam, dweller_id: UUID4
    ) -> TeamMember | None:
        """The dweller's place on this hazard team, if they hold one."""
        query = (
            select(TeamMember)
            .join(Team, Team.id == TeamMember.team_id)
            .where(
                Team.vault_id == vault_id,
                Team.hazard_team == team,
                TeamMember.dweller_id == dweller_id,
            )
        )
        return (await db_session.execute(query)).scalar_one_or_none()

    async def get_or_create_hazard_team(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> Team:
        """The vault's hazard team, created on first qualification (flushed so the id is usable).

        Deliberately reads without ``populate_existing``: this runs inside the
        incident round, where a refresh would expire the combatants' eager-loaded
        equipment.
        """
        row = await self._team_row(db_session, Team.hazard_team, team, vault_id)
        if row is not None:
            return row
        row = Team(vault_id=vault_id, hazard_team=team)
        row.members = []
        db_session.add(row)
        await db_session.flush()
        return row

    async def free_dead_hazard_slots(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> None:
        """Bench the fallen members of a hazard team so their place can be refilled.

        A dead member's row persists, but its slot must be freed or the unique slot
        constraint blocks the promotion that fills the place the loss opened. The
        member is demoted to ``reserve`` at the same time: holding a slot is what
        makes a member ``active``, so a slot-less active row would count as a
        responder again if the dweller were later revived.
        """
        await db_session.execute(
            update(TeamMember)
            .where(
                TeamMember.team_id.in_(select(Team.id).where(Team.vault_id == vault_id, Team.hazard_team == team)),
                TeamMember.status == ACTIVE_STATUS,
                TeamMember.slot_number.is_not(None),
                TeamMember.dweller_id.in_(
                    select(Dweller.id).where(Dweller.is_dead.is_(True) | Dweller.is_deleted.is_(True))
                ),
            )
            .values(slot_number=None, status=RESERVE_STATUS)
        )

    async def add_member(self, db_session: AsyncSession, member: TeamMember) -> TeamMember:
        """Stage a roster place on the caller's transaction."""
        db_session.add(member)
        await db_session.flush()
        return member


team_crud = CRUDTeam(Team)
