"""Earned hazard teams: service turns into a place on a standing team."""

import logging

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import HazardTeam
from app.crud.hazard_team import hazard_team_crud
from app.crud.incident_participant import incident_participant_crud
from app.models.dweller import Dweller
from app.models.hazard_team import ACTIVE_STATUS, RESERVE_STATUS, HazardTeamMember
from app.models.incident import HAZARD_TEAM_INCIDENT_TYPES, Incident, hazard_team_for
from app.schemas.contamination_team import ContaminationTeamRead, HazardTeamMemberRead, HazardTeamRosterRead
from app.services.bio_service import bio_service

logger = logging.getLogger(__name__)

#: Incident participations required before a dweller earns a place on a team.
QUALIFYING_INCIDENTS = 3
#: Dwellers who hold a team; further qualifiers wait on the bench.
TEAM_SIZE = 3
#: Bio entry source for service milestones (declared in ``bio_service.BIO_SECTIONS``).
BIO_SOURCE = "hazard"
#: How each team reads in a dweller's biography.
TEAM_LABELS: dict[HazardTeam, str] = {
    HazardTeam.FIRE: "fire team",
    HazardTeam.RADIATION: "radiation team",
}


class ContaminationTeamService:
    """Turns incident participation into earned places and bio milestones."""

    async def record_participation(
        self, db_session: AsyncSession, incident: Incident, dwellers: list[Dweller]
    ) -> list[Dweller]:
        """Credit this round's defenders and promote anyone who just qualified.

        Called inside the incident round, so everything written here rides the
        round's single commit and a failed round leaves no trace.
        """
        if not dwellers:
            return []
        credited_ids = await incident_participant_crud.record(
            db_session, incident.id, [dweller.id for dweller in dwellers]
        )
        team = hazard_team_for(incident.type)
        if not team or not credited_ids:
            return []
        dwellers_by_id = {dweller.id: dweller for dweller in dwellers}
        joined: list[Dweller] = []
        for dweller_id in credited_ids:
            dweller = dwellers_by_id.get(dweller_id)
            if dweller and await self._join_if_qualified(db_session, incident.vault_id, dweller, team):
                joined.append(dweller)
        return joined

    async def _join_if_qualified(
        self, db_session: AsyncSession, vault_id: UUID4, dweller: Dweller, team: HazardTeam
    ) -> bool:
        if await hazard_team_crud.get_member(db_session, vault_id, team, dweller.id):
            return False
        fought = await incident_participant_crud.count_incidents(
            db_session, dweller.id, HAZARD_TEAM_INCIDENT_TYPES[team]
        )
        if fought < QUALIFYING_INCIDENTS:
            return False
        active = await hazard_team_crud.count_active(db_session, vault_id, team)
        status = ACTIVE_STATUS if active < TEAM_SIZE else RESERVE_STATUS
        await hazard_team_crud.add(
            db_session,
            HazardTeamMember(vault_id=vault_id, dweller_id=dweller.id, team=team, status=status),
        )
        self._record_bio_entry(dweller, team, status, fought)
        logger.info(f"{dweller.first_name} {dweller.last_name} joined the {TEAM_LABELS[team]} as {status}")
        return True

    def _record_bio_entry(self, dweller: Dweller, team: HazardTeam, status: str, fought: int) -> None:
        label = TEAM_LABELS[team]
        callouts = f"{fought} {'callout' if fought == 1 else 'callouts'}"
        text = (
            f"Took a place on the vault's {label} after {callouts}."
            if status == ACTIVE_STATUS
            else f"Earned a bench place on the vault's {label} after {callouts}."
        )
        bio_service.add_entry(dweller, BIO_SOURCE, text, {"team": team.value, "status": status})

    async def get_roster(self, db_session: AsyncSession, vault_id: UUID4) -> ContaminationTeamRead:
        """Every team's roster for a vault, active places and bench included."""
        teams: list[HazardTeamRosterRead] = []
        for team in HazardTeam:
            places = await hazard_team_crud.get_team(db_session, vault_id, team)
            teams.append(
                HazardTeamRosterRead(
                    team=team,
                    active=[_place_read(place) for place in places if place.status == ACTIVE_STATUS],
                    reserve=[_place_read(place) for place in places if place.status == RESERVE_STATUS],
                )
            )
        return ContaminationTeamRead(vault_id=vault_id, teams=teams)


contamination_team_service = ContaminationTeamService()


def _place_read(place: HazardTeamMember) -> HazardTeamMemberRead:
    return HazardTeamMemberRead(dweller_id=place.dweller_id, status=place.status)
