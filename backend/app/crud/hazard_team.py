"""Queries for the standing hazard-team roster."""

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import HazardTeam
from app.crud.base import CRUDBase
from app.models.dweller import Dweller
from app.models.hazard_team import ACTIVE_STATUS, RESERVE_STATUS, HazardTeamMember


def _living_places():
    """Roster places held by a dweller who can still serve.

    A fallen or removed member must stop occupying a place, or the team keeps a
    phantom slot and no bench member can ever step up.
    """
    return (
        select(HazardTeamMember)
        .join(Dweller, Dweller.id == HazardTeamMember.dweller_id)
        .where(Dweller.is_dead.is_(False), Dweller.is_deleted.is_(False))
    )


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
        """Every place a living dweller holds on one team, most senior first."""
        query = _living_places().where(HazardTeamMember.vault_id == vault_id, HazardTeamMember.team == team)
        query = query.order_by(HazardTeamMember.created_at)
        return list((await db_session.execute(query)).scalars().all())

    async def get_reserve(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> list[HazardTeamMember]:
        """Bench places held by a living dweller, most senior first."""
        query = _living_places().where(
            HazardTeamMember.vault_id == vault_id,
            HazardTeamMember.team == team,
            HazardTeamMember.status == RESERVE_STATUS,
        )
        query = query.order_by(HazardTeamMember.created_at)
        return list((await db_session.execute(query)).scalars().all())

    async def count_active(self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam) -> int:
        """How many of the team's places are held by a living dweller."""
        query = (
            select(func.count())
            .select_from(HazardTeamMember)
            .join(Dweller, Dweller.id == HazardTeamMember.dweller_id)
            .where(
                HazardTeamMember.vault_id == vault_id,
                HazardTeamMember.team == team,
                HazardTeamMember.status == ACTIVE_STATUS,
                Dweller.is_dead.is_(False),
                Dweller.is_deleted.is_(False),
            )
        )
        return (await db_session.execute(query)).scalar_one_or_none() or 0

    async def get_active_member_ids(
        self, db_session: AsyncSession, vault_id: UUID4, team: HazardTeam, dweller_ids: list[UUID4]
    ) -> set[UUID4]:
        """Ids among ``dweller_ids`` who hold a living active place on the team."""
        if not dweller_ids:
            return set()
        query = (
            select(HazardTeamMember.dweller_id)
            .join(Dweller, Dweller.id == HazardTeamMember.dweller_id)
            .where(
                HazardTeamMember.vault_id == vault_id,
                HazardTeamMember.team == team,
                HazardTeamMember.status == ACTIVE_STATUS,
                HazardTeamMember.dweller_id.in_(dweller_ids),
                Dweller.is_dead.is_(False),
                Dweller.is_deleted.is_(False),
            )
        )
        return set((await db_session.execute(query)).scalars().all())

    async def add(self, db_session: AsyncSession, member: HazardTeamMember) -> HazardTeamMember:
        """Stage a roster place on the caller's transaction."""
        db_session.add(member)
        await db_session.flush()
        return member


hazard_team_crud = CRUDHazardTeam(HazardTeamMember)
