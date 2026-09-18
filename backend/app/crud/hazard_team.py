"""Queries for the standing hazard-team roster."""

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import HazardTeam
from app.crud.base import CRUDBase
from app.models.hazard_team import ACTIVE_STATUS, HazardTeamMember


class CRUDHazardTeam(CRUDBase[HazardTeamMember, None, None]):
    async def get_member(
        self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam, dweller_id: UUID4
    ) -> HazardTeamMember | None:
        """The dweller's place on this team, if they hold one."""
        query = select(HazardTeamMember).where(
            HazardTeamMember.vault_id == vault_id,
            HazardTeamMember.team == team,
            HazardTeamMember.dweller_id == dweller_id,
        )
        return (await db_session.execute(query)).scalar_one_or_none()

    async def get_team(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> list[HazardTeamMember]:
        """Every roster place on one team, most senior first."""
        query = (
            select(HazardTeamMember)
            .where(HazardTeamMember.vault_id == vault_id, HazardTeamMember.team == team)
            .order_by(HazardTeamMember.created_at)
        )
        return list((await db_session.execute(query)).scalars().all())

    async def count_active(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> int:
        """How many of the team's slots are filled."""
        query = (
            select(func.count())
            .select_from(HazardTeamMember)
            .where(
                HazardTeamMember.vault_id == vault_id,
                HazardTeamMember.team == team,
                HazardTeamMember.status == ACTIVE_STATUS,
            )
        )
        return (await db_session.execute(query)).scalar_one_or_none() or 0

    async def add(self, db_session: AsyncSession, member: HazardTeamMember) -> HazardTeamMember:
        """Stage a roster place on the caller's transaction."""
        db_session.add(member)
        await db_session.flush()
        return member


hazard_team_crud = CRUDHazardTeam(HazardTeamMember)
